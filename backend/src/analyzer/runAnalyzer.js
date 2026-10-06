"use strict";

/**
 * Wraps the static analyzer (malware_detection/analyze.py), following the
 * Node.js integration design that component originally documented and the
 * I/O contract in malware_detection/REPORT_CONTRACT.md:
 *
 *   1. Resolve absolute paths for the Python interpreter, the analyzer
 *      script, and the input file. Launch with spawn(), args passed
 *      separately (never a shell command string).
 *   2. Collect stdout/stderr separately as UTF-8, draining both as data
 *      arrives (a 'data' event is a chunk, not necessarily one JSON object).
 *   3. Handle the child 'error' event (launch failure) distinctly from a
 *      nonzero exit code, and guard against completing twice.
 *   4. Never parse partial stdout as success — only the full buffered
 *      string, and only after a clean exit.
 *   5. On exit 0, JSON.parse the full stdout once, then apply the project's
 *      contract checks (schema_version must be one this backend supports).
 *
 * Guardrails the handoff doc calls out as the backend team's responsibility
 * (execution-time limit, bounded captured output) are implemented here too.
 */

const { spawn } = require("node:child_process");
const fs = require("node:fs");
const config = require("../config");

const MAX_CAPTURED_BYTES = 10 * 1024 * 1024; // bound stdout/stderr capture

class AnalyzerError extends Error {
  constructor(message, code, details) {
    super(message);
    this.name = "AnalyzerError";
    this.code = code; // 'LAUNCH_FAILED' | 'TIMEOUT' | 'NONZERO_EXIT' | 'BAD_JSON' | 'UNSUPPORTED_SCHEMA' | 'INPUT_NOT_FOUND'
    this.details = details;
  }
}

/**
 * Run the static analyzer against a single file and return its parsed,
 * contract-checked report.
 *
 * @param {string} inputFilePath absolute path to the file to analyze
 * @returns {Promise<object>} the parsed analyzer report
 */
function runAnalyzer(inputFilePath) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(inputFilePath)) {
      reject(new AnalyzerError("Input file does not exist", "INPUT_NOT_FOUND", { inputFilePath }));
      return;
    }
    if (!fs.existsSync(config.analyzerScriptPath)) {
      reject(
        new AnalyzerError(
          "Analyzer script not found at configured ANALYZER_SCRIPT_PATH",
          "LAUNCH_FAILED",
          { analyzerScriptPath: config.analyzerScriptPath }
        )
      );
      return;
    }

    const child = spawn(config.pythonPath, [config.analyzerScriptPath, inputFilePath], {
      shell: false,
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";
    let settled = false;
    let timedOut = false;

    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGKILL");
    }, config.analyzerTimeoutMs);

    function finish(err, value) {
      if (settled) return; // never complete twice (e.g. 'error' then 'close')
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

    child.on("error", (err) => {
      // Launch failure: e.g. python interpreter not found.
      finish(new AnalyzerError("Failed to launch analyzer process", "LAUNCH_FAILED", { cause: err.message }));
    });

    child.on("close", (exitCode, signal) => {
      if (timedOut) {
        finish(
          new AnalyzerError("Analyzer timed out", "TIMEOUT", {
            timeoutMs: config.analyzerTimeoutMs,
            stderr: stderr.slice(0, 4000),
          })
        );
        return;
      }
      if (exitCode !== 0) {
        // The contract's failure shape is {"error", "message"} as JSON on
        // stderr (e.g. PEFormatError for a file that is not a PE). Surface
        // it when present so the dashboard can show the analyzer's reason.
        let analyzerError = null;
        try {
          const parsed = JSON.parse(stderr);
          if (parsed && typeof parsed.error === "string") {
            analyzerError = { error: parsed.error, message: String(parsed.message ?? "") };
          }
        } catch (_) {
          /* stderr was not the contract's JSON error; keep the raw text below */
        }
        finish(
          new AnalyzerError(
            analyzerError
              ? `Analyzer rejected the file: ${analyzerError.error}: ${analyzerError.message}`
              : "Analyzer exited with a nonzero status",
            "NONZERO_EXIT",
            {
              exitCode,
              signal,
              analyzer_error: analyzerError,
              stderr: stderr.slice(0, 4000),
            }
          )
        );
        return;
      }

      let report;
      try {
        report = JSON.parse(stdout);
      } catch (parseErr) {
        finish(
          new AnalyzerError("Analyzer stdout was not valid JSON", "BAD_JSON", {
            cause: parseErr.message,
            stdoutPreview: stdout.slice(0, 500),
          })
        );
        return;
      }

      if (!config.supportedSchemaVersions.includes(report.schema_version)) {
        finish(
          new AnalyzerError(
            `Unsupported analyzer schema_version: ${report.schema_version}`,
            "UNSUPPORTED_SCHEMA",
            { received: report.schema_version, supported: config.supportedSchemaVersions }
          )
        );
        return;
      }

      finish(null, report);
    });
  });
}

module.exports = { runAnalyzer, AnalyzerError };
