"use strict";

/**
 * Runs a Python script as a one-shot stage: JSON in on stdin, JSON out on
 * stdout. A third integration pattern next to runAnalyzer.js (file path in,
 * report out) and httpStage.js (a long-running service).
 *
 * Failure contract, the same one malware_detection/analyze.py uses: exit
 * nonzero and print {"error": ..., "message": ...} as JSON on stderr.
 */

const { spawn } = require("node:child_process");
const fs = require("node:fs");

const MAX_CAPTURED_BYTES = 10 * 1024 * 1024;

class PythonStageError extends Error {
  constructor(message, code, details) {
    super(message);
    this.name = "PythonStageError";
    this.code = code; // 'LAUNCH_FAILED' | 'TIMEOUT' | 'NONZERO_EXIT' | 'BAD_JSON'
    this.details = details;
  }
}

/**
 * @param {{ pythonPath: string, scriptPath: string, args?: string[], input: object, timeoutMs?: number }} options
 * @returns {Promise<object>} the script's parsed stdout
 */
function runPythonJson({ pythonPath, scriptPath, args = [], input, timeoutMs = 30000 }) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(scriptPath)) {
      reject(new PythonStageError("Stage script not found", "LAUNCH_FAILED", { scriptPath }));
      return;
    }

    const child = spawn(pythonPath, [scriptPath, ...args], { shell: false, windowsHide: true });

    let stdout = "";
    let stderr = "";
    let settled = false;
    let timedOut = false;

    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGKILL");
    }, timeoutMs);

    function finish(err, value) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (err) reject(err);
      else resolve(value);
    }

    child.stdout.on("data", (chunk) => {
      if (stdout.length < MAX_CAPTURED_BYTES) stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk) => {
      if (stderr.length < MAX_CAPTURED_BYTES) stderr += chunk.toString("utf8");
    });
    // The script may exit before reading all of stdin; the exit code and
    // stderr say why, so a broken pipe here is not worth its own error.
    child.stdin.on("error", () => {});

    child.on("error", (err) => {
      finish(new PythonStageError("Failed to launch Python", "LAUNCH_FAILED", { cause: err.message, pythonPath }));
    });

    child.on("close", (exitCode, signal) => {
      if (timedOut) {
        finish(new PythonStageError("Stage script timed out", "TIMEOUT", { timeoutMs, stderr: stderr.slice(0, 4000) }));
        return;
      }
      if (exitCode !== 0) {
        let scriptError = null;
        try {
          const parsed = JSON.parse(stderr);
          if (parsed && typeof parsed.error === "string") {
            scriptError = { error: parsed.error, message: String(parsed.message ?? "") };
          }
        } catch (_) {
          /* not the JSON failure shape; keep the raw stderr below */
        }
        finish(
          new PythonStageError(
            scriptError ? `${scriptError.error}: ${scriptError.message}` : "Stage script exited with a nonzero status",
            "NONZERO_EXIT",
            { exitCode, signal, script_error: scriptError, stderr: stderr.slice(0, 4000) }
          )
        );
        return;
      }
      try {
        finish(null, JSON.parse(stdout));
      } catch (err) {
        finish(
          new PythonStageError("Stage script stdout was not valid JSON", "BAD_JSON", {
            cause: err.message,
            stdoutPreview: stdout.slice(0, 500),
          })
        );
      }
    });

    child.stdin.end(JSON.stringify(input));
  });
}

module.exports = { runPythonJson, PythonStageError };
