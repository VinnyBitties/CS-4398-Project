"use strict";

// The sandbox and behavioral ML stages, against mock HTTP servers that
// return exactly what dynamic_telemetry/api.py and ML/predict.py --serve
// return. No VM, no Python, no network.

const { resetDb } = require("./helpers/testDb");

const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const path = require("node:path");
const store = require("../src/store/sampleStore");
const { runPipeline } = require("../src/pipeline/runPipeline");
const { createSandboxStage, createBehavioralMlStage } = require("../src/pipeline/stages");
const { detonate } = require("../src/stages/sandboxClient");
const { toMlReport, SandboxReportError } = require("../src/adapters/sandboxToMl");

test.before(resetDb);

const fixture = path.join(__dirname, "fixtures", "sample.bin");

// A /detonate response in the shape api.py builds it.
function sandboxResponse(overrides = {}) {
  const telemetry = {
    processes: [{ image: "C:\\Tools\\a.exe", command_line: "a.exe", parent: "cmd.exe", pid: "4242" }],
    network: [{ image: "C:\\Tools\\a.exe", dest_ip: "203.0.113.5", dest_port: "443" }],
    dns: [
      { query: "c2.example.com", results: "203.0.113.5" },
      { query: "cdn.example.com", results: "198.51.100.7" },
    ],
    file_drops: [{ target_filename: "C:\\Users\\Public\\x.dll", image: "C:\\Tools\\a.exe" }],
    registry: [
      { target_object: "HKCU\\Software\\Run\\x", details: "x.dll" },
      { target_object: "HKCU\\Software\\y", details: "1" },
    ],
    ...overrides.telemetry,
  };
  return {
    job_id: "6f1c0e1a-0000-4000-8000-000000000001",
    filename: "a.exe",
    timeout_seconds: 15,
    summary: {
      process_count: telemetry.processes.length,
      network_count: telemetry.network.length,
      dns_count: telemetry.dns.length,
      file_drops_count: telemetry.file_drops.length,
      registry_count: telemetry.registry.length,
    },
    telemetry,
  };
}

function listen(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => resolve({ server, url: `http://127.0.0.1:${server.address().port}` }));
  });
}

function readBody(req) {
  return new Promise((resolve) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
  });
}

