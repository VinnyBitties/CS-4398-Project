"use strict";

/**
 * Job queue: scans run in the background instead of inside the HTTP request.
 *
 * Why not BullMQ + Redis: the queue's state already has to live in SQLite
 * for scan history, a single Node process is the only worker this project
 * runs, and Redis would be one more thing every teammate has to install to
 * run the backend. So the `jobs` table IS the queue, and this module is the
 * worker loop over it. Swapping in a real broker later means replacing this
 * file; the routes only call enqueue() / waitFor().
 *
 * States: queued -> running -> completed | failed.
 *   completed = the pipeline ran to the end (individual stages may still
 *               have failed -- see results[].status)
 *   failed    = the pipeline itself crashed
 *
 * Durability: a job is a database row before the upload request returns, so
 * a restart loses nothing. start() re-queues jobs that were 'running' when
 * the process died and resumes anything still queued.
 */

const config = require("../config");
const store = require("../store/sampleStore");
const { runPipeline } = require("../pipeline/runPipeline");

function createQueue({ concurrency = config.jobConcurrency, runner = runPipeline } = {}) {
  let active = 0;
  let scheduled = false;
  const waiters = new Map(); // jobId -> [resolve]

  function settle(jobId) {
    const list = waiters.get(jobId);
    if (!list) return;
    waiters.delete(jobId);
    list.forEach((resolve) => resolve(true));
  }

  async function work(job) {
    let status = "completed";
    let error = null;
    try {
      await runner(job.sample_id);
    } catch (err) {
      status = "failed";
      error = err && err.message ? err.message : String(err);
    }
    try {
      store.stmts.finishJob.run(status, error, job.id);
    } finally {
      active -= 1;
      settle(job.id);
      pump();
    }
  }

  function pump() {
    scheduled = false;
    while (active < concurrency) {
      const job = store.stmts.nextQueuedJob.get();
      if (!job) return;
      if (store.stmts.startJob.run(job.id).changes !== 1) continue; // lost a race; try the next one
      active += 1;
      work(job);
    }
  }

  /** Ask the worker loop to pick up queued jobs, after the current tick. */
  function kick() {
    if (scheduled) return;
    scheduled = true;
    setImmediate(pump);
  }

  return {
    /** Call once at startup: recover interrupted jobs and resume the backlog. */
    start() {
      const requeued = store.stmts.requeueRunningJobs.run().changes;
      kick();
      return { requeued };
    },

    /** Tell the queue a job row was just inserted. */
    enqueue() {
      kick();
    },

    /**
     * Resolve true when the job finishes, or false after timeoutMs. Lets
     * `?wait=true` requests behave synchronously without blocking the queue.
     */
    waitFor(jobId, timeoutMs = config.waitTimeoutMs) {
      const job = store.stmts.getJob.get(jobId);
      if (!job || job.status === "completed" || job.status === "failed") return Promise.resolve(true);
      return new Promise((resolve) => {
        const timer = setTimeout(() => {
          const list = waiters.get(jobId) || [];
          const i = list.indexOf(done);
          if (i !== -1) list.splice(i, 1);
          resolve(false);
        }, timeoutMs);
        function done() {
          clearTimeout(timer);
          resolve(true);
        }
        if (!waiters.has(jobId)) waiters.set(jobId, []);
        waiters.get(jobId).push(done);
      });
    },

    stats() {
      return { active, concurrency };
    },
  };
}

// One queue per process: the routes and server.js share this instance.
const queue = createQueue();

module.exports = { queue, createQueue };
