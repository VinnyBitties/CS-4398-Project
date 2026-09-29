"use strict";

/**
 * Generic runner for a pipeline stage that's exposed as a local HTTP
 * service rather than a one-shot CLI process -- e.g. the ML team's
 * `predict.py --serve` pattern (a ThreadingHTTPServer that accepts a
 * POSTed JSON report and returns a JSON verdict).
 *
 * This is a second integration pattern alongside runAnalyzer.js's
 * subprocess model. Not every stage will look the same: signature/static
 * analysis is a CLI (spawn + stdout), while a stage a teammate built as a
 * long-running server needs to be called over HTTP instead of re-spawned
 * per request.
 */

const http = require("node:http");
const { URL } = require("node:url");

class StageHttpError extends Error {
  constructor(message, code, details) {
    super(message);
    this.name = "StageHttpError";
    this.code = code; // 'TIMEOUT' | 'CONNECTION_FAILED' | 'BAD_STATUS' | 'BAD_JSON'
    this.details = details;
  }
}

/**
 * POST a JSON payload to a stage's HTTP endpoint and return its parsed
 * JSON response.
 *
 * @param {string} url e.g. http://127.0.0.1:8000/
 * @param {object} payload JSON-serializable request body
 * @param {{ timeoutMs?: number }} [options]
 */
function callStage(url, payload, options = {}) {
  const timeoutMs = options.timeoutMs || 15000;

  return new Promise((resolve, reject) => {
    const target = new URL(url);
    const body = Buffer.from(JSON.stringify(payload), "utf8");

    const req = http.request(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port,
        path: target.pathname + target.search,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": body.length,
        },
        timeout: timeoutMs,
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => {
          data += chunk.toString("utf8");
        });
        res.on("end", () => {
          if (res.statusCode < 200 || res.statusCode >= 300) {
            reject(
              new StageHttpError("Stage returned a non-2xx status", "BAD_STATUS", {
                statusCode: res.statusCode,
                bodyPreview: data.slice(0, 500),
              })
            );
            return;
          }
          try {
            resolve(JSON.parse(data));
          } catch (err) {
            reject(
              new StageHttpError("Stage response was not valid JSON", "BAD_JSON", {
                cause: err.message,
                bodyPreview: data.slice(0, 500),
              })
            );
          }
        });
      }
    );

    req.on("timeout", () => {
      req.destroy();
      reject(new StageHttpError("Stage request timed out", "TIMEOUT", { timeoutMs, url }));
    });

    req.on("error", (err) => {
      reject(new StageHttpError("Failed to reach stage service", "CONNECTION_FAILED", { cause: err.message, url }));
    });

    req.write(body);
    req.end();
  });
}

module.exports = { callStage, StageHttpError };
