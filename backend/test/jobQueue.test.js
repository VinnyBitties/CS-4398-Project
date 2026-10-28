"use strict";

const { resetDb } = require("./helpers/testDb");

const test = require("node:test");
const assert = require("node:assert/strict");
const db = require("../src/db");
const store = require("../src/store/sampleStore");
const { createQueue } = require("../src/queue/jobQueue");
const config = require("../src/config");

test.before(resetDb);

// Each test makes its own queue. Stop it when the test ends, or an idle
// queue from an earlier test would pick up the next test's jobs.
const queues = [];
function makeQueue(options) {
  const queue = createQueue(options);
  queues.push(queue);
  return queue;
}
test.afterEach(() => {
  queues.splice(0).forEach((q) => q.stop());
});

let n = 0;
function newJob() {
  n += 1;
  return store.createLinkSample({ sha256: String(n).padStart(64, "0"), url: `https://example.com/${n}` });
}
async function jobStatus(jobId) {
  return (await store.getJob(jobId)).status;
}
function deferred() {
  let resolve;
  const promise = new Promise((r) => (resolve = r));
  return { promise, resolve };
}

test("a job moves queued -> running -> completed", async () => {
  const gate = deferred();
  const queue = makeQueue({ concurrency: 1, runner: () => gate.promise });
  const { jobId } = await newJob();
  assert.equal(await jobStatus(jobId), "queued");

  queue.enqueue();
  for (let i = 0; i < 50 && (await jobStatus(jobId)) !== "running"; i += 1) {
    await new Promise((r) => setTimeout(r, 10));
  }
  assert.equal(await jobStatus(jobId), "running");

  gate.resolve();
  assert.equal(await queue.waitFor(jobId, 1000), true);
  const job = await store.getJob(jobId);
  assert.equal(job.status, "completed");
  assert.equal(job.attempts, 1);
  assert.ok(job.started_at && job.finished_at);
});

test("a runner that throws marks the job failed and the queue keeps going", async () => {
  const queue = makeQueue({
    concurrency: 1,
    runner: async (sampleId) => {
      if (sampleId === bad.sampleId) throw new Error("boom");
    },
  });
  const bad = await newJob();
  const good = await newJob();
  queue.enqueue();

  await queue.waitFor(good.jobId, 1000);
  const failed = await store.getJob(bad.jobId);
  assert.equal(failed.status, "failed");
  assert.equal(failed.error_message, "boom");
  assert.equal(await jobStatus(good.jobId), "completed");
});

test("no more than `concurrency` jobs run at once, in submission order", async () => {
  let running = 0;
  let peak = 0;
  const order = [];
  const queue = makeQueue({
    concurrency: 2,
    runner: async (sampleId) => {
      order.push(sampleId);
      running += 1;
      peak = Math.max(peak, running);
      await new Promise((r) => setTimeout(r, 15));
      running -= 1;
    },
  });
  const jobs = [];
  for (let i = 0; i < 5; i += 1) jobs.push(await newJob());
  queue.enqueue();

  await Promise.all(jobs.map((j) => queue.waitFor(j.jobId, 2000)));
  assert.equal(peak, 2);
  assert.deepEqual(order, jobs.map((j) => j.sampleId));
  for (const j of jobs) assert.equal(await jobStatus(j.jobId), "completed");
});

test("waitFor gives up with false when the job outlasts the timeout", async () => {
  const gate = deferred();
  const queue = makeQueue({ concurrency: 1, runner: () => gate.promise });
  const { jobId } = await newJob();
  queue.enqueue();

  assert.equal(await queue.waitFor(jobId, 20), false);
  assert.equal(await jobStatus(jobId), "running");
  gate.resolve();
  assert.equal(await queue.waitFor(jobId, 1000), true);
});

test("start() re-queues jobs left running by a crash and finishes them", async () => {
  const { jobId } = await newJob();
  await db.run("UPDATE jobs SET status = 'running', attempts = 1 WHERE id = ?", [jobId]);

  const queue = makeQueue({ concurrency: 1, runner: async () => {} });
  assert.deepEqual(await queue.start(), { requeued: 1 });
  assert.equal(await queue.waitFor(jobId, 1000), true);

  const job = await store.getJob(jobId);
  assert.equal(job.status, "completed");
  assert.equal(job.attempts, 2);
});

test("a backend never runs or re-queues another backend's jobs", async () => {
  // Another teammate's backend, sharing the database: one job waiting, one
  // in progress. Their upload is on their disk, not ours.
  const theirs = await newJob();
  const theirsRunning = await newJob();
  await db.run("UPDATE jobs SET worker_id = 'teammate-laptop:3000' WHERE id IN (?, ?)", [theirs.jobId, theirsRunning.jobId]);
  await db.run("UPDATE jobs SET status = 'running' WHERE id = ?", [theirsRunning.jobId]);
  const mine = await newJob();

  const ran = [];
  const queue = makeQueue({ concurrency: 2, runner: async (sampleId) => ran.push(sampleId) });
  assert.deepEqual(await queue.start(), { requeued: 0 });
  assert.equal(await queue.waitFor(mine.jobId, 1000), true);
  await new Promise((r) => setTimeout(r, 50));

  assert.deepEqual(ran, [mine.sampleId]);
  assert.equal(await jobStatus(theirs.jobId), "queued");
  assert.equal(await jobStatus(theirsRunning.jobId), "running");
});

test("new jobs belong to this backend", async () => {
  const { jobId } = await newJob();
  assert.equal((await store.getJob(jobId)).worker_id, config.workerId);
});
