"use strict";

const fs = require("node:fs");
const path = require("node:path");
const Database = require("better-sqlite3");
const config = require("./config");

if (config.databasePath !== ":memory:") {
  fs.mkdirSync(path.dirname(config.databasePath), { recursive: true });
}

const db = new Database(config.databasePath);
db.pragma("journal_mode = WAL");
db.pragma("foreign_keys = ON");

db.exec(`
  CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT NOT NULL,             -- file contents, or the normalized URL for a link
    submission_type TEXT NOT NULL CHECK (submission_type IN ('file', 'link')),
    original_filename TEXT,
    submitted_url TEXT,
    file_size INTEGER,
    stored_path TEXT,                 -- where the upload lives on disk (files only)
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
  );

  CREATE INDEX IF NOT EXISTS idx_samples_sha256 ON samples (sha256);

  CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id INTEGER NOT NULL REFERENCES samples (id) ON DELETE CASCADE,
    stage TEXT NOT NULL,              -- 'signature' | 'static_analysis' | 'static_ml' | 'sandbox' | 'behavioral_ml' | 'llm'
    status TEXT NOT NULL,             -- 'running' | 'complete' | 'failed'
    signature_match INTEGER,          -- 0/1, only meaningful for stage = 'signature'
    report_json TEXT,                 -- full stage report, JSON-encoded
    error_message TEXT,               -- JSON-encoded { code, message, details } when status = 'failed'
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
  );

  CREATE INDEX IF NOT EXISTS idx_results_sample_id ON results (sample_id);

  -- One job per submission: the unit of work the queue hands to a worker.
  CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id INTEGER NOT NULL REFERENCES samples (id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued'
      CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    started_at TEXT,
    finished_at TEXT
  );

  CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status, id);
  CREATE INDEX IF NOT EXISTS idx_jobs_sample_id ON jobs (sample_id);
`);

// Databases created before the job queue existed have a `samples` table
// without stored_path; CREATE TABLE IF NOT EXISTS does not add columns.
const sampleColumns = db.prepare("PRAGMA table_info(samples)").all().map((c) => c.name);
if (!sampleColumns.includes("stored_path")) {
  db.exec("ALTER TABLE samples ADD COLUMN stored_path TEXT");
}

module.exports = db;
