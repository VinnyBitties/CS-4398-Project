"use strict";

process.env.DATABASE_PATH = ":memory:";

const test = require("node:test");
const assert = require("node:assert/strict");
const db = require("../src/db");
const store = require("../src/store/sampleStore");
const { createQueue } = require("../src/queue/jobQueue");

let n = 0;
function newJob() {
  n += 1;
  return store.createLinkSample({ sha256: String(n).padStart(64, "0"), url: `https://example.com/${n}` });
}
function jobStatus(jobId) {
  return store.stmts.getJob.get(jobId).status;
}
function deferred() {
  let resolve;
  const promise = new Promise((r) => (resolve = r));
  return { promise, resolve };
}

test("a job moves queued -> running -> completed", async () => {
  const gate = deferred();
  const queue = createQueue({ concurrency: 1, runner: () => gate.promise });
  const { jobId } = newJob();
  assert.equal(jobStatus(jobId), "queued");

  queue.enqueue();
  await new Promise((r) => setImmediate(r));
  assert.equal(jobStatus(jobId), "running");

  gate.resolve();
  assert.equal(await queue.waitFor(jobId, 1000), true);
  const job = store.stmts.getJob.get(jobId);
  assert.equal(job.status, "completed");
  assert.equal(job.attempts, 1);
  assert.ok(job.started_at && job.finished_at);
});

test("a runner that throws marks the job failed and the queue keeps going", async () => {
  const queue = createQueue({
    concurrency: 1,
    runner: async (sampleId) => {
      if (sampleId === bad.sampleId) throw new Error("boom");
    },
  });
  const bad = newJob();
  const good = newJob();
  queue.enqueue();

  await queue.waitFor(good.jobId, 1000);
  const failed = store.stmts.getJob.get(bad.jobId);
  assert.equal(failed.status, "failed");
  assert.equal(failed.error_message, "boom");
  assert.equal(jobStatus(good.jobId), "completed");
});

test("no more than `concurrency` jobs run at once, in submission order", async () => {
  let running = 0;
  let peak = 0;
  const order = [];
  const queue = createQueue({
    concurrency: 2,
    runner: async (sampleId) => {
      order.push(sampleId);
      running += 1;
      peak = Math.max(peak, running);
      await new Promise((r) => setTimeout(r, 15));
      running -= 1;
    },
  });
  const jobs = [newJob(), newJob(), newJob(), newJob(), newJob()];
  queue.enqueue();

  await Promise.all(jobs.map((j) => queue.waitFor(j.jobId, 2000)));
  assert.equal(peak, 2);
  assert.deepEqual(order, jobs.map((j) => j.sampleId));
  assert.ok(jobs.every((j) => jobStatus(j.jobId) === "completed"));
});

test("waitFor gives up with false when the job outlasts the timeout", async () => {
  const gate = deferred();
  const queue = createQueue({ concurrency: 1, runner: () => gate.promise });
  const { jobId } = newJob();
  queue.enqueue();

  assert.equal(await queue.waitFor(jobId, 20), false);
  assert.equal(jobStatus(jobId), "running");
  gate.resolve();
  assert.equal(await queue.waitFor(jobId, 1000), true);
});

test("start() re-queues jobs left running by a crash and finishes them", async () => {
  const { jobId } = newJob();
  db.prepare("UPDATE jobs SET status = 'running', attempts = 1 WHERE id = ?").run(jobId);

  const queue = createQueue({ concurrency: 1, runner: async () => {} });
  assert.deepEqual(queue.start(), { requeued: 1 });
  assert.equal(await queue.waitFor(jobId, 1000), true);

  const job = store.stmts.getJob.get(jobId);
  assert.equal(job.status, "completed");
  assert.equal(job.attempts, 2);
});
