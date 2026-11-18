#!/usr/bin/env python3
"""File type detection and per-type static analysis for every upload that is
not a Windows PE (PEs keep going to malware_detection/analyze.py).

Two modes, both run by the backend through src/stages/pythonStage.js:

    content_analyze.py detect    -> the `file_type` stage
    content_analyze.py analyze   -> the `content_analysis` stage

Input on stdin:  {"path": "/abs/path/to/upload", "filename": "invoice.pdf"}
Output on stdout: one JSON object (shapes in backend/docs/api-contract.md).
Failure: exit 1 with {"error": ..., "message": ...} as JSON on stderr.

The type comes from the file's CONTENT (magic bytes and container
structure), never from its name alone, so an .exe renamed to .pdf is still
treated as an .exe -- and flagged.

Everything here is static: nothing in the file is ever executed or opened by
another program. Only the Python standard library is required. If `oletools`
is installed (pip install -r scripts/requirements-content.txt), Office macro
source is also decompressed and scanned; without it, macros are still
detected but not read.

Findings are evidence, not a verdict. `risk_level` is just the highest
severity among the findings; the ML stages and the dashboard decide what the
sample is.
"""

import gzip
import io
import json
import math
import os
import re
import sys
import tarfile
import zipfile
import zlib
from collections import Counter

ANALYZER_VERSION = "1.0.0"

MAX_FILE_BYTES = 50 * 1024 * 1024        # never read more than this
MAX_SCAN_BYTES = 8 * 1024 * 1024         # regex scans look at this much text
MAX_MEMBER_BYTES = 10 * 1024 * 1024      # biggest archive member we unpack
MAX_TOTAL_EXTRACT = 50 * 1024 * 1024     # all members of one archive, together
MAX_ARCHIVE_DEPTH = 3                    # zip in zip in zip
MAX_MEMBERS_ANALYZED = 200
MAX_MEMBERS_LISTED = 500
MAX_INDICATORS = 50
MAX_FINDINGS = 60
MAX_PDF_STREAMS = 500

try:  # optional: Office macro source analysis
    from oletools.olevba import VBA_Parser  # type: ignore
    HAVE_OLETOOLS = True
except Exception:  # pragma: no cover - depends on the environment
    HAVE_OLETOOLS = False


# ---------------------------------------------------------------------------
# Type detection
# ---------------------------------------------------------------------------

# format -> (category, description, extensions that are normal for it)
FORMATS = {
    "pe": ("executable", "Windows PE executable", {".exe", ".dll", ".scr", ".sys", ".cpl", ".ocx", ".drv", ".efi", ".com", ".mui", ".ax"}),
    "dos": ("executable", "DOS MZ executable", {".exe", ".com"}),
    "dos_com": ("executable", "DOS .COM program (no header)", {".com"}),
    "elf": ("executable", "Linux/Unix ELF binary", {".so", ".elf", ".bin", ".o", ".out", ".ko"}),
    "macho": ("executable", "macOS Mach-O binary", {".dylib", ".bundle", ".macho", ".o"}),
    "java_class": ("executable", "Java class file", {".class"}),
    "jar": ("executable", "Java archive (JAR)", {".jar", ".war", ".ear"}),
    "apk": ("executable", "Android app (APK)", {".apk", ".xapk"}),
    "msi": ("installer", "Windows Installer package", {".msi", ".msp", ".mst"}),
    "doc": ("office", "Word 97-2003 document", {".doc", ".dot"}),
    "xls": ("office", "Excel 97-2003 workbook", {".xls", ".xlt", ".xla"}),
    "ppt": ("office", "PowerPoint 97-2003 presentation", {".ppt", ".pps", ".pot"}),
    "ole": ("office", "OLE compound file", {".doc", ".xls", ".ppt", ".pps", ".dot", ".xlt", ".pot", ".msg", ".vsd", ".pub"}),
    "docx": ("office", "Word document (OOXML)", {".docx", ".docm", ".dotx", ".dotm"}),
    "xlsx": ("office", "Excel workbook (OOXML)", {".xlsx", ".xlsm", ".xltx", ".xltm", ".xlsb", ".xlam"}),
    "pptx": ("office", "PowerPoint presentation (OOXML)", {".pptx", ".pptm", ".ppsx", ".ppsm", ".potx", ".potm"}),
    "rtf": ("office", "Rich Text Format document", {".rtf", ".doc"}),
    "onenote": ("office", "OneNote section", {".one", ".onepkg"}),
    "csv": ("office", "CSV spreadsheet", {".csv"}),
    "pdf": ("pdf", "PDF document", {".pdf"}),
    "powershell": ("script", "PowerShell script", {".ps1", ".psm1", ".psd1"}),
    "batch": ("script", "Windows batch script", {".bat", ".cmd"}),
    "vbscript": ("script", "VBScript", {".vbs", ".vbe"}),
    "jscript": ("script", "JavaScript / JScript", {".js", ".jse", ".mjs"}),
    "wsf": ("script", "Windows Script File", {".wsf", ".wsc"}),
    "hta": ("script", "HTML Application", {".hta"}),
    "python": ("script", "Python script", {".py", ".pyw"}),
    "shell": ("script", "Shell script", {".sh", ".bash", ".zsh", ".ksh"}),
    "c": ("source", "C source", {".c"}),
    "cpp": ("source", "C++ source", {".cpp", ".cc", ".cxx", ".c++"}),
    "c_header": ("source", "C/C++ header", {".h", ".hpp", ".hh", ".hxx"}),
    "csharp": ("source", "C# source", {".cs"}),
    "go": ("source", "Go source", {".go"}),
    "rust": ("source", "Rust source", {".rs"}),
    "java": ("source", "Java source", {".java"}),
    "zip": ("archive", "ZIP archive", {".zip", ".zipx"}),
    "rar": ("archive", "RAR archive", {".rar"}),
    "7z": ("archive", "7-Zip archive", {".7z"}),
    "gzip": ("archive", "gzip compressed file", {".gz", ".tgz", ".gzip"}),
    "tar": ("archive", "tar archive", {".tar"}),
    "cab": ("archive", "Microsoft Cabinet archive", {".cab"}),
    "iso": ("archive", "ISO disk image", {".iso"}),
    "vhd": ("archive", "Virtual hard disk image", {".vhd", ".vhdx"}),
    "img": ("archive", "Raw disk image", {".img"}),
    "lnk": ("shortcut", "Windows shortcut (.lnk)", {".lnk"}),
    "internet_shortcut": ("shortcut", "Internet shortcut (.url)", {".url"}),
    "html": ("web", "HTML page", {".html", ".htm", ".xhtml", ".shtml"}),
    "svg": ("web", "SVG image", {".svg"}),
    "chm": ("web", "Compiled HTML Help", {".chm"}),
    "text": ("unknown", "Plain text", set()),
    "unknown": ("unknown", "Unrecognized binary data", set()),
}

EXT_TO_TEXT_FORMAT = {}
for _fmt in ("powershell", "batch", "vbscript", "jscript", "wsf", "hta", "python", "shell",
             "c", "cpp", "c_header", "csharp", "go", "rust", "java",
             "html", "svg", "internet_shortcut", "csv"):
    for _ext in FORMATS[_fmt][2]:
        EXT_TO_TEXT_FORMAT[_ext] = _fmt

EXECUTABLE_LIKE_EXTS = {
    ".exe", ".scr", ".com", ".pif", ".bat", ".cmd", ".js", ".jse", ".vbs", ".vbe",
    ".wsf", ".hta", ".ps1", ".lnk", ".msi", ".jar", ".dll", ".cpl", ".iso", ".img",
}
DOCUMENT_LIKE_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf",
    ".jpg", ".jpeg", ".png", ".gif", ".mp3", ".mp4", ".csv", ".zip",
}
RTLO = "\u202e"


def ext_of(filename):
    return os.path.splitext(filename or "")[1].lower()


def is_text(data):
    head = data[:8192]
    if not head:
        return True
    if b"\x00" in head:
        # UTF-16 text (PowerShell often saves this way) has NULs; accept a BOM.
        return head.startswith((b"\xff\xfe", b"\xfe\xff"))
    printable = sum(1 for b in head if b in (9, 10, 13) or 32 <= b < 127 or b >= 128)
    return printable / len(head) > 0.95


