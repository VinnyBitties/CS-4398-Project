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

  // Sandbox stage (dynamic_telemetry/api.py). Empty = the sandbox and
  // behavioral ML stages are skipped. Base URL only; /detonate is appended.
  sandboxUrl: process.env.SANDBOX_URL || "",
  // How long the sample runs inside the VM (the sandbox's own `timeout`).
  sandboxDetonationSeconds: parseInt(process.env.SANDBOX_DETONATION_SECONDS || "15", 10),
  // Whole HTTP request: revert + detonation + log export and parsing.
  sandboxTimeoutMs: parseInt(process.env.SANDBOX_TIMEOUT_MS || "120000", 10),

  // Behavioral ML stage (ML/predict.py --serve). Runs after the sandbox
  // stage; src/adapters/sandboxToMl.js converts the sandbox's report into
  // the shape the ML service expects.
  behavioralMlUrl: process.env.BEHAVIORAL_ML_URL || "http://127.0.0.1:8000/",
  behavioralMlTimeoutMs: parseInt(process.env.BEHAVIORAL_ML_TIMEOUT_MS || "15000", 10),

  // Accounts and sessions (src/auth, src/routes/auth.js).
  // How long a login lasts before the user has to sign in again.
  sessionTtlHours: parseInt(process.env.SESSION_TTL_HOURS || "168", 10), // 7 days
  // Mark the session cookie Secure (HTTPS only). Leave false for local
  // http://localhost development; set true once the site is served over HTTPS.
  cookieSecure: ["1", "true", "yes"].includes(String(process.env.COOKIE_SECURE || "").toLowerCase()),
  // Set false to stop new sign-ups (existing accounts can still log in).
  allowRegistration: !["0", "false", "no"].includes(String(process.env.ALLOW_REGISTRATION || "true").toLowerCase()),
  // Failed logins allowed per username + IP before a 15-minute lockout.
  maxFailedLogins: parseInt(process.env.MAX_FAILED_LOGINS || "10", 10),

  // The dashboard (website/). The backend serves it, so the pages and the
  // API share one origin and the session cookie just works. Set to an empty
  // string to turn this off.
  websiteDir: process.env.WEBSITE_DIR === "" ? "" : resolveFromRoot(process.env.WEBSITE_DIR || "../website"),
  // Other origins allowed to call the API with the session cookie, for when
  // the pages are served separately (e.g. VS Code Live Server on :5500).
  corsOrigins: (process.env.CORS_ORIGINS || "http://localhost:5500,http://127.0.0.1:5500")
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean),
};

module.exports = config;
