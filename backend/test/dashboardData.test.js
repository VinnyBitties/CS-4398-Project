"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { view } = require("../../website/dashboard/reports-data");
const { complete, raw } = require("./dashboard/fixtures");

test("normalized and raw sandbox reports have identical counts; summaries override abbreviated arrays", () => {
  const normalized = view(complete());
  const legacy = view(raw());
  assert.deepEqual(normalized.telemetry.counts.map(c => c.value), [3, 2, 2, 4, 12]);
  assert.deepEqual(legacy.telemetry.counts, normalized.telemetry.counts);
  assert.equal(normalized.risk, .72);
  assert.equal(normalized.threshold, .26);
  assert.equal(normalized.source, "Trained classifier");
  assert.equal(normalized.synthetic, true);
});
test("failed sandbox suppresses historical ML verdict and never supplies zero counts", () => {
  const sample = complete(); sample.results[1].status = "failed";
  sample.results[1].error = { message: "Connection refused" };
  const vm = view(sample);
  assert.equal(vm.risk, null);
  assert.equal(vm.anomaly, null);
  assert.ok(vm.telemetry.counts.every(c => c.value === null));
  assert.equal(vm.stages.find(s => s.key === "sandbox").error, "Connection refused");
  assert.equal(vm.stages.find(s => s.key === "static_ml").status, "not_run");
});
test("empty telemetry, malformed counts, and explicit collection errors are unavailable", () => {
  for (const mode of ["empty", "error", "malformed"]) {
    const sample = complete(), report = sample.results[1].report;
    if (mode === "error") report.parse_error = "No logs";
    else { for (const key of Object.keys(report.summary)) report.summary[key] = mode === "empty" ? 0 : "bad";
      for (const key of ["processes", "network", "dns", "file_drops", "registry"]) report[key] = []; }
    assert.equal(view(sample).risk, null);
    assert.equal(view(sample).telemetry.usable, false);
  }
});
test("valid zero risk stays zero; invalid or failed ML results stay unavailable", () => {
  for (const score of [null, undefined, -1, 1.1, NaN, "0.4"]) {
    const sample = complete(); sample.results[2].report.risk_score = score;
    assert.equal(view(sample).risk, null);
  }
  const sample = complete(); sample.results[2].report.risk_score = 0;
  assert.equal(view(sample).risk, 0);
  sample.results[2].status = "failed";
  assert.equal(view(sample).risk, null);
});
test("running and link-only scans show pending or not-run stages with no invented verdict", () => {
  for (const status of ["queued", "running", "completed", "failed"]) {
    const vm = view({ status, submission_type: "link", results: [] });
    assert.equal(vm.risk, null);
    assert.equal(vm.stages[3].status, ["queued", "running"].includes(status) ? "pending" : "not_run");
  }
});
test("heuristic verdict and anomaly score stay separate; signature finding is independent", () => {
  const sample = complete(), ml = sample.results[2].report;
  ml.prediction_source = "heuristic"; ml.risk_score = .2;
  const vm = view(sample);
  assert.equal(vm.source, "Heuristic"); assert.equal(vm.risk, .2);
  assert.equal(vm.anomaly, "anomaly"); assert.equal(vm.anomalyScore, -.17);
  assert.equal(vm.signatureMatch, true);
  delete ml.risk_score; delete ml.risk_level; delete ml.threshold;
  const anomalyOnly = view(sample);
  assert.equal(anomalyOnly.risk, null);
  assert.equal(anomalyOnly.source, "Unavailable");
  assert.equal(anomalyOnly.anomaly, "anomaly");
  assert.equal(anomalyOnly.anomalyScore, -.17);
});
test("missing fields and abbreviated event details preserve unavailable values and raw text", () => {
  const sample = complete(), report = sample.results[1].report;
  delete report.summary.dns_queries; delete report.dns;
  report.registry = [];
  assert.equal(view(sample).telemetry.counts[2].value, null);
  assert.equal(view(sample).telemetry.counts[4].value, 12);
  assert.deepEqual(view(sample).telemetry.counts[4].events, []);
  assert.match(view(sample).evidence[0], /<img/);
});