function json(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

// ---- adapter -------------------------------------------------------------

test("adapter maps the sandbox's field names to the ML parser's", () => {
  const { report, notes } = toMlReport(sandboxResponse());
  assert.deepEqual(report.summary, {
    processes_created: 1,
    network_connections: 1,
    dns_queries: 2,
    files_created: 1,
    registry_modifications: 2,
    remote_threads_injected: 0,
  });
  assert.equal(report.original_filename, "a.exe");
  assert.equal(report.dns[0].query_name, "c2.example.com");
  assert.equal(report.dns[0].query, undefined);
  assert.equal(report.registry.length, 2);
  assert.deepEqual(report.remote_threads, []);
  assert.deepEqual(report.signatures, []);
  assert.match(notes[0], /remote_threads_injected/);
});

test("adapter uses remote_threads when the sandbox starts sending them", () => {
  const { report, notes } = toMlReport(sandboxResponse({ telemetry: { remote_threads: [{ target: "lsass.exe" }] } }));
  assert.equal(report.summary.remote_threads_injected, 1);
  assert.deepEqual(notes, []);
});

test("adapter passes a report already in the ML shape through untouched", () => {
  const mlShaped = {
    summary: { processes_created: 3, network_connections: 1, dns_queries: 2, files_created: 4,
      registry_modifications: 12, remote_threads_injected: 0 },
    processes: [], network: [], dns: [], file_drops: [], registry: [], remote_threads: [],
  };
  const { report, notes } = toMlReport(mlShaped);
  assert.equal(report, mlShaped);
  assert.deepEqual(notes, []);
});

test("adapter refuses a run whose Sysmon log could not be parsed", () => {
  const broken = sandboxResponse({
    telemetry: { processes: [], network: [], dns: [], file_drops: [], registry: [], parse_error: "No such file" },
  });
  assert.throws(() => toMlReport(broken), (err) => {
    assert.ok(err instanceof SandboxReportError);
    assert.equal(err.code, "TELEMETRY_PARSE_ERROR");
    assert.equal(err.details.parse_error, "No such file");
    return true;
  });
});

test("adapter refuses a response with no telemetry", () => {
  assert.throws(() => toMlReport({ job_id: "x", summary: {} }), { code: "BAD_SANDBOX_REPORT" });
  assert.throws(() => toMlReport(sandboxResponse({ telemetry: { dns: "nope" } })), { code: "BAD_SANDBOX_REPORT" });
});

// ---- sandbox client -------------------------------------------------------

test("detonate uploads the file and timeout as multipart and returns the JSON", async () => {
  let seen;
  const { server, url } = await listen(async (req, res) => {
    const body = await readBody(req);
    seen = { method: req.method, path: req.url, type: req.headers["content-type"], body: body.toString("latin1") };
    json(res, 200, sandboxResponse());
  });
  try {
    const out = await detonate(`${url}/detonate`, fixture, { filename: "a.exe", detonationSeconds: 7 });
    assert.equal(out.job_id, sandboxResponse().job_id);
    assert.equal(seen.method, "POST");
    assert.equal(seen.path, "/detonate");
    assert.match(seen.type, /^multipart\/form-data; boundary=/);
    assert.match(seen.body, /name="file"; filename="a.exe"/);
    assert.match(seen.body, /name="timeout"\r\n\r\n7\r\n/);
  } finally {
    server.close();
  }
});

test("detonate reports a sandbox 500 as BAD_STATUS with FastAPI's detail", async () => {
  const { server, url } = await listen((req, res) => json(res, 500, { detail: "virsh: domain not running" }));
  try {
    await assert.rejects(() => detonate(`${url}/detonate`, fixture), (err) => {
      assert.equal(err.code, "BAD_STATUS");
      assert.equal(err.details.statusCode, 500);
      assert.match(err.details.bodyPreview, /domain not running/);
      return true;
    });
  } finally {
    server.close();
  }
});

test("detonate reports an unreachable sandbox as CONNECTION_FAILED", async () => {
  await assert.rejects(() => detonate("http://127.0.0.1:1/detonate", fixture), { code: "CONNECTION_FAILED" });
});

test("detonate reports a slow sandbox as TIMEOUT", async () => {
  const { server, url } = await listen(() => {}); // never answers
  try {
    await assert.rejects(() => detonate(`${url}/detonate`, fixture, { timeoutMs: 100 }), { code: "TIMEOUT" });
  } finally {
    server.closeAllConnections();
    server.close();
  }
});

test("detonations never overlap, because the sandbox has one VM", async () => {
  let active = 0;
  let maxActive = 0;
  const { server, url } = await listen(async (req, res) => {
    await readBody(req);
    active += 1;
    maxActive = Math.max(maxActive, active);
    await new Promise((r) => setTimeout(r, 30));
    active -= 1;
    json(res, 200, sandboxResponse());
  });
  try {
    await Promise.all([1, 2, 3].map(() => detonate(`${url}/detonate`, fixture)));
    assert.equal(maxActive, 1);
  } finally {
    server.close();
  }
});

// ---- pipeline -------------------------------------------------------------

let n = 0;
async function newFileSample() {
  n += 1;
  const { sampleId } = await store.createFileSample({
    sha256: String(n).padStart(64, "a"),
    originalFilename: "a.exe",
    fileSize: 10,
    storedPath: fixture,
  });
  return sampleId;
}

async function resultsByStage(sampleId) {
  return Object.fromEntries((await store.getSampleView(sampleId)).results.map((r) => [r.stage, r]));
}

test("pipeline: sandbox telemetry is translated and scored by the ML service", async () => {
  let mlRequest;
  const sandbox = await listen(async (req, res) => {
    await readBody(req);
    json(res, 200, sandboxResponse());
  });
  const ml = await listen(async (req, res) => {
    mlRequest = JSON.parse((await readBody(req)).toString("utf8"));
    json(res, 200, { malicious: true, risk_score: 0.71, risk_level: "high", features: {}, evidence: ["2 DNS request(s) observed"] });
  });
  try {
    const sampleId = await newFileSample();
    await runPipeline(sampleId, [
      createSandboxStage({ url: `${sandbox.url}/detonate`, detonationSeconds: 15, timeoutMs: 5000 }),
      createBehavioralMlStage({ url: `${ml.url}/`, timeoutMs: 5000 }),
    ]);

    const r = await resultsByStage(sampleId);
    assert.equal(r.sandbox.status, "complete");
    assert.equal(r.sandbox.report.job_id, sandboxResponse().job_id);
    assert.equal(r.behavioral_ml.status, "complete");
    assert.equal(r.behavioral_ml.report.malicious, true);
    assert.equal(r.behavioral_ml.report.risk_score, 0.71);
    assert.equal(r.behavioral_ml.report.input_summary.dns_queries, 2);
    assert.match(r.behavioral_ml.report.adapter_notes[0], /remote_threads_injected/);
    // What actually went over the wire is the ML shape.
    assert.equal(mlRequest.summary.processes_created, 1);
    assert.equal(mlRequest.dns[0].query_name, "c2.example.com");
  } finally {
    sandbox.server.close();
    ml.server.close();
  }
});

test("pipeline: an empty Sysmon log fails the sandbox stage and is never scored", async () => {
  let mlCalled = false;
  const sandbox = await listen(async (req, res) => {
    await readBody(req);
    json(res, 200, sandboxResponse({
      telemetry: { processes: [], network: [], dns: [], file_drops: [], registry: [], parse_error: "[Errno 2] No such file" },
    }));
  });
  const ml = await listen((req, res) => {
    mlCalled = true;
    json(res, 200, {});
  });
  try {
    const sampleId = await newFileSample();
    await runPipeline(sampleId, [
      createSandboxStage({ url: `${sandbox.url}/detonate`, timeoutMs: 5000 }),
      createBehavioralMlStage({ url: `${ml.url}/`, timeoutMs: 5000 }),
    ]);

    const r = await resultsByStage(sampleId);
    assert.equal(r.sandbox.status, "failed");
    assert.equal(r.sandbox.error.code, "TELEMETRY_PARSE_ERROR");
    assert.equal(r.behavioral_ml.status, "failed");
    assert.equal(r.behavioral_ml.error.code, "NO_SANDBOX_REPORT");
    assert.equal(mlCalled, false);
  } finally {
    sandbox.server.close();
    ml.server.close();
  }
});

test("pipeline: the ML service being down fails only behavioral_ml", async () => {
  const sandbox = await listen(async (req, res) => {
    await readBody(req);
    json(res, 200, sandboxResponse());
  });
  try {
    const sampleId = await newFileSample();
    await runPipeline(sampleId, [
      createSandboxStage({ url: `${sandbox.url}/detonate`, timeoutMs: 5000 }),
      createBehavioralMlStage({ url: "http://127.0.0.1:1/", timeoutMs: 1000 }),
    ]);
    const r = await resultsByStage(sampleId);
    assert.equal(r.sandbox.status, "complete");
    assert.equal(r.behavioral_ml.status, "failed");
    assert.equal(r.behavioral_ml.error.code, "CONNECTION_FAILED");
  } finally {
    sandbox.server.close();
  }
});

test("the sandbox stages skip link submissions", () => {
  assert.deepEqual(createSandboxStage({ url: "http://x/detonate" }).appliesTo, ["file"]);
  assert.deepEqual(createBehavioralMlStage({ url: "http://x/" }).appliesTo, ["file"]);
});