def decode_text(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8", errors="replace")


def zip_names(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return [i.filename for i in zf.infolist()[:5000]]
    except Exception:
        return None


def ole_format(data, ext):
    if ext in (".msi", ".msp", ".mst"):
        return "msi"
    # Directory entry names are UTF-16LE.
    def has(name):
        return name.encode("utf-16-le") in data
    if has("WordDocument"):
        return "doc"
    if has("Workbook") or has("Book"):
        return "xls"
    if has("PowerPoint Document"):
        return "ppt"
    return "ole"


def detect_bytes(data, filename):
    ext = ext_of(filename)
    fmt = None

    if data[:2] == b"MZ":
        fmt = "dos"
        if len(data) >= 0x40:
            e_lfanew = int.from_bytes(data[0x3C:0x40], "little")
            if 0 < e_lfanew < len(data) - 4 and data[e_lfanew:e_lfanew + 4] == b"PE\x00\x00":
                fmt = "pe"
    elif data[:4] == b"\x7fELF":
        fmt = "elf"
    elif data[:4] in (b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"):
        fmt = "macho"
    elif data[:4] == b"\xca\xfe\xba\xbe":
        # Shared by Java classes and universal Mach-O binaries: a fat binary
        # stores a small architecture count where a class stores its version.
        fmt = "java_class" if ext == ".class" or int.from_bytes(data[4:8], "big") >= 45 else "macho"
    elif b"%PDF-" in data[:1024]:
        fmt = "pdf"
    elif data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        fmt = ole_format(data, ext)
    elif data[:4] in (b"PK\x03\x04", b"PK\x05\x06"):
        names = zip_names(data) or []
        name_set = set(names)
        if "[Content_Types].xml" in name_set:
            if any(n.startswith("word/") for n in names):
                fmt = "docx"
            elif any(n.startswith("xl/") for n in names):
                fmt = "xlsx"
            elif any(n.startswith("ppt/") for n in names):
                fmt = "pptx"
            else:
                fmt = "zip"
        elif "AndroidManifest.xml" in name_set and any(n.endswith(".dex") for n in names):
            fmt = "apk"
        elif "META-INF/MANIFEST.MF" in name_set and (ext in (".jar", ".war", ".ear") or any(n.endswith(".class") for n in names)):
            fmt = "jar"
        else:
            fmt = "zip"
    elif data[:6] == b"Rar!\x1a\x07":
        fmt = "rar"
    elif data[:6] == b"7z\xbc\xaf\x27\x1c":
        fmt = "7z"
    elif data[:2] == b"\x1f\x8b":
        fmt = "gzip"
    elif data[257:262] == b"ustar":
        fmt = "tar"
    elif data[:4] == b"MSCF":
        fmt = "cab"
    elif data[0x8001:0x8006] == b"CD001" or data[0x8801:0x8806] == b"CD001":
        fmt = "iso"
    elif data[:8] == b"vhdxfile" or data[:8] == b"conectix" or data[-512:-504] == b"conectix":
        fmt = "vhd"
    elif data[:5] == b"{\\rtf" or data[:4] == b"{\\rt":
        fmt = "rtf"
    elif data[:20] == b"\x4c\x00\x00\x00\x01\x14\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00\x46":
        fmt = "lnk"
    elif data[:16] == b"\xe4\x52\x5c\x7b\x8c\xd8\xa7\x4d\xae\xb1\x53\x78\xd0\x29\x96\xd3":
        fmt = "onenote"
    elif data[:4] == b"ITSF":
        fmt = "chm"
    elif ext == ".com":
        fmt = "dos_com"  # headerless; only the name says what it is
    elif ext == ".img" and len(data) >= 512 and data[510:512] == b"\x55\xaa":
        fmt = "img"

    text = fmt is None and is_text(data)
    if fmt is None:
        if text:
            fmt = EXT_TO_TEXT_FORMAT.get(ext) or sniff_text_format(data) or "text"
        else:
            fmt = "unknown"

    category, description, normal_exts = FORMATS[fmt]
    # Only formats identified by their bytes can contradict the name; a text
    # format was mostly chosen *from* the name.
    by_content = fmt not in EXT_TO_TEXT_FORMAT.values() and fmt not in ("text", "unknown", "dos_com")
    mismatch = bool(by_content and ext and normal_exts and ext not in normal_exts)

    return {
        "category": category,
        "format": fmt,
        "description": description,
        "extension": ext or None,
        "is_text": bool(text),
        "size": len(data),
        "extension_mismatch": mismatch,
        "expected_extensions": sorted(normal_exts),
    }


def sniff_text_format(data):
    head = decode_text(data[:4096]).lstrip("\ufeff").lstrip()
    lower = head.lower()
    if head.startswith("#!"):
        first = lower.splitlines()[0]
        if "python" in first:
            return "python"
        if "node" in first:
            return "jscript"
        if "pwsh" in first or "powershell" in first:
            return "powershell"
        return "shell"
    if lower.startswith("[internetshortcut]"):
        return "internet_shortcut"
    if lower.startswith("<!doctype html") or lower.startswith("<html"):
        return "html"
    if lower.startswith("<svg") or ("<svg" in lower[:512] and lower.startswith("<?xml")):
        return "svg"
    if lower.startswith("<hta:") or "<hta:application" in lower:
        return "hta"
    if lower.startswith("@echo off"):
        return "batch"
    return None


def filename_warnings(filename, detected):
    """Name tricks: invoice.pdf.exe, right-to-left override, wrong extension."""
    out = []
    name = filename or ""
    if RTLO in name:
        out.append(finding("rtlo_filename", "high",
                           "File name contains a right-to-left override character, which makes the extension display backwards (e.g. 'gpj.exe' shown as 'exe.jpg').",
                           name.replace(RTLO, "<RTLO>")))
    parts = name.lower().split(".")
    if len(parts) >= 3:
        inner, outer = "." + parts[-2], "." + parts[-1]
        if inner in DOCUMENT_LIKE_EXTS and outer in EXECUTABLE_LIKE_EXTS:
            out.append(finding("double_extension", "high",
                               "File name uses a double extension to look like a document while being executable.", name))
    if detected["extension_mismatch"]:
        sev = "high" if detected["category"] in ("executable", "installer") else "medium"
        out.append(finding("extension_mismatch", sev,
                           "The file's contents are %s, but its name ends in %s." % (detected["description"], detected["extension"]),
                           {"expected": detected["expected_extensions"]}))
    return out


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3}

BENIGN_DOMAINS = (
    "schemas.openxmlformats.org", "schemas.microsoft.com", "www.w3.org", "w3.org",
    "purl.org", "ns.adobe.com", "schema.org", "microsoft.com/office",
    "openxmlformats.org", "www.xfa.org", "iptc.org", "ns.microsoft.com",
)

URL_RE = re.compile(r"\b(?:https?|ftp)://[^\s\"'<>\\)\]\}]{3,2048}", re.I)
IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
B64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")


def finding(fid, severity, description, evidence=None):
    f = {"id": fid, "severity": severity, "description": description}
    if evidence is not None:
        if isinstance(evidence, str) and len(evidence) > 300:
            evidence = evidence[:300] + "..."
        f["evidence"] = evidence
    return f


def entropy(data):
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return round(-sum(c / n * math.log2(c / n) for c in counts.values()), 3)


def ascii_strings(data, minimum=5, limit=20000):
    out = []
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % minimum, data[:MAX_SCAN_BYTES]):
        out.append(m.group().decode("ascii"))
        if len(out) >= limit:
            break
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}" % minimum, data[:MAX_SCAN_BYTES]):
        out.append(m.group().replace(b"\x00", b"").decode("ascii"))
        if len(out) >= limit * 2:
            break
    return out


def is_public_ipv4(ip):
    a, b = (int(x) for x in ip.split(".")[:2])
    return not (a in (0, 10, 127) or a >= 224 or (a == 169 and b == 254)
                or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168))


def extract_indicators(text):
    urls, domains, ips = [], [], []
    for m in URL_RE.finditer(text[:MAX_SCAN_BYTES]):
        url = m.group().rstrip(".,;:'\"")
        host = re.sub(r"^[a-z]+://", "", url, flags=re.I).split("/")[0].split(":")[0].lower()
        if any(host == d or host.endswith("." + d) or (d in url.lower()) for d in BENIGN_DOMAINS):
            continue
        if url not in urls and len(urls) < MAX_INDICATORS:
            urls.append(url)
        if host and not IPV4_RE.fullmatch(host) and host not in domains and len(domains) < MAX_INDICATORS:
            domains.append(host)
    for m in IPV4_RE.finditer(text[:MAX_SCAN_BYTES]):
        ip = m.group()
        # Version numbers like 1.0.0.1 look like IPs; only keep public ones.
        if is_public_ipv4(ip) and ip not in ips and len(ips) < MAX_INDICATORS:
            ips.append(ip)
    return {"urls": urls, "domains": domains, "ips": ips}


def merge_indicators(a, b):
    for key in ("urls", "domains", "ips"):
        for v in b.get(key, []):
            if v not in a[key] and len(a[key]) < MAX_INDICATORS:
                a[key].append(v)
    return a


