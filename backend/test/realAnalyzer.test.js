"use strict";

// Runs the backend against the team's REAL static analyzer
// (malware_detection/analyze.py) instead of the mock. Skipped automatically
// when pefile is not installed for python3, so `npm test` still passes on a
// machine that only has Node. To enable:
//   pip install -r ../malware_detection/requirements.txt

const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");
const { spawnSync } = require("node:child_process");

const repoRoot = path.join(__dirname, "..", "..");
const analyzerDir = path.join(repoRoot, "malware_detection");
const python = process.env.PYTHON_PATH || "python3";
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "sentinel-real-"));

process.env.ANALYZER_SCRIPT_PATH = path.join(analyzerDir, "analyze.py");
process.env.DATABASE_PATH = ":memory:";
process.env.UPLOAD_DIR = path.join(tmp, "uploads");

const test = require("node:test");
const assert = require("node:assert/strict");

// The analyzer's own test suite builds an inert PE (one data section, no
// executable code). Reuse that builder rather than committing a binary.
const fixturePath = path.join(tmp, "fixture.exe");
const built = spawnSync(
  python,
  [
    "-c",
    "import sys, pefile; sys.path.insert(0, sys.argv[1]); import test_analyze; open(sys.argv[2], 'wb').write(test_analyze.make_import_pe())",
    path.join(analyzerDir, "tests"),
    fixturePath,
  ],
  { cwd: analyzerDir, encoding: "utf8" }
);
const skip = built.status === 0 ? false : "real analyzer unavailable (malware_detection/ or pefile missing)";

const request = skip ? null : require("supertest");
const app = skip ? null : require("../src/app").createApp();

function staticStage(body) {
  return body.results.find((r) => r.stage === "static_analysis");
}

test("a real PE is analyzed by malware_detection/analyze.py", { skip }, async () => {
  const res = await request(app).post("/api/samples?wait=true").attach("file", fixturePath);

  assert.equal(res.status, 201);
  const result = staticStage(res.body);
  assert.equal(result.status, "complete", JSON.stringify(result.error));
  assert.equal(result.report.schema_version, "1.2.0");
  assert.equal(result.report.sha256, res.body.sha256);
  assert.ok(Array.isArray(result.report.sections) && result.report.sections.length > 0);
  assert.ok(result.report.imports.dlls.length > 0);
});

test("a file that is not a PE fails static_analysis with the analyzer's reason", { skip }, async () => {
  const res = await request(app)
    .post("/api/samples?wait=true")
    .attach("file", Buffer.from("inert text only"), "not-a-pe.txt");

  assert.equal(res.status, 201);
  assert.equal(res.body.status, "completed");
  assert.equal(res.body.signature_match, false);
  const result = staticStage(res.body);
  assert.equal(result.status, "failed");
  assert.equal(result.error.code, "NONZERO_EXIT");
  assert.equal(result.error.details.analyzer_error.error, "PEFormatError");
});
