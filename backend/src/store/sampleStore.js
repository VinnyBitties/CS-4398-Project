"use strict";

/**
 * All SQL for samples, per-stage results and jobs lives here, plus the one
 * function that turns those rows into the JSON shape the API returns
 * (docs/api-contract.md). Routes, the queue and the pipeline go through this
 * module rather than writing SQL of their own.
 *
 * Every function is async: the database may be a PostgreSQL server across
 * the network (see src/db.js).
 */

const db = require("../db");

function parseJson(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === "object") return value; // PostgreSQL JSONB arrives parsed
  try {
    return JSON.parse(value);
  } catch (_) {
    return { message: value };
  }
}

// ---- samples -----------------------------------------------------------------

async function createSampleAndJob(insertSample) {
  return db.transaction(async (tx) => {
    const sampleId = await insertSample(tx);
    const jobId = await tx.insert("INSERT INTO jobs (sample_id, worker_id) VALUES (?, ?)", [
      sampleId,
      require("../config").workerId,
    ]);
    return { sampleId, jobId };
  });
}

// userId is the signed-in submitter, or null for a guest.
function createFileSample({ sha256, originalFilename, fileSize, storedPath, userId = null }) {
  return createSampleAndJob((tx) =>
    tx.insert(
      `INSERT INTO samples (sha256, submission_type, original_filename, file_size, stored_path, user_id)
       VALUES (?, 'file', ?, ?, ?, ?)`,
      [sha256, originalFilename, fileSize, storedPath, userId]
    )
  );
}

function createLinkSample({ sha256, url, userId = null }) {
  return createSampleAndJob((tx) =>
    tx.insert(
      `INSERT INTO samples (sha256, submission_type, submitted_url, user_id)
       VALUES (?, 'link', ?, ?)`,
      [sha256, url, userId]
    )
  );
}

function getSampleRow(id) {
  return db.get("SELECT * FROM samples WHERE id = ?", [id]);
}

/** Whether `userId` (null = guest) may see this sample: only its own submitter. */
function canView(sampleRow, userId) {
  return Boolean(sampleRow) && (sampleRow.user_id ?? null) === (userId ?? null);
}

/**
 * The API representation of one submission. `status` is the job's state;
 * `signature_match` is null until the signature stage has finished.
 */
async function getSampleView(id) {
  const sample = await getSampleRow(id);
  if (!sample) return null;
  const [job, results] = await Promise.all([latestJobForSample(sample.id), resultsForSample(sample.id)]);
  const signature = results.find((r) => r.stage === "signature" && r.status === "complete");

  return {
    sample_id: sample.id,
    submission_type: sample.submission_type,
    status: job ? job.status : "completed", // rows from before the queue existed have no job
    sha256: sample.sha256,
    original_filename: sample.original_filename,
    submitted_url: sample.submitted_url,
    file_size: sample.file_size === null ? null : Number(sample.file_size),
    created_at: sample.created_at,
    signature_match: signature ? Boolean(signature.signature_match) : null,
    job: job
      ? {
          job_id: job.id,
          status: job.status,
          attempts: job.attempts,
          error: job.error_message,
          queued_at: job.created_at,
          started_at: job.started_at,
          finished_at: job.finished_at,
        }
      : null,
    results: results.map((r) => ({
      stage: r.stage,
      status: r.status,
      signature_match: r.signature_match === null ? null : Boolean(r.signature_match),
      report: parseJson(r.report_json),
      error: parseJson(r.error_message),
      created_at: r.created_at,
    })),
  };
}

/** Scan history for one user, or for guests when userId is null. */
async function listSampleViews({ limit, offset, userId = null }) {
  // IS NOT DISTINCT FROM also matches NULL = NULL, so null lists guest scans.
  const [count, rows] = await Promise.all([
    db.get("SELECT CAST(COUNT(*) AS INTEGER) AS n FROM samples WHERE user_id IS NOT DISTINCT FROM ?", [userId]),
    db.all(
      "SELECT id FROM samples WHERE user_id IS NOT DISTINCT FROM ? ORDER BY id DESC LIMIT ? OFFSET ?",
      [userId, limit, offset]
    ),
  ]);
  return {
    total: Number(count.n),
    limit,
    offset,
    samples: await Promise.all(rows.map((row) => getSampleView(row.id))),
  };
}

// ---- jobs --------------------------------------------------------------------

function getJob(id) {
  return db.get("SELECT * FROM jobs WHERE id = ?", [id]);
}

function latestJobForSample(sampleId) {
  return db.get("SELECT * FROM jobs WHERE sample_id = ? ORDER BY id DESC LIMIT 1", [sampleId]);
}

/** Oldest queued job belonging to this backend. */
function nextQueuedJob(workerId) {
  return db.get("SELECT * FROM jobs WHERE status = 'queued' AND worker_id = ? ORDER BY id LIMIT 1", [workerId]);
}

/** queued -> running. Returns false if something else already took the job. */
async function startJob(id) {
  const { changes } = await db.run(
    "UPDATE jobs SET status = 'running', attempts = attempts + 1, started_at = ? WHERE id = ? AND status = 'queued'",
    [db.now(), id]
  );
  return changes === 1;
}

function finishJob(id, status, errorMessage) {
  return db.run("UPDATE jobs SET status = ?, error_message = ?, finished_at = ? WHERE id = ?", [
    status,
    errorMessage,
    db.now(),
    id,
  ]);
}

/**
 * At startup: jobs this backend was running when it stopped go back to
 * queued. Only this backend's own jobs; a teammate's backend sharing the
 * database may be running its jobs right now.
 */
async function requeueRunningJobs(workerId) {
  // Jobs from before jobs had an owner belong to whoever starts first. With a
  // local SQLite file that can only be this backend.
  if (db.dialect === "sqlite") {
    await db.run("UPDATE jobs SET worker_id = ? WHERE worker_id IS NULL", [workerId]);
  }
  const { changes } = await db.run(
    "UPDATE jobs SET status = 'queued', started_at = NULL WHERE status = 'running' AND worker_id = ?",
    [workerId]
  );
  return changes;
}

// ---- results -----------------------------------------------------------------

function startResult(sampleId, stage) {
  return db.insert("INSERT INTO results (sample_id, stage, status) VALUES (?, ?, 'running')", [sampleId, stage]);
}

function finishResult(id, { status, signatureMatch = null, reportJson = null, errorMessage = null }) {
  return db.run(
    "UPDATE results SET status = ?, signature_match = ?, report_json = ?, error_message = ? WHERE id = ?",
    [status, signatureMatch, reportJson, errorMessage, id]
  );
}

function deleteRunningResults(sampleId) {
  return db.run("DELETE FROM results WHERE sample_id = ? AND status = 'running'", [sampleId]);
}

function resultsForSample(sampleId) {
  return db.all("SELECT * FROM results WHERE sample_id = ? ORDER BY id", [sampleId]);
}

module.exports = {
  createFileSample,
  createLinkSample,
  getSampleRow,
  getSampleView,
  canView,
  listSampleViews,
  getJob,
  nextQueuedJob,
  startJob,
  finishJob,
  requeueRunningJobs,
  startResult,
  finishResult,
  deleteRunningResults,
};