def apply_rules(text, rules):
    """rules: [(id, severity, description, compiled_regex)] -> findings."""
    out = []
    for fid, sev, desc, rx in rules:
        m = rx.search(text)
        if m:
            out.append(finding(fid, sev, desc, m.group(0)))
    return out


def rule(fid, severity, description, pattern, flags=re.I):
    return (fid, severity, description, re.compile(pattern, flags))


def obfuscation_findings(text):
    out = []
    blobs = B64_BLOB_RE.findall(text[:MAX_SCAN_BYTES])
    if blobs:
        out.append(finding("base64_blob", "medium",
                           "Long base64-encoded blob(s), often a hidden payload or command.",
                           {"count": len(blobs), "longest": max(len(b) for b in blobs)}))
    lines = text.splitlines() or [""]
    longest = max(len(l) for l in lines[:100000])
    if longest > 5000:
        out.append(finding("very_long_line", "low", "A single line longer than 5,000 characters, typical of packed or obfuscated code.", {"length": longest}))
    charcodes = len(re.findall(r"(?:chr[w$]?\s*\(\s*\d+\s*\)|String\.fromCharCode|\[char\]\s*\d+)", text[:MAX_SCAN_BYTES], re.I))
    if charcodes >= 10:
        out.append(finding("char_code_building", "medium", "Builds strings one character code at a time, a common way to hide commands.", {"count": charcodes}))
    return out


# ---------------------------------------------------------------------------
# Rules: scripts and source code
# ---------------------------------------------------------------------------

COMMON_SCRIPT_RULES = [
    rule("download_and_execute", "high", "Downloads something from the internet and runs it.",
         r"(DownloadString|DownloadFile|Invoke-WebRequest|\biwr\b|\bwget\b|\bcurl\b|URLDownloadToFile|XMLHTTP|WinHttpRequest|bitsadmin\s+/transfer|certutil[^\n]{0,40}-urlcache)[^\n]{0,400}(IEX|Invoke-Expression|Start-Process|\.Run\b|\bexec\b|\|\s*(ba)?sh\b|ShellExecute|cmd(\.exe)?\s*/c)"
         r"|(\bIEX\b|Invoke-Expression)[^\n]{0,200}(DownloadString|Invoke-WebRequest|\biwr\b|Invoke-RestMethod|\birm\b)"),
    rule("defender_tampering", "high", "Tries to weaken Windows Defender.",
         r"(Set-MpPreference[^\n]{0,80}Disable|Add-MpPreference[^\n]{0,40}Exclusion|DisableRealtimeMonitoring|DisableAntiSpyware)"),
    rule("shadow_copy_deletion", "high", "Deletes backups/shadow copies (common in ransomware).",
         r"(vssadmin[^\n]{0,20}delete\s+shadows|wmic[^\n]{0,20}shadowcopy\s+delete|wbadmin[^\n]{0,20}delete|bcdedit[^\n]{0,40}recoveryenabled\s+no)"),
    rule("persistence_run_key", "high", "Writes a Windows Run key so it starts at every login.",
         r"(CurrentVersion\\Run(Once)?\b)"),
    rule("scheduled_task", "medium", "Creates a scheduled task.", r"(schtasks[^\n]{0,20}/create|Register-ScheduledTask|New-ScheduledTask)"),
    rule("lolbin_proxy_execution", "medium", "Uses a built-in Windows tool to run code indirectly.",
         r"\b(mshta|rundll32|regsvr32|wmic\s+process\s+call\s+create|installutil|msbuild|cmstp|forfiles)\b"),
    rule("account_creation", "medium", "Creates a user or adds one to Administrators.", r"(net\s+user\s+\S+\s+\S+\s+/add|net\s+localgroup\s+administrators)"),
    rule("credential_access", "high", "Looks for stored credentials or dumps LSASS memory.",
         r"(mimikatz|sekurlsa|lsass(\.exe)?[^\n]{0,60}(dump|minidump)|comsvcs[^\n]{0,30}MiniDump|Login Data|logins\.json)"),
]

POWERSHELL_RULES = [
    rule("ps_invoke_expression", "high", "Runs a string as code (Invoke-Expression / IEX).", r"(\bIEX\b|Invoke-Expression)"),
    rule("ps_encoded_command", "high", "Runs a base64-encoded PowerShell command.", r"-(e|en|enc|enco|encodedcommand)\s+[A-Za-z0-9+/=]{20,}"),
    rule("ps_base64_decode", "medium", "Decodes base64 data.", r"FromBase64String"),
    rule("ps_hidden_window", "medium", "Runs PowerShell with a hidden window.", r"-w(indowstyle)?\s+h(idden)?\b"),
    rule("ps_execution_policy_bypass", "medium", "Bypasses the PowerShell execution policy.", r"-ExecutionPolicy\s+Bypass|-ep\s+bypass"),
    rule("ps_reflective_load", "high", "Loads a .NET assembly straight from memory.", r"\[(System\.)?Reflection\.Assembly\]::Load"),
    rule("ps_amsi_bypass", "high", "Tries to disable AMSI (Windows' script scanning).", r"(AmsiUtils|amsiInitFailed|AmsiScanBuffer)"),
    rule("ps_web_client", "low", "Creates a web client.", r"Net\.WebClient|Invoke-RestMethod"),
]

VB_JS_RULES = [
    rule("wscript_shell", "medium", "Uses WScript.Shell to run commands.", r"WScript\.Shell"),
    rule("shell_application", "medium", "Uses Shell.Application to run programs.", r"Shell\.Application"),
    rule("activex_object", "low", "Creates ActiveX/COM objects.", r"(ActiveXObject|CreateObject)\s*\("),
    rule("adodb_stream", "medium", "Writes downloaded bytes to disk with ADODB.Stream.", r"ADODB\.Stream"),
    rule("http_request", "medium", "Makes HTTP requests.", r"(MSXML2\.(Server)?XMLHTTP|WinHttp\.WinHttpRequest|XMLHttpRequest)"),
    rule("eval_execution", "medium", "Runs a string as code.", r"\b(eval|Execute|ExecuteGlobal)\s*\("),
    rule("run_command", "medium", "Runs a command.", r"\.(Run|Exec|ShellExecute)\s*\("),
]

BATCH_RULES = [
    rule("certutil_decode", "high", "Uses certutil to download or decode a file.", r"certutil[^\n]{0,40}(-decode|-urlcache)"),
    rule("hidden_attribute", "low", "Hides files.", r"attrib\s+\+h"),
    rule("powershell_from_batch", "medium", "Launches PowerShell.", r"\bpowershell(\.exe)?\b"),
    rule("firewall_change", "medium", "Changes firewall rules.", r"netsh\s+(adv)?firewall"),
]

SHELL_RULES = [
    rule("pipe_to_shell", "high", "Downloads a script and pipes it straight into a shell.", r"(curl|wget)[^\n|]{0,300}\|\s*(sudo\s+)?(ba|z|da)?sh\b"),
    rule("reverse_shell", "high", "Opens a reverse shell.", r"(/dev/tcp/|nc\s+(-e|-c)|ncat[^\n]{0,40}-e|bash\s+-i\s*>&)"),
    rule("crontab_persistence", "medium", "Adds a cron job.", r"(crontab\s+-|/etc/cron)"),
    rule("chmod_exec", "low", "Makes a file executable.", r"chmod\s+(\+x|[0-7]*7[0-7]*)\s"),
    rule("ld_preload", "high", "Uses LD_PRELOAD to inject code.", r"(LD_PRELOAD|/etc/ld\.so\.preload)"),
    rule("ssh_key_persistence", "medium", "Adds an SSH authorized key.", r"authorized_keys"),
    rule("history_wipe", "medium", "Erases shell history.", r"(history\s+-c|unset\s+HISTFILE|>\s*~?/?\.bash_history)"),
]

PYTHON_RULES = [
    rule("py_exec", "medium", "Runs a string as code.", r"\b(exec|eval)\s*\("),
    rule("py_b64_exec", "high", "Runs base64/marshal/zlib-decoded code.", r"(exec|eval)\s*\([^\n]{0,80}(b64decode|marshal\.loads|zlib\.decompress)"),
    rule("py_marshal", "medium", "Loads marshalled bytecode.", r"marshal\.loads"),
    rule("py_subprocess", "low", "Runs system commands.", r"(subprocess\.|os\.system|os\.popen)"),
    rule("py_socket", "low", "Opens network sockets.", r"socket\.socket"),
    rule("py_ctypes_memory", "high", "Allocates executable memory through ctypes.", r"ctypes[^\n]{0,200}(VirtualAlloc|mmap|PROT_EXEC|RtlMoveMemory)"),
    rule("py_keylogger", "medium", "Captures keystrokes.", r"(pynput\.keyboard|keyboard\.on_press|GetAsyncKeyState)"),
]

