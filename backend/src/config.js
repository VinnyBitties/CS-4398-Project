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
  supportedSchemaVersions: ["1.0.0"],

  // Behavioral ML stage (e.g. ML/predict.py --serve). Not wired into a
  // route yet -- the sandbox's telemetry schema needs to be settled first
  // (see backend/README.md "Open coordination items"). httpStage.js is
  // ready to call this once there's an agreed report shape to send it.
  behavioralMlUrl: process.env.BEHAVIORAL_ML_URL || "http://127.0.0.1:8000/",
  behavioralMlTimeoutMs: parseInt(process.env.BEHAVIORAL_ML_TIMEOUT_MS || "15000", 10),
};

module.exports = config;
