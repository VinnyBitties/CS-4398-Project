# Defines shared ML feature names, thresholds, dataset paths, and label constants.

# Increment when feature order or extraction semantics change.
FEATURE_SCHEMA_VERSION = "sysmon-behavior-v1"

FEATURE_COLUMNS = [
    "num_processes_created",
    "num_files_written",
    "num_registry_keys_set",
    "num_network_connections",
    "num_dns_requests",
    "num_signatures_matched",
    "max_signature_severity",
    "has_persistence_signature",   # binary persistence-behavior flag
    "has_network_signature",
]

# Independent schema for backend file_type/content_analysis reports. Keep this
# separate from behavioral features: the two report sources have different
# meaning and may be present for different files.
STATIC_FEATURE_SCHEMA_VERSION = "content-analysis-static-v1"
STATIC_CATEGORY_VALUES = [
    "executable", "installer", "office", "pdf", "script", "source",
    "archive", "shortcut", "web", "unknown",
]
STATIC_FORMAT_VALUES = [
    "pe", "dos", "elf", "macho", "java_class", "jar", "apk", "msi",
    "doc", "xls", "ppt", "ole", "docx", "xlsx", "pptx", "rtf", "onenote",
    "csv", "pdf", "powershell", "batch", "vbscript", "jscript", "wsf",
    "hta", "python", "shell", "c", "cpp", "c_header", "csharp", "go",
    "rust", "java", "zip", "rar", "7z", "gzip", "tar", "cab", "iso",
    "vhd", "img", "lnk", "internet_shortcut", "html", "svg", "chm", "text",
    "unknown",
]
STATIC_FINDING_BUCKETS = 32
STATIC_FEATURE_COLUMNS = [
    *(f"category_{value}" for value in STATIC_CATEGORY_VALUES),
    *(f"format_{value}" for value in STATIC_FORMAT_VALUES),
    "content_risk_none", "content_risk_low", "content_risk_medium", "content_risk_high",
    "extension_mismatch", "file_truncated", "finding_count",
    "finding_severity_low", "finding_severity_medium", "finding_severity_high",
    *(f"finding_id_bucket_{index:02d}" for index in range(STATIC_FINDING_BUCKETS)),
]

DEFAULT_MALICIOUS_THRESHOLD = 0.5

PERSISTENCE_KEYWORDS = [
    "persistence",
    "autorun",
    "auto-run",
    "startup",
    "run key",
    "scheduled task",
    "task scheduler",
    "service install",
    "registry run",
]

NETWORK_KEYWORDS = [
    "network",
    "dns",
    "http",
    "https",
    "beacon",
    "c2",
    "command and control",
    "exfil",
    "exfiltration",
    "callback",
    "communication",
]

# --- Dataset / synthetic data paths -----------------------------------------
# Centralized here so synthetic_reports.py, build_dataset.py, and the eventual
# train_classifier.py / train_anomaly.py all agree on where things live.
# Swap SYNTHETIC_REPORTS_DIR for a real sandbox output directory once one exists
# -- nothing downstream needs to change.
 
from pathlib import Path
 
DATA_DIR = Path("data")
SYNTHETIC_REPORTS_DIR = DATA_DIR / "synthetic_reports"
MANIFEST_PATH = DATA_DIR / "manifest.csv"          # columns: report_path,label
FEATURES_CSV_PATH = DATA_DIR / "features.csv"      # columns: FEATURE_COLUMNS + label
 
# label convention used across the dataset: 1 = malicious, 0 = benign
LABEL_MALICIOUS = 1
LABEL_BENIGN = 0
