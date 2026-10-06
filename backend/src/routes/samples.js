"use strict";

const express = require("express");
const multer = require("multer");
const crypto = require("node:crypto");
const path = require("node:path");
const fs = require("node:fs");

const config = require("../config");
const store = require("../store/sampleStore");
const { queue } = require("../queue/jobQueue");
const { normalizeUrl } = require("../signatures/catalog");

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

function sha256OfFile(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    fs.createReadStream(filePath)
      .on("error", reject)
      .on("data", (chunk) => hash.update(chunk))
      .on("end", () => resolve(hash.digest("hex")));
  });
}

function wantsWait(req) {
  return ["1", "true", "yes"].includes(String(req.query.wait || "").toLowerCase());
}

/**
 * Shared tail of both submission routes: the sample and its job are already
 * in the database; hand the job to the queue and answer.
 *
 *   default      -> 202 Accepted straight away; poll GET /api/samples/:id
 *   ?wait=true   -> hold the request until the scan finishes -> 201 Created,
 *                   or 202 if it is still running after WAIT_TIMEOUT_MS
 */
async function respondWithSubmission(req, res, { sampleId, jobId }) {
  queue.enqueue();
  const finished = wantsWait(req) ? await queue.waitFor(jobId) : false;
  res.location(`/api/samples/${sampleId}`);
  return res.status(finished ? 201 : 202).json(store.getSampleView(sampleId));
}

// POST /api/samples  (multipart/form-data, field name: "file")
router.post("/samples", upload.single("file"), async (req, res, next) => {
  if (!req.file) {
    return res.status(400).json({ error: "missing_file", message: "Upload a file under field name 'file'." });
  }
  try {
    // Hashed here, not taken from the analyzer, so the hash and the
    // signature lookup never depend on a Python process being healthy.
    const sha256 = await sha256OfFile(req.file.path);
    const ids = store.createFileSample({
      sha256,
      originalFilename: req.file.originalname,
      fileSize: req.file.size,
      storedPath: req.file.path,
    });
    return await respondWithSubmission(req, res, ids);
  } catch (err) {
    return next(err);
  }
});

// POST /api/links  (application/json: { "url": "https://..." })
//
// The backend never fetches the submitted URL: requesting an attacker-chosen
// address from the server is an SSRF hole, and the page may be live malware.
// Visiting the link is the sandbox's job (Week 8). Until then a link gets
// the one stage that needs no network: the signature lookup.
router.post("/links", async (req, res, next) => {
  const raw = req.body && typeof req.body.url === "string" ? req.body.url.trim() : "";
  if (!raw) {
    return res.status(400).json({ error: "missing_url", message: 'Send JSON like {"url": "https://example.com/"}.' });
  }
  if (raw.length > config.maxUrlLength) {
    return res.status(400).json({ error: "url_too_long", message: `URLs are limited to ${config.maxUrlLength} characters.` });
  }
  let url;
  try {
    const parsed = new URL(raw);
    if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname) throw new Error("unsupported");
    url = normalizeUrl(raw);
  } catch (_) {
    return res.status(400).json({ error: "invalid_url", message: "Only absolute http:// and https:// URLs are accepted." });
  }
  try {
    const sha256 = crypto.createHash("sha256").update(url).digest("hex");
    return await respondWithSubmission(req, res, store.createLinkSample({ sha256, url }));
  } catch (err) {
    return next(err);
  }
});

// GET /api/samples?limit=20&offset=0  -- scan history, newest first (FR08)
router.get("/samples", (req, res) => {
  const limit = Math.min(Math.max(parseInt(req.query.limit, 10) || 20, 1), 100);
  const offset = Math.max(parseInt(req.query.offset, 10) || 0, 0);
  return res.json(store.listSampleViews({ limit, offset }));
});

// GET /api/samples/:id
router.get("/samples/:id", (req, res) => {
  const view = /^\d+$/.test(req.params.id) ? store.getSampleView(Number(req.params.id)) : null;
  if (!view) {
    return res.status(404).json({ error: "not_found" });
  }
  return res.json(view);
});

module.exports = router;
