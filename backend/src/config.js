"use strict";

try {
  // Optional: only present once `npm install` has run. Falling back to
  // process.env alone (e.g. in CI or before deps are installed) is fine.
  require("dotenv").config();
} catch (_) {
  /* dotenv not installed yet -- ignore, real env vars still work */
}
const path = require("node:path");

function resolveFromRoot(p) {
  return path.isAbsolute(p) ? p : path.join(__dirname, "..", p);
}

const config = {
  port: parseInt(process.env.PORT || "3000", 10),
  pythonPath: process.env.PYTHON_PATH || "python3",
  analyzerScriptPath: resolveFromRoot(
    process.env.ANALYZER_SCRIPT_PATH || "./scripts/mock_analyze.py"
  ),
  uploadDir: resolveFromRoot(process.env.UPLOAD_DIR || "./uploads"),
  databasePath: process.env.DATABASE_PATH === ":memory:" ? ":memory:" : resolveFromRoot(process.env.DATABASE_PATH || "./data/sentinel.db"),
  maxUploadBytes: parseInt(process.env.MAX_UPLOAD_BYTES || "26214400", 10), // 25 MiB
  analyzerTimeoutMs: parseInt(process.env.ANALYZER_TIMEOUT_MS || "15000", 10),
  // Analyzer report contract versions (malware_detection/REPORT_CONTRACT.md)
  // this backend accepts. The backend stores the report and passes it to the
  // dashboard without reading inside it, so the additive 1.1.0 and 1.2.0
  // releases are safe to accept. A new major version must be added here on
  // purpose, after checking what changed.
  supportedSchemaVersions: ["1.0.0", "1.1.0", "1.2.0"],

  // Job queue (src/queue/jobQueue.js). Scans run in the background; this is
  // how many run at once, and how long `?wait=true` holds a request open
  // before falling back to a 202 the client can poll.
  jobConcurrency: parseInt(process.env.JOB_CONCURRENCY || "2", 10),
  waitTimeoutMs: parseInt(process.env.WAIT_TIMEOUT_MS || "30000", 10),

  // Signature catalog (src/signatures/catalog.js). The JSON catalog is
  // curated and committed; the hash list is an optional bulk feed (one
  // SHA-256 per line, e.g. a MalwareBazaar export) that is NOT committed.
  signatureCatalogPath: resolveFromRoot(
    process.env.SIGNATURE_CATALOG_PATH || "./signatures/catalog.json"
  ),
  signatureHashlistPath: process.env.SIGNATURE_HASHLIST_PATH
    ? resolveFromRoot(process.env.SIGNATURE_HASHLIST_PATH)
    : null,

  maxUrlLength: parseInt(process.env.MAX_URL_LENGTH || "2048", 10),

  // Behavioral ML stage (e.g. ML/predict.py --serve). Not wired into a
  // route yet -- the sandbox's telemetry schema needs to be settled first
  // (see backend/README.md "Open coordination items"). httpStage.js is
  // ready to call this once there's an agreed report shape to send it.
  behavioralMlUrl: process.env.BEHAVIORAL_ML_URL || "http://127.0.0.1:8000/",
  behavioralMlTimeoutMs: parseInt(process.env.BEHAVIORAL_ML_TIMEOUT_MS || "15000", 10),
};

module.exports = config;
