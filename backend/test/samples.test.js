"use strict";

// Run with: npm test  (after `npm install`)
// Uses the mock analyzer (scripts/mock_analyze.py) so these tests don't
// depend on the real malware_detection branch being merged in yet.

process.env.ANALYZER_SCRIPT_PATH = require("node:path").join(__dirname, "..", "scripts", "mock_analyze.py");
process.env.DATABASE_PATH = ":memory:";

const test = require("node:test");
const assert = require("node:assert/strict");
const request = require("supertest");
const path = require("node:path");
const { createApp } = require("../src/app");

test("GET /api/health returns ok", async () => {
  const app = createApp();
  const res = await request(app).get("/api/health");
  assert.equal(res.status, 200);
  assert.equal(res.body.status, "ok");
});

test("POST /api/samples analyzes an uploaded file and stores the result", async () => {
  const app = createApp();
  const fixture = path.join(__dirname, "fixtures", "sample.bin");

  const res = await request(app).post("/api/samples").attach("file", fixture);

  assert.equal(res.status, 201);
  assert.ok(res.body.sha256);
  assert.equal(typeof res.body.signature_match, "boolean");

  const fetched = await request(app).get(`/api/samples/${res.body.sample_id}`);
  assert.equal(fetched.status, 200);
  assert.equal(fetched.body.sha256, res.body.sha256);
});

test("POST /api/samples without a file returns 400", async () => {
  const app = createApp();
  const res = await request(app).post("/api/samples");
  assert.equal(res.status, 400);
});
