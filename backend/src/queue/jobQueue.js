"use strict";

/**
 * Job queue: scans run in the background instead of inside the HTTP request.
 *
 * Why not BullMQ + Redis: the queue's state already has to live in the
 * database for scan history, and Redis would be one more thing every
 * teammate has to install to run the backend. So the `jobs` table IS the
 * queue, and this module is the worker loop over it.
 *
 * Shared database: every job records the backend that created it
 * (config.workerId), and a backend only picks up its own jobs. An uploaded
 * file is saved on the disk of the backend that received it, so no other
 * backend could scan it anyway. Swapping in a real broker later means replacing this
 * file; the routes only call enqueue() / waitFor().
 *
 * States: queued -> running -> completed | failed.
 *   completed = the pipeline ran to the end (individual stages may still
 *               have failed -- see results[].status)
 *   failed    = the pipeline itself crashed
 *
 * Durability: a job is a database row before the upload request returns, so
 * a restart loses nothing. start() re-queues this backend's jobs that were
 * 'running' when it died and resumes anything still queued.
 */

const config = require("../config");
const store = require("../store/sampleStore");
const { runPipeline } = require("../pipeline/runPipeline");

function createQueue({ concurrency = config.jobConcurrency, runner = runPipeline, workerId = config.workerId } = {}) {
  let active = 0;
  let scheduled = false;
  let pumping = false;
  let pumpAgain = false;
  let stopped = false;
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
      await store.finishJob(job.id, status, error);
    } catch (err) {
      console.error(`Could not record the end of job ${job.id}:`, err.message);
    } finally {
      active -= 1;
      settle(job.id);
      kick();
    }
  }

  // Claims queued jobs until `concurrency` are running. Only one pump runs at
  // a time; a kick that arrives mid-pump makes it go round once more.
  async function pump() {
    scheduled = false;
    if (stopped) return;
    if (pumping) {
      pumpAgain = true;
      return;
    }
    pumping = true;
    try {
      do {
        pumpAgain = false;
        while (active < concurrency && !stopped) {
          const job = await store.nextQueuedJob(workerId);
          if (!job) break;
          if (!(await store.startJob(job.id))) continue; // lost a race; try the next one
          active += 1;
          work(job);
        }
      } while (pumpAgain);
    } catch (err) {
      // Database unreachable: try again shortly instead of stalling forever.
      console.error("Job queue could not reach the database:", err.message);
      setTimeout(kick, 5000).unref();
    } finally {
      pumping = false;
    }
  }

  /** Ask the worker loop to pick up queued jobs, after the current tick. */
  function kick() {
    if (scheduled || stopped) return;
    scheduled = true;
    setImmediate(pump);
  }

  return {
    /** Call once at startup: recover interrupted jobs and resume the backlog. */
    async start() {
      const requeued = await store.requeueRunningJobs(workerId);
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
    async waitFor(jobId, timeoutMs = config.waitTimeoutMs) {
      const job = await store.getJob(jobId);
      if (!job || job.status === "completed" || job.status === "failed") return true;
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

    /** Stop claiming new jobs. Jobs already running are left to finish. */
    stop() {
      stopped = true;
    },

    stats() {
      return { active, concurrency, workerId };
    },
  };
}

// One queue per process: the routes and server.js share this instance.
const queue = createQueue();

module.exports = { queue, createQueue };
