"use strict";

const fs = require("node:fs");
const path = require("node:path");
const Database = require("better-sqlite3");
const config = require("./config");

fs.mkdirSync(path.dirname(config.databasePath), { recursive: true });

const db = new Database(config.databasePath);
db.pragma("journal_mode = WAL");

db.exec(`
  CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT NOT NULL,
    submission_type TEXT NOT NULL CHECK (submission_type IN ('file', 'link')),
    original_filename TEXT,
    submitted_url TEXT,
    file_size INTEGER,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
  );

  CREATE INDEX IF NOT EXISTS idx_samples_sha256 ON samples (sha256);

  CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id INTEGER NOT NULL REFERENCES samples (id) ON DELETE CASCADE,
    stage TEXT NOT NULL,              -- 'signature' | 'static_ml' | 'sandbox' | 'behavioral_ml' | 'llm'
    status TEXT NOT NULL,             -- 'pending' | 'running' | 'complete' | 'failed'
    signature_match INTEGER,          -- 0/1, only meaningful for stage = 'signature'
    report_json TEXT,                 -- full stage report, JSON-encoded
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
  );

  CREATE INDEX IF NOT EXISTS idx_results_sample_id ON results (sample_id);
`);

module.exports = db;