SOURCE_RULES = [
    rule("memory_alloc_exec", "medium", "Allocates or changes memory to be executable.", r"\b(VirtualAlloc(Ex)?|VirtualProtect(Ex)?|NtAllocateVirtualMemory|mprotect)\b", 0),
    rule("remote_process_write", "high", "Writes into another process's memory.", r"\b(WriteProcessMemory|NtWriteVirtualMemory)\b", 0),
    rule("remote_thread", "high", "Starts a thread inside another process.", r"\b(CreateRemoteThread(Ex)?|NtCreateThreadEx|RtlCreateUserThread|QueueUserAPC)\b", 0),
    rule("process_hollowing", "high", "Uses process-hollowing APIs.", r"\b(NtUnmapViewOfSection|ZwUnmapViewOfSection|SetThreadContext)\b", 0),
    rule("open_other_process", "low", "Opens a handle to another process.", r"\bOpenProcess\b", 0),
    rule("keyboard_hook", "high", "Installs a keyboard hook or polls keys (keylogging).", r"(SetWindowsHookEx\w*\s*\(\s*WH_KEYBOARD(_LL)?|GetAsyncKeyState|GetKeyState\s*\()", 0),
    rule("registry_persistence", "high", "Writes a Run key for persistence.", r"CurrentVersion\\{1,2}Run", re.I),
    rule("registry_write", "low", "Writes to the registry.", r"\b(RegSetValueEx[AW]?|RegCreateKeyEx[AW]?)\b", 0),
    rule("download_file", "high", "Downloads a file from the internet.", r"\b(URLDownloadToFile[AW]?|InternetOpenUrl[AW]?|WinHttpOpen|HttpSendRequest[AW]?)\b", 0),
    rule("raw_sockets", "low", "Opens network sockets.", r"\b(WSAStartup|socket\s*\(\s*AF_INET|connect\s*\()", 0),
    rule("anti_debug", "medium", "Checks for a debugger (sandbox/analysis evasion).", r"\b(IsDebuggerPresent|CheckRemoteDebuggerPresent|NtQueryInformationProcess|ptrace\s*\(\s*PTRACE_TRACEME)\b", 0),
    rule("anti_vm", "medium", "Checks whether it is running in a VM or sandbox.", r"(VBoxService|vmtoolsd|VMware|SbieDll\.dll|\bwine_get_version\b)", re.I),
    rule("privilege_escalation", "medium", "Enables debug privilege / adjusts token privileges.", r"\b(AdjustTokenPrivileges|SeDebugPrivilege)\b", 0),
    rule("file_encryption", "medium", "Encrypts data with Windows crypto APIs.", r"\b(CryptEncrypt|BCryptEncrypt|CryptGenKey)\b", 0),
    rule("file_enumeration", "low", "Walks the file system.", r"\b(FindFirstFile[AW]?|FindNextFile[AW]?|opendir|readdir)\b", 0),
    rule("shell_spawn", "medium", "Starts a command shell.", r"(cmd\.exe|powershell(\.exe)?|/bin/sh|/bin/bash|WinExec\s*\(|ShellExecute(Ex)?[AW]?\s*\(|CreateProcess[AW]?\s*\()", re.I),
    rule("self_delete", "medium", "Deletes its own executable.", r"(MoveFileEx[AW]?[^\n]{0,80}MOVEFILE_DELAY_UNTIL_REBOOT|del\s+%0|/c\s+del\s)", re.I),
    rule("screen_capture", "low", "Captures the screen.", r"\b(BitBlt|GetDC\s*\(\s*(NULL|0|nullptr)\s*\))", 0),
    rule("dynamic_api_resolution", "medium", "Looks up Windows APIs at runtime (hides imports).", r"\b(GetProcAddress|LdrGetProcedureAddress)\b", 0),
]

SHELLCODE_ARRAY_RE = re.compile(r"(?:0x[0-9a-fA-F]{2}\s*,\s*){128,}")
SHELLCODE_STRING_RE = re.compile(r"(?:\\x[0-9a-fA-F]{2}){128,}")


def analyze_script(data, fmt):
    text = decode_text(data[:MAX_SCAN_BYTES])
    rules = list(COMMON_SCRIPT_RULES)
    if fmt == "powershell":
        rules += POWERSHELL_RULES
    elif fmt in ("vbscript", "jscript", "wsf", "hta"):
        rules += VB_JS_RULES + POWERSHELL_RULES[:2]
    elif fmt == "batch":
        rules += BATCH_RULES + POWERSHELL_RULES[:2]
    elif fmt == "shell":
        rules += SHELL_RULES
    elif fmt == "python":
        rules += PYTHON_RULES
    findings = apply_rules(text, rules) + obfuscation_findings(text)
    details = {"lines": text.count("\n") + 1, "entropy": entropy(data[:MAX_SCAN_BYTES])}
    return findings, extract_indicators(text), details


def analyze_source(data, fmt):
    text = decode_text(data[:MAX_SCAN_BYTES])
    findings = apply_rules(text, SOURCE_RULES)
    ids = {f["id"] for f in findings}

    shell_arrays = SHELLCODE_ARRAY_RE.findall(text) + SHELLCODE_STRING_RE.findall(text)
    if shell_arrays:
        longest = max(len(s) for s in shell_arrays)
        findings.append(finding("embedded_shellcode", "high",
                                "Contains a long hard-coded byte array, typical of embedded shellcode.",
                                {"arrays": len(shell_arrays), "longest_chars": longest}))
        ids.add("embedded_shellcode")

    # Combinations that mean more than their parts.
    if {"memory_alloc_exec", "remote_process_write", "remote_thread"} <= ids:
        findings.insert(0, finding("process_injection_pattern", "high",
                                   "Allocate + write + remote thread: the classic process-injection sequence."))
    elif "embedded_shellcode" in ids and "memory_alloc_exec" in ids:
        findings.insert(0, finding("shellcode_loader_pattern", "high",
                                   "Embedded byte array plus executable memory: a shellcode loader."))
    if "file_encryption" in ids and "file_enumeration" in ids:
        findings.insert(0, finding("ransomware_pattern", "high",
                                   "Walks the file system and encrypts data, the core loop of ransomware."))

    findings += obfuscation_findings(text)
    details = {
        "lines": text.count("\n") + 1,
        "includes": sorted(set(re.findall(r'#include\s*[<"]([^>"]+)[>"]', text)))[:50],
        "compiled": False,
        "note": "Source code is analyzed statically only; it is not compiled or run.",
    }
    return findings, extract_indicators(text), details


# ---------------------------------------------------------------------------
# Office documents
# ---------------------------------------------------------------------------

MACRO_KEYWORDS = [
    ("AutoOpen", "autoexec"), ("Auto_Open", "autoexec"), ("Document_Open", "autoexec"),
    ("Workbook_Open", "autoexec"), ("AutoExec", "autoexec"), ("Document_Close", "autoexec"),
    ("AutoClose", "autoexec"), ("Presentation_Open", "autoexec"),
    ("Shell", "suspicious"), ("WScript.Shell", "suspicious"), ("CreateObject", "suspicious"),
    ("URLDownloadToFile", "suspicious"), ("XMLHTTP", "suspicious"), ("ADODB.Stream", "suspicious"),
    ("powershell", "suspicious"), ("CallByName", "suspicious"), ("Environ", "suspicious"),
    ("Lib \"kernel32", "suspicious"), ("VirtualAlloc", "suspicious"), ("RtlMoveMemory", "suspicious"),
]


def oletools_macro_findings(data, filename):
    """Decompress and scan VBA source. Returns (findings, indicators, details) or None."""
    if not HAVE_OLETOOLS:
        return None
    try:
        vba = VBA_Parser(filename or "sample", data=data)
        try:
            if not vba.detect_vba_macros():
                return [], {"urls": [], "domains": [], "ips": []}, {"macros": False, "macro_source_scanned": True}
            autoexec, suspicious, iocs = [], [], []
            for kw_type, keyword, _desc in vba.analyze_macros():
                if kw_type == "AutoExec":
                    autoexec.append(keyword)
                elif kw_type == "Suspicious":
                    suspicious.append(keyword)
                elif kw_type == "IOC":
                    iocs.append(keyword)
            code = "\n".join(c for (_f, _s, _n, c) in vba.extract_macros() if c)[:MAX_SCAN_BYTES]
        finally:
            vba.close()
    except Exception as exc:  # malformed documents are common in malware
        return [finding("macro_parse_error", "low", "oletools could not parse the macros.", str(exc))], {"urls": [], "domains": [], "ips": []}, {"macros": None}

    findings = [finding("vba_macros", "medium", "Document contains VBA macros.")]
    if autoexec:
        findings.append(finding("macro_autoexec", "high" if suspicious else "medium",
                                "Macros run automatically when the document is opened or closed.", sorted(set(autoexec))[:20]))
    if suspicious:
        findings.append(finding("macro_suspicious_keywords", "high",
                                "Macros use keywords common in malicious documents.", sorted(set(suspicious))[:30]))
    indicators = extract_indicators(code + "\n" + "\n".join(iocs))
    return findings, indicators, {"macros": True, "macro_source_scanned": True, "macro_code_chars": len(code)}


