"use strict";

const express = require("express");
const multer = require("multer");
const crypto = require("node:crypto");
const path = require("node:path");
const fs = require("node:fs");

const config = require("../config");
const db = require("../db");
const { runAnalyzer, AnalyzerError } = require("../analyzer/runAnalyzer");
const { checkSignature } = require("../signatures/knownHashes");

const router = express.Router();

fs.mkdirSync(config.uploadDir, { recursive: true });

const storage = multer.diskStorage({
  destination: config.uploadDir,
  filename: (req, file, cb) => {
    const unique = crypto.randomBytes(16).toString("hex");
    cb(null, `${unique}${path.extname(file.originalname)}`);
  },
});

const upload = multer({
  storage,
  limits: { fileSize: config.maxUploadBytes },
});

// POST /api/samples  (multipart/form-data, field name: "file")
//
// Week 3 benchmark: "An uploaded file ... produces a hash + signature-match
// result that is correctly stored in the database."
router.post("/samples", upload.single("file"), async (req, res) => {
  if (!req.file) {
    return res.status(400).json({ error: "missing_file", message: "Upload a file under field name 'file'." });
  }

  const insertSample = db.prepare(`
    INSERT INTO samples (sha256, submission_type, original_filename, file_size)
    VALUES (?, 'file', ?, ?)
  `);
  const insertResult = db.prepare(`
    INSERT INTO results (sample_id, stage, status, signature_match, report_json, error_message)
    VALUES (?, 'signature', ?, ?, ?, ?)
  `);

  try {
    const report = await runAnalyzer(req.file.path);
    const signatureMatch = checkSignature(report.sha256);

    // Placeholder sha256/original_filename get overwritten with the
    // analyzer's own values so the DB reflects what was actually hashed.
    const sampleInfo = insertSample.run(report.sha256, req.file.originalname, req.file.size);
    insertResult.run(sampleInfo.lastInsertRowid, "complete", signatureMatch ? 1 : 0, JSON.stringify(report), null);

    return res.status(201).json({
      sample_id: sampleInfo.lastInsertRowid,
      sha256: report.sha256,
      signature_match: signatureMatch,
      analyzer_report: report,
    });
  } catch (err) {
    // Still record the attempt so failures show up in scan history, per the
    // Database Record's "operational configuration" scope in the backend
    // documentation form.
    const sampleInfo = insertSample.run("unknown", req.file.originalname, req.file.size);
    insertResult.run(
      sampleInfo.lastInsertRowid,
      "failed",
      null,
      null,
      err instanceof AnalyzerError ? JSON.stringify(err.details || {}) : null
    );

    if (err instanceof AnalyzerError) {
      const statusByCode = {
        INPUT_NOT_FOUND: 400,
        BAD_JSON: 502,
        UNSUPPORTED_SCHEMA: 502,
        NONZERO_EXIT: 422, // most likely: not a valid PE file
        TIMEOUT: 504,
        LAUNCH_FAILED: 500,
      };
      const status = statusByCode[err.code] || 500;
      return res.status(status).json({ error: err.code, message: err.message, sample_id: sampleInfo.lastInsertRowid });
    }

    req.log?.error?.(err);
    return res.status(500).json({ error: "internal_error", message: "Unexpected server error." });
  }
});

// GET /api/samples/:id
router.get("/samples/:id", (req, res) => {
  const sample = db.prepare("SELECT * FROM samples WHERE id = ?").get(req.params.id);
  if (!sample) {
    return res.status(404).json({ error: "not_found" });
  }
  const results = db.prepare("SELECT * FROM results WHERE sample_id = ? ORDER BY created_at").all(sample.id);
  return res.json({
    ...sample,
    results: results.map((r) => ({
      ...r,
      signature_match: r.signature_match === null ? null : Boolean(r.signature_match),
      report: r.report_json ? JSON.parse(r.report_json) : null,
    })),
  });
});

// POST /api/links  -- not implemented yet.
//
// Week 3/8 plan extends ingestion and the sandbox to accept links too, but
// that depends on Dynamic Analysis extending the sandbox harness to render
// URLs (Week 8). Stubbed here so the route exists and fails loudly instead
// of silently, rather than half-implemented.
router.post("/links", (req, res) => {
  res.status(501).json({
    error: "not_implemented",
    message: "Link analysis depends on the Week 8 sandbox extension; not wired up yet.",
  });
});

module.exports = router;
