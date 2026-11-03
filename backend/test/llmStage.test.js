"use strict";

// The llm stage: building the LLM/Threat Intelligence input from earlier
// reports, the Python bridge, and the stage inside the pipeline.
//
// Most tests use a small stand-in for llm-threat-intelligence/ written to a
// temp folder, with the same two functions Jaden's component exposes. The
// last test runs the real component when ../../llm-threat-intelligence
// exists (it lives on the llm-threat-intelligence branch), and is skipped
// otherwise.

const { resetDb } = require("./helpers/testDb");

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const store = require("../src/store/sampleStore");
const { runPipeline } = require("../src/pipeline/runPipeline");
const { signatureStage, createLlmStage } = require("../src/pipeline/stages");
const { buildLlmInput, isPublicIp, MAX_EVENTS_PER_LIST } = require("../src/adapters/llmInput");
const { runPythonJson } = require("../src/stages/pythonStage");

test.before(resetDb);

const python = process.env.PYTHON_PATH || "python3";
const bridgePath = path.join(__dirname, "..", "scripts", "llm_bridge.py");
const realLlmDir = path.join(__dirname, "..", "..", "llm-threat-intelligence");
const fixture = path.join(__dirname, "fixtures", "sample.bin");
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "sentinel-llm-"));

function makeLlmDir(name, analyzerSource) {
  const dir = path.join(tmp, name);
  fs.mkdirSync(dir);
  fs.writeFileSync(
    path.join(dir, "threat_intel.py"),
    "def analyze_indicator(indicator, indicator_type):\n" +
      "    return {'indicator': indicator, 'type': indicator_type, 'status': 'received'}\n"
  );
  fs.writeFileSync(path.join(dir, "llm_analyzer.py"), analyzerSource);
  return dir;
}

const standInDir = makeLlmDir(
  "stand-in",
  "from threat_intel import analyze_indicator\n" +
    "def build_security_prompt(report):\n" +
    "    return '\\nFilename: ' + str(report.get('filename')) + '\\nDynamic: ' + str(report.get('dynamic_analysis')) + '\\n'\n"
);
const brokenDir = makeLlmDir(
  "broken",
  "def build_security_prompt(report):\n    raise ValueError('cannot read this report')\n"
);

function sandboxReport(telemetry = {}) {
  return {
    job_id: "job-1",
    summary: { process_count: 1, network_count: 3, dns_count: 2 },
    telemetry: {
      processes: [{ image: "a.exe" }],
      network: [
        { dest_ip: "203.0.113.5", dest_port: "443" },
        { dest_ip: "192.168.1.10", dest_port: "445" },
        { dest_ip: "203.0.113.5", dest_port: "80" },
      ],
      dns: [{ query: "c2.example.com" }, { query: "C2.example.com." }],
      ...telemetry,
    },
  };
}

// ---- input ----------------------------------------------------------------

test("input: a file's hash and the public domains/IPs it contacted become indicators", () => {
  const sample = { submission_type: "file", sha256: "ab".repeat(32), original_filename: "a.exe" };
  const { report, indicators } = buildLlmInput(sample, {
    signature: { matched: false },
    static_analysis: { schema_version: "1.2.0" },
    sandbox: sandboxReport(),
    behavioral_ml: { malicious: true, risk_score: 0.7 },
  });

  assert.deepEqual(indicators, [
    { indicator: "ab".repeat(32), type: "hash" },
    { indicator: "c2.example.com", type: "domain" },
    { indicator: "203.0.113.5", type: "ip" },
  ]);
  assert.equal(report.filename, "a.exe");
  assert.equal(report.sha256, "ab".repeat(32));
  assert.deepEqual(report.static_analysis, { schema_version: "1.2.0" });
  assert.deepEqual(report.ml_analysis, { behavioral: { malicious: true, risk_score: 0.7 } });
  assert.equal(report.dynamic_analysis.summary.dns_count, 2);
});

test("input: a link gives its URL and host; its sha256 is not a file hash", () => {
  const sample = { submission_type: "link", sha256: "cd".repeat(32), submitted_url: "http://malware.wicar.org/data/" };
  const { report, indicators } = buildLlmInput(sample, { signature: { matched: true } });
  assert.deepEqual(indicators, [
    { indicator: "http://malware.wicar.org/data/", type: "url" },
    { indicator: "malware.wicar.org", type: "domain" },
  ]);
  assert.equal(report.sha256, null);
  assert.equal(report.filename, "http://malware.wicar.org/data/");
  assert.deepEqual(report.static_analysis, {});
  assert.deepEqual(report.dynamic_analysis, {});
});

test("input: long telemetry lists are cut down and the cut is recorded", () => {
  const processes = Array.from({ length: MAX_EVENTS_PER_LIST + 7 }, (_, i) => ({ pid: String(i) }));
  const { report } = buildLlmInput({ submission_type: "file", sha256: "ef".repeat(32) }, {
    sandbox: sandboxReport({ processes }),
  });
  assert.equal(report.dynamic_analysis.telemetry.processes.length, MAX_EVENTS_PER_LIST);
  assert.deepEqual(report.dynamic_analysis.telemetry.omitted_events, { processes: 7 });
});

