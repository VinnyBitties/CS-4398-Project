"use strict";

// Run with: npm test  (after `npm install`)
// Uses the mock analyzer (scripts/mock_analyze.py) so these tests don't
// depend on the real malware_detection branch being merged in yet.

const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");

process.env.ANALYZER_SCRIPT_PATH = path.join(__dirname, "..", "scripts", "mock_analyze.py");
process.env.DATABASE_PATH = ":memory:";
process.env.UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), "sentinel-uploads-"));

const test = require("node:test");
const assert = require("node:assert/strict");
const request = require("supertest");
const { createApp } = require("../src/app");

const app = createApp();
const fixture = path.join(__dirname, "fixtures", "sample.bin");

// The EICAR antivirus test string, assembled at runtime. It is deliberately
// not stored in the repo (as a fixture or as one literal): antivirus on a
// teammate's machine would quarantine the file that contains it.
const EICAR = ["X5O!P%@AP[4\\PZX54(P^)7CC)7}$", "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"].join("");
const EICAR_SHA256 = "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f";

function stage(body, name) {
  return body.results.find((r) => r.stage === name);
}

async function pollUntilDone(id) {
  for (let i = 0; i < 100; i += 1) {
    const res = await request(app).get(`/api/samples/${id}`);
    if (res.body.status === "completed" || res.body.status === "failed") return res;
    await new Promise((r) => setTimeout(r, 20));
  }
  throw new Error(`sample ${id} never finished`);
}

test("GET /api/health returns ok", async () => {
  const res = await request(app).get("/api/health");
  assert.equal(res.status, 200);
  assert.equal(res.body.status, "ok");
});

test("POST /api/samples queues the scan and returns 202 before it has run", async () => {
  const res = await request(app).post("/api/samples").attach("file", fixture);

  assert.equal(res.status, 202);
  assert.equal(res.body.status, "queued");
  assert.equal(res.body.signature_match, null);
  assert.match(res.body.sha256, /^[0-9a-f]{64}$/);
  assert.equal(res.body.original_filename, "sample.bin");
  assert.equal(res.headers.location, `/api/samples/${res.body.sample_id}`);

  const done = await pollUntilDone(res.body.sample_id);
  assert.equal(done.body.status, "completed");
  assert.equal(done.body.sha256, res.body.sha256);
  assert.equal(done.body.signature_match, false);
  assert.equal(stage(done.body, "signature").status, "complete");
  assert.equal(stage(done.body, "static_analysis").status, "complete");
  assert.equal(stage(done.body, "static_analysis").report.schema_version, "1.2.0");
  assert.ok(done.body.job.started_at && done.body.job.finished_at);
});

test("POST /api/samples?wait=true returns the finished scan with 201", async () => {
  const res = await request(app).post("/api/samples?wait=true").attach("file", fixture);

  assert.equal(res.status, 201);
  assert.equal(res.body.status, "completed");
  assert.equal(res.body.signature_match, false);
  // The backend's own hash must agree with the analyzer's.
  assert.equal(stage(res.body, "static_analysis").report.sha256, res.body.sha256);
});

test("an uploaded EICAR test file is a signature match", async () => {
  const res = await request(app)
    .post("/api/samples?wait=true")
    .attach("file", Buffer.from(EICAR, "latin1"), "eicar.com");

  assert.equal(res.status, 201);
  assert.equal(res.body.sha256, EICAR_SHA256);
  assert.equal(res.body.signature_match, true);
  const sig = stage(res.body, "signature");
  assert.equal(sig.signature_match, true);
  assert.equal(sig.report.match.name, "EICAR-Test-File");
});

test("POST /api/samples without a file returns 400", async () => {
  const res = await request(app).post("/api/samples");
  assert.equal(res.status, 400);
  assert.equal(res.body.error, "missing_file");
});

test("a failing analyzer fails only its own stage, not the scan", async () => {
  const config = require("../src/config");
  const real = config.analyzerScriptPath;
  config.analyzerScriptPath = path.join(__dirname, "does-not-exist.py");
  try {
    const res = await request(app)
      .post("/api/samples?wait=true")
      .attach("file", Buffer.from(EICAR, "latin1"), "eicar.com");

    assert.equal(res.status, 201);
    assert.equal(res.body.status, "completed");
    assert.equal(res.body.signature_match, true);
    assert.equal(stage(res.body, "static_analysis").status, "failed");
    assert.equal(stage(res.body, "static_analysis").error.code, "LAUNCH_FAILED");
  } finally {
    config.analyzerScriptPath = real;
  }
});

test("POST /api/links flags a URL on a cataloged domain", async () => {
  const res = await request(app)
    .post("/api/links?wait=true")
    .send({ url: "http://Malware.WICAR.org/data/eicar.com#frag" });

  assert.equal(res.status, 201);
  assert.equal(res.body.submission_type, "link");
  assert.equal(res.body.submitted_url, "http://malware.wicar.org/data/eicar.com");
  assert.equal(res.body.signature_match, true);
  assert.equal(stage(res.body, "signature").report.checked, "url");
  // Links get no static analysis: there is no file to analyze.
  assert.equal(stage(res.body, "static_analysis"), undefined);
});

test("POST /api/links reports no match for an unknown URL", async () => {
  const res = await request(app).post("/api/links?wait=true").send({ url: "https://example.com/" });
  assert.equal(res.status, 201);
  assert.equal(res.body.signature_match, false);
});

test("POST /api/links rejects missing, malformed and non-http URLs", async () => {
  const cases = [
    [{}, "missing_url"],
    [{ url: "not a url" }, "invalid_url"],
    [{ url: "file:///etc/passwd" }, "invalid_url"],
    [{ url: "javascript:alert(1)" }, "invalid_url"],
    [{ url: `https://example.com/${"a".repeat(3000)}` }, "url_too_long"],
  ];
  for (const [body, code] of cases) {
    const res = await request(app).post("/api/links").send(body);
    assert.equal(res.status, 400, JSON.stringify(body).slice(0, 60));
    assert.equal(res.body.error, code);
  }
  const bad = await request(app).post("/api/links").set("Content-Type", "application/json").send("{oops");
  assert.equal(bad.status, 400);
  assert.equal(bad.body.error, "invalid_json");
});

test("GET /api/samples lists history newest first, with paging", async () => {
  const all = await request(app).get("/api/samples?limit=100");
  assert.equal(all.status, 200);
  assert.equal(all.body.samples.length, all.body.total);
  assert.ok(all.body.total >= 6);
  const ids = all.body.samples.map((s) => s.sample_id);
  assert.deepEqual(ids, [...ids].sort((a, b) => b - a));

  const page = await request(app).get("/api/samples?limit=2&offset=1");
  assert.deepEqual(page.body.samples.map((s) => s.sample_id), ids.slice(1, 3));
  assert.equal(page.body.total, all.body.total);
});

test("GET /api/samples/:id returns 404 for unknown and non-numeric ids", async () => {
  assert.equal((await request(app).get("/api/samples/999999")).status, 404);
  assert.equal((await request(app).get("/api/samples/abc")).status, 404);
});