def raw_macro_findings(blob):
    """Fallback without oletools: spot macros and readable keywords in raw bytes."""
    findings = []
    has_vba = (b"_VBA_PROJECT" in blob or b"Attribute VB_" in blob or "_VBA_PROJECT".encode("utf-16-le") in blob
               or b"V\x00B\x00A\x00\x00\x00" in blob)
    if not has_vba:
        return findings, False
    findings.append(finding("vba_macros", "medium", "Document contains VBA macros (source not decompressed; install oletools to read it)."))
    hits = {"autoexec": set(), "suspicious": set()}
    lower = blob.lower()
    for kw, kind in MACRO_KEYWORDS:
        if kw.lower().encode() in lower:
            hits[kind].add(kw)
    if hits["autoexec"]:
        findings.append(finding("macro_autoexec", "high" if hits["suspicious"] else "medium",
                                "Macros appear to run automatically on open/close.", sorted(hits["autoexec"])))
    if hits["suspicious"]:
        findings.append(finding("macro_suspicious_keywords", "medium",
                                "Readable suspicious keywords near the macro code (compressed source may hide more).", sorted(hits["suspicious"])))
    return findings, True


def analyze_ooxml(data, fmt, filename, depth, budget):
    findings, indicators = [], {"urls": [], "domains": [], "ips": []}
    details = {"parts": 0, "macros": False, "external_relationships": [], "embedded_files": []}
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception as exc:
        return [finding("corrupt_container", "medium", "The Office file's ZIP container is damaged.", str(exc))], indicators, details

    with zf:
        infos = zf.infolist()
        details["parts"] = len(infos)
        names = [i.filename for i in infos]

        vba_parts = [n for n in names if n.lower().endswith("vbaproject.bin")]
        if vba_parts:
            details["macros"] = True
            result = oletools_macro_findings(data, filename)
            if result is not None:
                f, ind, d = result
                findings += f
                merge_indicators(indicators, ind)
                details.update(d)
            # A vbaProject.bin part means macros, whatever a parser says:
            # malware ships deliberately malformed projects to confuse parsers.
            if not any(f["id"] == "vba_macros" for f in findings):
                blob = read_member(zf, zf.getinfo(vba_parts[0]), MAX_MEMBER_BYTES) or b""
                f, _ = raw_macro_findings(blob)
                findings += f or [finding("vba_macros", "medium", "Document contains a VBA project (macros).")]
                details["macros"] = True
        if (filename or "").lower().endswith((".docm", ".xlsm", ".pptm", ".dotm", ".xltm", ".potm", ".ppsm", ".xlam")) and not vba_parts:
            findings.append(finding("macro_extension_without_macros", "low", "Macro-enabled file type, but no macro project was found."))

        if any("activex" in n.lower() for n in names):
            findings.append(finding("activex_controls", "medium", "Document contains ActiveX controls, which can run code."))

        embedded = [n for n in names if "/embeddings/" in n.lower() or n.lower().endswith((".bin",)) and "oleobject" in n.lower()]
        if embedded:
            details["embedded_files"] = embedded[:50]
            findings.append(finding("embedded_objects", "medium", "Document has embedded objects (OLE packages or files).", embedded[:10]))

        # External relationships: remote templates (template injection), remote
        # OLE objects (e.g. CVE-2021-40444 / Follina-style), and plain links.
        ext_rels = []
        for name in names:
            if not name.endswith(".rels"):
                continue
            xml = (read_member(zf, zf.getinfo(name), 2 * 1024 * 1024) or b"").decode("utf-8", "replace")
            for rel in re.finditer(r"<Relationship\b[^>]*>", xml):
                tag = rel.group(0)
                if 'TargetMode="External"' not in tag:
                    continue
                target = re.search(r'Target="([^"]*)"', tag)
                rtype = re.search(r'Type="[^"]*/([^"/]+)"', tag)
                ext_rels.append({"part": name, "type": rtype.group(1) if rtype else None, "target": target.group(1) if target else None})
        details["external_relationships"] = ext_rels[:50]
        for rel in ext_rels:
            target = rel["target"] or ""
            rtype = (rel["type"] or "").lower()
            if rtype in ("attachedtemplate", "subdocument", "frame"):
                findings.append(finding("remote_template", "high",
                                        "Document loads a template or part from an external location when opened (template injection).", target))
            elif rtype == "oleobject":
                findings.append(finding("remote_ole_object", "high", "Document loads an OLE object from an external location.", target))
            elif target.lower().startswith(("mhtml:", "ms-msdt:", "search-ms:", "ms-officecmd:")):
                findings.append(finding("dangerous_uri_scheme", "high", "External link uses a URI scheme abused for code execution.", target))
            elif target.startswith("\\\\") or target.lower().startswith("file:"):
                findings.append(finding("unc_path_link", "medium", "External link to a network/file path (can leak Windows credentials).", target))
        merge_indicators(indicators, extract_indicators("\n".join(r["target"] or "" for r in ext_rels)))

        # DDE fields and body text, for Word / Excel parts.
        for name in names:
            low = name.lower()
            if not low.endswith(".xml") or not (low.startswith("word/") or low.startswith("xl/") or low.startswith("ppt/slides/")):
                continue
            xml = (read_member(zf, zf.getinfo(name), 8 * 1024 * 1024) or b"").decode("utf-8", "replace")
            if re.search(r"(DDEAUTO|\bDDE\b\s)", xml) or "ddeService" in xml:
                findings.append(finding("dde_field", "high", "Document uses a DDE field, which can launch programs when opened.", name))
            merge_indicators(indicators, extract_indicators(re.sub(r"<[^>]+>", " ", xml)))

        # Embedded files can themselves be anything: analyze them like archive members.
        if embedded and depth < MAX_ARCHIVE_DEPTH:
            members = []
            for info in infos:
                if info.filename in embedded[:20]:
                    blob = read_member(zf, info, MAX_MEMBER_BYTES)
                    if blob is not None and budget.take(len(blob)):
                        members.append(analyze_member(info.filename, blob, depth + 1, budget))
            details["embedded_analysis"] = members
            findings += lift_member_findings(members)
    return findings, indicators, details


def analyze_ole(data, fmt, filename):
    findings, indicators = [], {"urls": [], "domains": [], "ips": []}
    details = {"macros": False}
    result = oletools_macro_findings(data, filename)
    if result is not None:
        f, ind, d = result
        findings += f
        merge_indicators(indicators, ind)
        details.update(d)
    else:
        f, has = raw_macro_findings(data)
        findings += f
        details["macros"] = has
    if b"Equation.3" in data or "Equation.3".encode("utf-16-le") in data:
        findings.append(finding("equation_editor_object", "high",
                                "Contains an Equation Editor object, a common exploit vector (CVE-2017-11882)."))
    if "Ole10Native".encode("utf-16-le") in data:
        findings.append(finding("ole_package", "medium", "Contains an embedded OLE package (a file hidden inside the document)."))
    if fmt == "xls" and re.search(rb"(EXEC|CALL|REGISTER|URLDownloadToFile)\(", data):
        findings.append(finding("excel4_macro_hint", "medium", "Possible Excel 4.0 (XLM) macro functions."))
    merge_indicators(indicators, extract_indicators("\n".join(ascii_strings(data))))
    if fmt == "msi":
        findings += apply_rules("\n".join(ascii_strings(data)), COMMON_SCRIPT_RULES + POWERSHELL_RULES[:2])
        details["note"] = "MSI tables are not parsed; strings were scanned for suspicious commands."
    return findings, indicators, details


def analyze_rtf(data):
    findings = []
    text = data[:MAX_SCAN_BYTES].decode("latin-1")
    objects = len(re.findall(r"\\object\b", text))
    objdata = len(re.findall(r"\\objdata\b", text))
    if objects or objdata:
        findings.append(finding("rtf_embedded_objects", "medium", "RTF contains embedded OLE objects.", {"object": objects, "objdata": objdata}))
    if re.search(r"Equation\.3|4571756174696f6e2e33", text, re.I):  # also hex-encoded
        findings.append(finding("equation_editor_object", "high",
                                "Contains an Equation Editor object, a common exploit vector (CVE-2017-11882)."))
    if re.search(r"\\objupdate\b", text):
        findings.append(finding("rtf_objupdate", "medium", "Object is set to update automatically on open."))
    if text.count("{") > 20000 or re.search(r"\\bin\d{5,}", text):
        findings.append(finding("rtf_obfuscation", "low", "Unusual RTF structure often used to evade parsers."))
    return findings, extract_indicators(text), {"objects": objects}


