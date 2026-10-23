"use strict";

/**
 * Client for the sandbox service (dynamic_telemetry/api.py, FastAPI):
 *   POST /detonate   multipart: file=<sample>, timeout=<seconds>
 *
 * Unlike the ML service, the sandbox takes the sample itself as a file
 * upload, so this can't reuse httpStage.callStage (JSON only). Errors use
 * the same StageHttpError codes so the dashboard sees one vocabulary.
 *
 * The sandbox drives one VM and reverts it to a snapshot at the start of
 * every run, so two overlapping detonations would wipe each other out.
 * Calls from this process are therefore queued one at a time, whatever
 * JOB_CONCURRENCY is set to.
 */

const fs = require("node:fs");
const path = require("node:path");
const { StageHttpError } = require("./httpStage");

let tail = Promise.resolve();

/** Run fn after every earlier call has settled (a one-slot mutex). */
function serialize(fn) {
  const run = tail.then(fn, fn);
  tail = run.catch(() => {});
  return run;
}

/**
 * @param {string} url e.g. http://127.0.0.1:8001/detonate
 * @param {string} filePath sample on disk
 * @param {{ filename?: string, detonationSeconds?: number, timeoutMs?: number }} [options]
 */
function detonate(url, filePath, options = {}) {
  return serialize(() => detonateNow(url, filePath, options));
}

async function detonateNow(url, filePath, options) {
  const detonationSeconds = options.detonationSeconds ?? 15;
  // The sandbox sleeps for the whole detonation, then exports and parses the
  // log, so the request needs well over detonationSeconds.
  const timeoutMs = options.timeoutMs ?? 120000;
  const filename = options.filename || path.basename(filePath);

  let blob;
  try {
    blob = await fs.openAsBlob(filePath);
  } catch (err) {
    throw new StageHttpError("Sample file is not readable", "INPUT_NOT_FOUND", { cause: err.message });
  }
  const form = new FormData();
  form.append("file", blob, filename);
  form.append("timeout", String(detonationSeconds));

  let res;
  try {
    res = await fetch(url, { method: "POST", body: form, signal: AbortSignal.timeout(timeoutMs) });
  } catch (err) {
    if (err.name === "TimeoutError" || err.name === "AbortError") {
      throw new StageHttpError("Sandbox request timed out", "TIMEOUT", { timeoutMs, url });
    }
    throw new StageHttpError("Failed to reach sandbox service", "CONNECTION_FAILED", {
      cause: err.cause?.message || err.message,
      url,
    });
  }

  const text = await res.text();
  if (!res.ok) {
    throw new StageHttpError("Sandbox returned a non-2xx status", "BAD_STATUS", {
      statusCode: res.status,
      bodyPreview: text.slice(0, 500),
    });
  }
  try {
    return JSON.parse(text);
  } catch (err) {
    throw new StageHttpError("Sandbox response was not valid JSON", "BAD_JSON", {
      cause: err.message,
      bodyPreview: text.slice(0, 500),
    });
  }
}

module.exports = { detonate };
