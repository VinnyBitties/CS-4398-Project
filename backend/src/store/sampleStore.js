"use strict";

/**
 * All SQL for samples, per-stage results and jobs lives here, plus the one
 * function that turns those rows into the JSON shape the API returns
 * (docs/api-contract.md). Routes, the queue and the pipeline go through this
 * module rather than writing SQL of their own.
 */

const db = require("../db");

const NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')";

const stmts = {
  insertFile: db.prepare(`
    INSERT INTO samples (sha256, submission_type, original_filename, file_size, stored_path)
    VALUES (?, 'file', ?, ?, ?)
  `),
  insertLink: db.prepare(`
    INSERT INTO samples (sha256, submission_type, submitted_url)
    VALUES (?, 'link', ?)
  `),
  getSample: db.prepare("SELECT * FROM samples WHERE id = ?"),
  listSamples: db.prepare("SELECT id FROM samples ORDER BY id DESC LIMIT ? OFFSET ?"),
  countSamples: db.prepare("SELECT COUNT(*) AS n FROM samples"),

  insertJob: db.prepare("INSERT INTO jobs (sample_id) VALUES (?)"),
  getJob: db.prepare("SELECT * FROM jobs WHERE id = ?"),
  latestJobForSample: db.prepare("SELECT * FROM jobs WHERE sample_id = ? ORDER BY id DESC LIMIT 1"),
  nextQueuedJob: db.prepare("SELECT * FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1"),
  startJob: db.prepare(`
    UPDATE jobs SET status = 'running', attempts = attempts + 1, started_at = ${NOW}
    WHERE id = ? AND status = 'queued'
  `),
  finishJob: db.prepare(`
    UPDATE jobs SET status = ?, error_message = ?, finished_at = ${NOW} WHERE id = ?
  `),
  requeueRunningJobs: db.prepare("UPDATE jobs SET status = 'queued', started_at = NULL WHERE status = 'running'"),

  startResult: db.prepare("INSERT INTO results (sample_id, stage, status) VALUES (?, ?, 'running')"),
  finishResult: db.prepare(`
    UPDATE results SET status = ?, signature_match = ?, report_json = ?, error_message = ? WHERE id = ?
  `),
  deleteRunningResults: db.prepare("DELETE FROM results WHERE sample_id = ? AND status = 'running'"),
  resultsForSample: db.prepare("SELECT * FROM results WHERE sample_id = ? ORDER BY id"),
};

function parseJson(text) {
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (_) {
    return { message: text };
  }
}

const createSampleAndJob = db.transaction((insert) => {
  const sampleId = Number(insert().lastInsertRowid);
  const jobId = Number(stmts.insertJob.run(sampleId).lastInsertRowid);
  return { sampleId, jobId };
});

function createFileSample({ sha256, originalFilename, fileSize, storedPath }) {
  return createSampleAndJob(() => stmts.insertFile.run(sha256, originalFilename, fileSize, storedPath));
}

function createLinkSample({ sha256, url }) {
  return createSampleAndJob(() => stmts.insertLink.run(sha256, url));
}

function getSampleRow(id) {
  return stmts.getSample.get(id) || null;
}

/**
 * The API representation of one submission. `status` is the job's state;
 * `signature_match` is null until the signature stage has finished.
 */
function getSampleView(id) {
  const sample = stmts.getSample.get(id);
  if (!sample) return null;
  const job = stmts.latestJobForSample.get(sample.id);
  const results = stmts.resultsForSample.all(sample.id);
  const signature = results.find((r) => r.stage === "signature" && r.status === "complete");

  return {
    sample_id: sample.id,
    submission_type: sample.submission_type,
    status: job ? job.status : "completed", // rows from before the queue existed have no job
    sha256: sample.sha256,
    original_filename: sample.original_filename,
    submitted_url: sample.submitted_url,
    file_size: sample.file_size,
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

function listSampleViews({ limit, offset }) {
  return {
    total: stmts.countSamples.get().n,
    limit,
    offset,
    samples: stmts.listSamples.all(limit, offset).map((row) => getSampleView(row.id)),
  };
}

module.exports = {
  stmts,
  createFileSample,
  createLinkSample,
  getSampleRow,
  getSampleView,
  listSampleViews,
};