test("input: private, loopback and link-local addresses are not looked up", () => {
  for (const ip of ["10.0.0.1", "127.0.0.1", "172.20.1.1", "192.168.0.5", "169.254.1.1", "0.0.0.0", "::1", "fe80::1", "fd00::1"]) {
    assert.equal(isPublicIp(ip), false, ip);
  }
  for (const ip of ["8.8.8.8", "203.0.113.5", "172.32.0.1", "2001:4860:4860::8888"]) {
    assert.equal(isPublicIp(ip), true, ip);
  }
  assert.equal(isPublicIp("not-an-ip"), false);
});

// ---- bridge ---------------------------------------------------------------

test("bridge: returns threat intel per indicator and the prompt", async () => {
  const out = await runPythonJson({
    pythonPath: python,
    scriptPath: bridgePath,
    args: [standInDir],
    input: { report: { filename: "a.exe" }, indicators: [{ indicator: "x.example", type: "domain" }] },
  });
  assert.deepEqual(out.threat_intel, [{ indicator: "x.example", type: "domain", status: "received" }]);
  assert.match(out.prompt, /^Filename: a\.exe/);
  assert.equal(out.explanation, null);
  assert.equal(out.explanation_status, "not_generated");
});

test("bridge: a missing component folder is a clear error", async () => {
  await assert.rejects(
    runPythonJson({ pythonPath: python, scriptPath: bridgePath, args: [path.join(tmp, "nope")], input: {} }),
    (err) => {
      assert.equal(err.code, "NONZERO_EXIT");
      assert.equal(err.details.script_error.error, "LlmComponentNotFound");
      return true;
    }
  );
});

test("bridge: an exception in the component is reported, not swallowed", async () => {
  await assert.rejects(
    runPythonJson({ pythonPath: python, scriptPath: bridgePath, args: [brokenDir], input: { report: {} } }),
    (err) => {
      assert.equal(err.details.script_error.error, "ValueError");
      assert.match(err.message, /cannot read this report/);
      return true;
    }
  );
});

// ---- pipeline -------------------------------------------------------------

let n = 0;
async function newFileSample() {
  n += 1;
  const { sampleId } = await store.createFileSample({
    sha256: String(n).padStart(64, "b"),
    originalFilename: "a.exe",
    fileSize: 10,
    storedPath: fixture,
  });
  return sampleId;
}

async function resultsByStage(sampleId) {
  return Object.fromEntries((await store.getSampleView(sampleId)).results.map((r) => [r.stage, r]));
}

function llmStage(llmDir) {
  return createLlmStage({ pythonPath: python, bridgePath, llmDir, timeoutMs: 10000 });
}

test("pipeline: llm runs last and sees the earlier stages' reports", async () => {
  const fakeSandbox = { name: "sandbox", appliesTo: ["file"], run: async () => ({ report: sandboxReport() }) };
  const sampleId = await newFileSample();
  await runPipeline(sampleId, [signatureStage, fakeSandbox, llmStage(standInDir)]);

  const r = await resultsByStage(sampleId);
  assert.equal(r.llm.status, "complete");
  assert.deepEqual(r.llm.report.stages_used, ["signature", "sandbox"]);
  assert.deepEqual(
    r.llm.report.threat_intel.map((t) => t.type),
    ["hash", "domain", "ip"]
  );
  assert.equal(r.llm.report.indicators.length, 3);
  assert.match(r.llm.report.prompt, /c2\.example\.com/);
});

test("pipeline: links go through the llm stage too", async () => {
  const url = "http://malware.wicar.org/llm-test";
  const { sampleId } = await store.createLinkSample({ sha256: "c".repeat(64), url });
  await runPipeline(sampleId, [signatureStage, llmStage(standInDir)]);
  const r = await resultsByStage(sampleId);
  assert.equal(r.llm.status, "complete");
  assert.equal(r.llm.report.threat_intel[0].indicator, url);
});

test("pipeline: a broken llm component fails only the llm stage", async () => {
  const sampleId = await newFileSample();
  await runPipeline(sampleId, [signatureStage, llmStage(path.join(tmp, "missing"))]);
  const r = await resultsByStage(sampleId);
  assert.equal(r.signature.status, "complete");
  assert.equal(r.llm.status, "failed");
  assert.equal(r.llm.error.code, "NONZERO_EXIT");
});

// ---- the real component ---------------------------------------------------

test(
  "real component: Jaden's llm_analyzer builds the prompt from our input",
  { skip: fs.existsSync(path.join(realLlmDir, "llm_analyzer.py")) ? false : "llm-threat-intelligence/ not present" },
  async () => {
    const { report, indicators } = buildLlmInput(
      { submission_type: "file", sha256: "ab".repeat(32), original_filename: "a.exe" },
      { static_analysis: { schema_version: "1.2.0" }, sandbox: sandboxReport(), behavioral_ml: { risk_level: "high" } }
    );
    const out = await runPythonJson({
      pythonPath: python,
      scriptPath: bridgePath,
      args: [realLlmDir],
      input: { report, indicators },
    });
    assert.equal(out.threat_intel.length, indicators.length);
    assert.ok(out.threat_intel.every((t) => t.status === "received"));
    assert.match(out.prompt, /a\.exe/);
    assert.match(out.prompt, /c2\.example\.com/);
    assert.match(out.prompt, /risk_level/);
  }
);