def analyze_onenote(data):
    findings = []
    strings = "\n".join(ascii_strings(data))
    embedded_magic = {
        "pe": b"MZ", "hta": b"<hta:", "script": b"WScript", "batch": b"@echo off",
        "lnk": b"\x4c\x00\x00\x00\x01\x14\x02\x00",
    }
    found = [k for k, sig in embedded_magic.items() if data.find(sig, 1024) != -1]
    if found:
        findings.append(finding("onenote_embedded_payload", "high",
                                "OneNote file has an embedded executable/script, a delivery trick used since 2023.", found))
    findings += apply_rules(strings, COMMON_SCRIPT_RULES)
    return findings, extract_indicators(strings), {"embedded_types": found}


def analyze_csv(data):
    text = decode_text(data[:MAX_SCAN_BYTES])
    findings = []
    hits = re.findall(r"(?:^|[,;\t])\s*[\"']?[=+\-@][^,;\n]*(cmd|powershell|mshta|HYPERLINK|DDE|WEBSERVICE|IMPORTXML)[^,;\n]*", text, re.I)
    if hits:
        findings.append(finding("csv_formula_injection", "high", "Cells contain formulas that can run commands or call out when opened in Excel.", {"count": len(hits)}))
    return findings, extract_indicators(text), {"rows": text.count("\n") + 1}


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

PDF_KEYWORDS = ["/JS", "/JavaScript", "/OpenAction", "/AA", "/Launch", "/EmbeddedFile",
                "/URI", "/ObjStm", "/AcroForm", "/XFA", "/RichMedia", "/SubmitForm", "/GoToR", "/Encrypt"]


def normalize_pdf_names(raw):
    """Decode #xx escapes inside names (/J#61vaScript -> /JavaScript)."""
    escaped = [False]

    def fix(m):
        escaped[0] = True
        return bytes([int(m.group(1), 16)])
    out = re.sub(rb"#([0-9a-fA-F]{2})", fix, raw)
    return out, escaped[0]


def analyze_pdf(data):
    findings, details = [], {}
    raw = data[:MAX_FILE_BYTES]
    normalized, escaped = normalize_pdf_names(raw)

    # Flate streams can hide JavaScript and URLs; inflate a bounded number.
    inflated_parts, inflated_total = [], 0
    for m in re.finditer(rb"stream\r?\n", raw):
        if len(inflated_parts) >= MAX_PDF_STREAMS or inflated_total > MAX_TOTAL_EXTRACT:
            break
        start = m.end()
        end = raw.find(b"endstream", start)
        if end == -1:
            break
        try:
            d = zlib.decompressobj()
            chunk = d.decompress(raw[start:end], MAX_MEMBER_BYTES)
            if chunk:
                inflated_parts.append(chunk)
                inflated_total += len(chunk)
        except zlib.error:
            pass
    inflated = b"\n".join(inflated_parts)

    counts = {}
    for kw in PDF_KEYWORDS:
        pattern = re.escape(kw.encode()) + rb"(?![A-Za-z])"
        counts[kw] = len(re.findall(pattern, normalized)) + len(re.findall(pattern, inflated))
    details["keyword_counts"] = counts
    details["streams_inflated"] = len(inflated_parts)
    details["pages"] = len(re.findall(rb"/Type\s*/Page(?![a-z])", normalized + inflated))

    js = counts["/JS"] + counts["/JavaScript"]
    auto = counts["/OpenAction"] + counts["/AA"]
    if js and auto:
        findings.append(finding("pdf_auto_javascript", "high", "Runs JavaScript automatically when the PDF is opened."))
    elif js:
        findings.append(finding("pdf_javascript", "medium", "Contains JavaScript."))
    elif auto:
        findings.append(finding("pdf_auto_action", "low", "Has an automatic action on open (often benign, e.g. go to page)."))
    if counts["/Launch"]:
        findings.append(finding("pdf_launch_action", "high", "Has a /Launch action that can start external programs."))
    if counts["/EmbeddedFile"]:
        findings.append(finding("pdf_embedded_file", "medium", "Has a file embedded inside the PDF."))
    if counts["/XFA"] or counts["/RichMedia"]:
        findings.append(finding("pdf_rich_content", "medium", "Uses XFA forms or rich media (Flash/3D), historically exploited features."))
    if counts["/SubmitForm"] or counts["/GoToR"]:
        findings.append(finding("pdf_external_action", "low", "Can submit data or jump to another file/URL."))
    if escaped and any(counts[k] for k in ("/JS", "/JavaScript", "/OpenAction", "/Launch")):
        findings.append(finding("pdf_name_obfuscation", "high", "Hides PDF keywords with #-escapes (e.g. /J#61vaScript) to evade scanners."))
    if counts["/Encrypt"]:
        findings.append(finding("pdf_encrypted", "low", "PDF is encrypted; some content could not be inspected."))
    if counts["/ObjStm"] and js:
        findings.append(finding("pdf_object_streams", "low", "Uses object streams, which can hide objects from simple parsers."))

    js_bodies = re.findall(rb"(?s)/JS\s*\((.{0,20000}?)\)\s*(?:/|>>)", normalized + b"\n" + inflated)
    script_text = "\n".join(body.decode("latin-1") for body in js_bodies)
    if script_text:
        findings += apply_rules(script_text, VB_JS_RULES[4:6])
        details["javascript_preview"] = script_text[:500]
    if b"%%EOF" in raw:
        trailing = raw[raw.rfind(b"%%EOF") + 5:].strip()
        if len(trailing) > 1024:
            findings.append(finding("pdf_trailing_data", "medium", "Has a large amount of data after the end of the PDF (possible appended payload).", {"bytes": len(trailing)}))

    uri_text = " ".join(m.decode("latin-1") for m in re.findall(rb"/URI\s*\(([^)]{1,2048})\)", normalized + b"\n" + inflated))
    text_for_iocs = uri_text + "\n" + "\n".join(ascii_strings(inflated, 8, 5000))
    return findings, extract_indicators(text_for_iocs), details


# ---------------------------------------------------------------------------
# Archives and disk images
# ---------------------------------------------------------------------------

class Budget:
    """Total bytes we are willing to unpack from one upload (zip-bomb guard)."""

    def __init__(self, total):
        self.left = total
        self.members = 0

    def take(self, n):
        if n > self.left or self.members >= MAX_MEMBERS_ANALYZED:
            return False
        self.left -= n
        self.members += 1
        return True


def read_member(zf, info, limit):
    if info.file_size > limit:
        return None
    try:
        with zf.open(info) as fh:
            blob = fh.read(limit + 1)
        return blob if len(blob) <= limit else None
    except Exception:
        return None


RISKY_MEMBER_EXTS = {".exe", ".scr", ".com", ".pif", ".bat", ".cmd", ".js", ".jse", ".vbs", ".vbe",
                     ".wsf", ".hta", ".ps1", ".lnk", ".msi", ".jar", ".dll", ".cpl", ".iso", ".img", ".vhd", ".vhdx", ".one", ".chm"}


def member_name_findings(names):
    out = []
    risky = [n for n in names if ext_of(n) in RISKY_MEMBER_EXTS]
    if risky:
        out.append(finding("risky_members", "medium", "Archive contains executables, scripts, shortcuts or disk images.", risky[:20]))
    doubled = [n for n in names if filename_warnings(os.path.basename(n), {"extension_mismatch": False})]
    if doubled:
        out.append(finding("member_name_trick", "high", "An archived file uses a double extension or right-to-left override to disguise itself.", doubled[:10]))
    traversal = [n for n in names if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/")]
    if traversal:
        out.append(finding("path_traversal", "high", "Archive paths try to escape the extraction folder (../ or absolute paths).", traversal[:10]))
    return out


def lift_member_findings(members):
    """Surface the worst finding of each member at the archive level."""
    out = []
    for m in members:
        worst = max(m.get("findings", []), key=lambda f: SEVERITY_RANK[f["severity"]], default=None)
        if worst and SEVERITY_RANK[worst["severity"]] >= SEVERITY_RANK["medium"]:
            out.append(finding("member_" + worst["id"], worst["severity"], "%s: %s" % (m["name"], worst["description"]), worst.get("evidence")))
    return out


def analyze_member(name, blob, depth, budget):
    detected = detect_bytes(blob, os.path.basename(name))
    findings, indicators, details = analyze_detected(blob, detected, os.path.basename(name), depth, budget)
    findings = filename_warnings(os.path.basename(name), detected) + findings
    return {
        "name": name,
        "size": len(blob),
        "category": detected["category"],
        "format": detected["format"],
        "risk_level": risk_level(findings),
        "findings": findings[:15],
        "indicators": indicators,
        "details": {k: v for k, v in details.items() if k in ("members", "macros", "keyword_counts")},
    }


def analyze_zip(data, depth, budget):
    findings, indicators, details = [], {"urls": [], "domains": [], "ips": []}, {}
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except Exception as exc:
        return [finding("corrupt_archive", "medium", "ZIP archive could not be opened.", str(exc))], indicators, details
    with zf:
        infos = zf.infolist()
        names = [i.filename for i in infos]
        total_uncompressed = sum(i.file_size for i in infos)
        total_compressed = sum(i.compress_size for i in infos) or 1
        ratio = round(total_uncompressed / total_compressed, 1)
        encrypted = [i.filename for i in infos if i.flag_bits & 0x1]
        details.update({
            "member_count": len(infos),
            "uncompressed_bytes": total_uncompressed,
            "compression_ratio": ratio,
            "encrypted_members": len(encrypted),
            "listing": [{"name": i.filename, "size": i.file_size} for i in infos[:MAX_MEMBERS_LISTED]],
        })
        if ratio > 100 and total_uncompressed > 100 * 1024 * 1024:
            findings.append(finding("zip_bomb", "high", "Extreme compression ratio: this archive expands to an enormous size (zip bomb).",
                                    {"ratio": ratio, "uncompressed_bytes": total_uncompressed}))
        if encrypted:
            findings.append(finding("encrypted_archive", "medium",
                                    "Password-protected members could not be inspected (a common way to slip malware past scanners).", encrypted[:10]))
        findings += member_name_findings(names)

        members = []
        if depth < MAX_ARCHIVE_DEPTH:
            for info in infos:
                if info.is_dir() or info.flag_bits & 0x1:
                    continue
                if info.file_size > MAX_MEMBER_BYTES or not budget.take(info.file_size):
                    continue
                blob = read_member(zf, info, MAX_MEMBER_BYTES)
                if blob is not None:
                    members.append(analyze_member(info.filename, blob, depth + 1, budget))
        else:
            findings.append(finding("deeply_nested_archive", "medium", "Archives nested deeper than %d levels were not opened." % MAX_ARCHIVE_DEPTH))
        details["members"] = members
        findings += lift_member_findings(members)
        for m in members:
            merge_indicators(indicators, m["indicators"])
    return findings, indicators, details


def analyze_tar(data, depth, budget):
    findings, indicators, details = [], {"urls": [], "domains": [], "ips": []}, {}
    try:
        tf = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
    except Exception as exc:
        return [finding("corrupt_archive", "medium", "tar archive could not be opened.", str(exc))], indicators, details
    with tf:
        entries = tf.getmembers()[:5000]
        names = [e.name for e in entries]
        details["member_count"] = len(entries)
        details["listing"] = [{"name": e.name, "size": e.size} for e in entries[:MAX_MEMBERS_LISTED]]
        findings += member_name_findings(names)
        links = [e.name for e in entries if e.issym() or e.islnk()]
        if links:
            findings.append(finding("archive_links", "low", "Archive contains symbolic/hard links.", links[:10]))
        members = []
        if depth < MAX_ARCHIVE_DEPTH:
            for e in entries:
                if not e.isfile() or e.size > MAX_MEMBER_BYTES or not budget.take(e.size):
                    continue
                fh = tf.extractfile(e)
                if fh:
                    members.append(analyze_member(e.name, fh.read(MAX_MEMBER_BYTES), depth + 1, budget))
        details["members"] = members
        findings += lift_member_findings(members)
        for m in members:
            merge_indicators(indicators, m["indicators"])
    return findings, indicators, details


def analyze_gzip(data, filename, depth, budget):
    # .tar.gz / .tgz go through tarfile.
    try:
        tarfile.open(fileobj=io.BytesIO(data), mode="r:gz").close()
        return analyze_tar(data, depth, budget)
    except Exception:
        pass
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as gz:
            inner = gz.read(MAX_MEMBER_BYTES + 1)
    except Exception as exc:
        return [finding("corrupt_archive", "medium", "gzip data could not be decompressed.", str(exc))], {"urls": [], "domains": [], "ips": []}, {}
    if len(inner) > MAX_MEMBER_BYTES:
        return [finding("oversized_member", "low", "Decompressed content is larger than the analysis limit; it was not inspected.")], {"urls": [], "domains": [], "ips": []}, {}
    inner_name = filename[:-3] if (filename or "").lower().endswith(".gz") else "decompressed"
    member = analyze_member(inner_name, inner, depth + 1, budget) if budget.take(len(inner)) else None
    members = [member] if member else []
    return lift_member_findings(members), (member or {}).get("indicators", {"urls": [], "domains": [], "ips": []}), {"members": members}


def analyze_optional_archive(data, fmt, depth, budget):
    """7z / RAR / ISO / VHD / CAB: list contents when an optional parser is installed."""
    findings = [finding("container_format", "low",
                        "Archive or disk image format (%s). Disk images and uncommon archives are used to bypass Windows 'Mark of the Web' warnings." % fmt)]
    details = {"listed": False}
    names = []
    try:
        if fmt == "7z":
            import py7zr  # type: ignore
            with py7zr.SevenZipFile(io.BytesIO(data)) as z:
                if z.needs_password():
                    findings.append(finding("encrypted_archive", "medium", "Password-protected 7z archive; contents could not be inspected."))
                names = z.getnames()
        elif fmt == "rar":
            import rarfile  # type: ignore
            with rarfile.RarFile(io.BytesIO(data)) as r:
                if r.needs_password():
                    findings.append(finding("encrypted_archive", "medium", "Password-protected RAR archive; contents could not be inspected."))
                names = r.namelist()
        elif fmt == "iso":
            import pycdlib  # type: ignore
            iso = pycdlib.PyCdlib()
            iso.open_fp(io.BytesIO(data))
            try:
                facade = iso.get_joliet_facade() if iso.has_joliet() else iso.get_iso9660_facade()
                for dirname, _dirs, files in facade.walk("/"):
                    names += [os.path.join(dirname, f) for f in files][:MAX_MEMBERS_LISTED]
            finally:
                iso.close()
    except ImportError:
        details["note"] = "Install the optional parser for %s (see scripts/requirements-content.txt) to list its contents." % fmt
    except Exception as exc:
        findings.append(finding("corrupt_archive", "low", "Could not list the archive's contents.", str(exc)))
    if names:
        details.update({"listed": True, "member_count": len(names), "listing": [{"name": n} for n in names[:MAX_MEMBERS_LISTED]]})
        findings += member_name_findings(names)
    # Strings still reveal a lot (file names inside ISOs are stored in clear).
    strings = "\n".join(ascii_strings(data[:MAX_SCAN_BYTES]))
    if not names:
        embedded_names = sorted(set(re.findall(r"[\w\-. ]{1,80}\.(?:exe|dll|lnk|bat|cmd|js|vbs|hta|ps1|scr|msi)\b", strings, re.I)))[:20]
        if embedded_names:
            findings.append(finding("risky_members", "medium", "Archive appears to contain executables/scripts (from file names in its raw bytes).", embedded_names))
    return findings, extract_indicators(strings), details


# ---------------------------------------------------------------------------
# Shortcuts, web content, other binaries
# ---------------------------------------------------------------------------

LOLBINS = r"\b(cmd(\.exe)?|powershell(\.exe)?|pwsh|mshta(\.exe)?|wscript(\.exe)?|cscript(\.exe)?|rundll32(\.exe)?|regsvr32(\.exe)?|certutil(\.exe)?|bitsadmin|msiexec(\.exe)?|conhost(\.exe)?|forfiles|curl(\.exe)?)\b"


def analyze_lnk(data):
    strings = ascii_strings(data, 3)
    text = "\n".join(strings)
    findings = []
    lol = re.search(LOLBINS, text, re.I)
    if lol:
        findings.append(finding("lnk_runs_interpreter", "high", "Shortcut launches a command interpreter or system tool, the usual way malicious .lnk files run code.", lol.group(0)))
    findings += apply_rules(text, COMMON_SCRIPT_RULES + POWERSHELL_RULES[:3])
    if len(data) > 100 * 1024:
        findings.append(finding("lnk_oversized", "medium", "Shortcut is unusually large; extra data may be appended to it.", {"bytes": len(data)}))
    long_args = [s for s in strings if len(s) > 200]
    if long_args:
        findings.append(finding("lnk_long_arguments", "medium", "Shortcut has a very long argument string (often padded to hide the command).", long_args[0][:300]))
    return findings, extract_indicators(text), {"strings": strings[:40]}


def analyze_internet_shortcut(data):
    text = decode_text(data[:65536])
    findings = []
    url = re.search(r"^\s*URL\s*=\s*(.+)$", text, re.I | re.M)
    icon = re.search(r"^\s*IconFile\s*=\s*(.+)$", text, re.I | re.M)
    target = url.group(1).strip() if url else ""
    if target.lower().startswith("file:") or target.startswith("\\\\"):
        findings.append(finding("url_file_target", "high", "Shortcut points to a file or network share (can run remote programs or leak credentials).", target))
    elif re.match(r"^(search-ms|ms-msdt|ms-officecmd|mhtml):", target, re.I):
        findings.append(finding("dangerous_uri_scheme", "high", "Shortcut uses a URI scheme abused for code execution.", target))
    if icon and (icon.group(1).strip().startswith("\\\\") or "://" in icon.group(1)):
        findings.append(finding("remote_icon", "medium", "Icon is loaded from a remote location (can leak credentials when the folder is viewed).", icon.group(1).strip()))
    return findings, extract_indicators(text), {"target": target or None}


WEB_RULES = [
    rule("html_smuggling", "high", "Builds a file in the browser and downloads it (HTML smuggling).",
         r"(msSaveOrOpenBlob|new\s+Blob\s*\([\s\S]{0,400}(createObjectURL|\.download\s*=))"),
    rule("js_eval_decode", "medium", "Decodes and runs hidden script.", r"(eval\s*\(\s*(atob|unescape|decodeURIComponent)|document\.write\s*\(\s*unescape)"),
    rule("hidden_iframe", "medium", "Loads a hidden iframe.", r"<iframe[^>]{0,200}(width\s*=\s*[\"']?0|height\s*=\s*[\"']?0|display\s*:\s*none|visibility\s*:\s*hidden)"),
    rule("auto_redirect", "low", "Redirects the visitor automatically.", r"(http-equiv\s*=\s*[\"']?refresh|window\.location(\.href)?\s*=|location\.replace\s*\()"),
    rule("password_form", "medium", "Has a password field (possible credential-phishing page).", r"<input[^>]{0,200}type\s*=\s*[\"']?password"),
    rule("form_posts_offsite", "medium", "A form sends data to another site.", r"<form[^>]{0,300}action\s*=\s*[\"']?https?://"),
    rule("svg_script", "medium", "SVG image contains script.", r"<svg[\s\S]{0,20000}<script"),
    rule("data_uri_payload", "medium", "Embeds a large base64 data: URI.", r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]{1000,}"),
]


def analyze_web(data, fmt):
    if fmt == "chm":
        text = "\n".join(ascii_strings(data))
        findings = apply_rules(text, COMMON_SCRIPT_RULES + VB_JS_RULES[:2])
        if re.search(r"(ShortCut|Adb880a6-d8ff-11cf-9377-00aa003b7a11)", text, re.I):
            findings.append(finding("chm_shortcut_command", "high", "Help file uses an embedded command shortcut to run programs."))
        return findings, extract_indicators(text), {}
    text = decode_text(data[:MAX_SCAN_BYTES])
    findings = apply_rules(text, WEB_RULES) + obfuscation_findings(text)
    scripts = len(re.findall(r"<script\b", text, re.I))
    if fmt in ("html", "svg") and re.search(r"(WScript|ActiveXObject|<hta:)", text, re.I):
        findings.append(finding("windows_script_in_html", "high", "Page uses Windows scripting objects (behaves like an HTA)."))
    return findings, extract_indicators(text), {"script_tags": scripts}


def analyze_binary_generic(data, fmt):
    """ELF, Mach-O, Java, APK, unknown blobs: strings, entropy, indicators."""
    strings = ascii_strings(data)
    text = "\n".join(strings)
    findings = apply_rules(text, COMMON_SCRIPT_RULES + SHELL_RULES[:2] + SOURCE_RULES[1:4])
    ent = entropy(data[:MAX_SCAN_BYTES])
    if ent > 7.2 and len(data) > 4096:
        findings.append(finding("high_entropy", "low", "Data is nearly random, which usually means it is packed, compressed or encrypted.", {"entropy": ent}))
    if fmt == "elf" and b"UPX!" in data[:4096]:
        findings.append(finding("upx_packed", "medium", "Binary is packed with UPX."))
    details = {"entropy": ent, "string_count": len(strings)}
    if fmt in ("apk", "jar"):
        names = zip_names(data) or []
        details["entry_count"] = len(names)
        if fmt == "apk":
            details["dex_files"] = [n for n in names if n.endswith(".dex")][:10]
            if any(n.startswith("lib/") and n.endswith(".so") for n in names):
                details["native_libraries"] = True
    return findings, extract_indicators(text), details


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def analyze_detected(data, detected, filename, depth=0, budget=None):
    budget = budget or Budget(MAX_TOTAL_EXTRACT)
    category, fmt = detected["category"], detected["format"]
    if category == "office":
        if fmt in ("docx", "xlsx", "pptx"):
            return analyze_ooxml(data, fmt, filename, depth, budget)
        if fmt == "rtf":
            return analyze_rtf(data)
        if fmt == "onenote":
            return analyze_onenote(data)
        if fmt == "csv":
            return analyze_csv(data)
        return analyze_ole(data, fmt, filename)
    if category == "installer":
        return analyze_ole(data, fmt, filename)
    if category == "pdf":
        return analyze_pdf(data)
    if category == "script":
        if fmt == "hta":
            f1, i1, d1 = analyze_script(data, fmt)
            f2, i2, _ = analyze_web(data, "html")
            return f1 + [f for f in f2 if f["id"] not in {x["id"] for x in f1}], merge_indicators(i1, i2), d1
        return analyze_script(data, fmt)
    if category == "source":
        return analyze_source(data, fmt)
    if category == "archive":
        if fmt == "zip":
            return analyze_zip(data, depth, budget)
        if fmt == "tar":
            return analyze_tar(data, depth, budget)
        if fmt == "gzip":
            return analyze_gzip(data, filename, depth, budget)
        return analyze_optional_archive(data, fmt, depth, budget)
    if category == "shortcut":
        return analyze_lnk(data) if fmt == "lnk" else analyze_internet_shortcut(data)
    if category == "web":
        return analyze_web(data, fmt)
    if fmt in ("pe", "dos", "dos_com"):
        # Top-level PEs go to malware_detection/analyze.py; this path is only
        # reached for a PE found inside an archive.
        return analyze_binary_generic(data, fmt)
    if fmt == "text":
        text = decode_text(data[:MAX_SCAN_BYTES])
        return apply_rules(text, COMMON_SCRIPT_RULES) + obfuscation_findings(text), extract_indicators(text), {}
    return analyze_binary_generic(data, fmt)


def risk_level(findings):
    worst = max((SEVERITY_RANK[f["severity"]] for f in findings), default=0)
    return {0: "none", 1: "low", 2: "medium", 3: "high"}[worst]


def dedupe(findings):
    seen, out = set(), []
    for f in findings:
        key = (f["id"], json.dumps(f.get("evidence"), sort_keys=True, default=str))
        if key not in seen:
            seen.add(key)
            out.append(f)
    out.sort(key=lambda f: -SEVERITY_RANK[f["severity"]])
    return out[:MAX_FINDINGS]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_input():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError as exc:
        fail("bad_input", "stdin is not JSON: %s" % exc)
    path = payload.get("path")
    if not isinstance(path, str) or not path:
        fail("bad_input", 'Expected {"path": "...", "filename": "..."} on stdin.')
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            data = fh.read(MAX_FILE_BYTES)
    except OSError as exc:
        fail("read_failed", str(exc))
    filename = payload.get("filename") or os.path.basename(path)
    return data, filename, size


def fail(code, message):
    sys.stderr.write(json.dumps({"error": code, "message": message}))
    sys.exit(1)


def main(argv):
    if len(argv) != 2 or argv[1] not in ("detect", "analyze"):
        sys.stderr.write("usage: content_analyze.py detect|analyze  (JSON input on stdin)\n")
        sys.exit(2)
    data, filename, size = load_input()
    detected = detect_bytes(data, filename)
    detected["size"] = size
    detected["truncated"] = size > len(data)
    warnings = filename_warnings(filename, detected)

    if argv[1] == "detect":
        out = dict(detected, analyzer_version=ANALYZER_VERSION, filename=filename,
                   warnings=warnings, risk_level=risk_level(warnings))
    else:
        findings, indicators, details = analyze_detected(data, detected, filename)
        findings = dedupe(warnings + findings)
        out = {
            "analyzer_version": ANALYZER_VERSION,
            "filename": filename,
            "category": detected["category"],
            "format": detected["format"],
            "risk_level": risk_level(findings),
            "findings": findings,
            "indicators": indicators,
            "details": details,
            "tools": {"oletools": HAVE_OLETOOLS},
        }
    sys.stdout.write(json.dumps(out, default=str))


if __name__ == "__main__":
    main(sys.argv)
