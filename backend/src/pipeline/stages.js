"use strict";

/**
 * The pipeline, as an ordered list of stages. A job runs every stage whose
 * `appliesTo` includes the sample's submission_type, in this order.
 *
 * To wire in a new stage (static ML, sandbox, behavioral ML, LLM), add an
 * object here -- nothing else in the queue, the routes or the database needs
 * to change:
 *
 *   {
 *     name: "sandbox",                    // stored in results.stage
 *     appliesTo: ["file", "link"],
 *     async run(sample, ctx) { ... }      // ctx.reports has earlier stages' reports
 *   }
 *
 * `run` returns { report, signatureMatch? }. Throwing marks only this stage
 * as failed (use an error with a `.code`, like AnalyzerError/StageHttpError);
 * later stages still run, because one team's stage being down should not
 * hide another's result.
 */

const config = require("../config");
const { runAnalyzer } = require("../analyzer/runAnalyzer");
const { getCatalog } = require("../signatures/catalog");
const { detonate } = require("../stages/sandboxClient");
const { callStage } = require("../stages/httpStage");
const { toMlReport, checkSandboxResponse } = require("../adapters/sandboxToMl");

const signatureStage = {
  name: "signature",
  appliesTo: ["file", "link"],
  async run(sample) {
    const catalog = getCatalog();
    const match =
      sample.submission_type === "link" ? catalog.matchUrl(sample.submitted_url) : catalog.matchHash(sample.sha256);
    return {
      signatureMatch: Boolean(match),
      report: {
        matched: Boolean(match),
        checked: sample.submission_type === "link" ? "url" : "sha256",
        match: match || null,
      },
    };
  },
};

// The static analyzer (malware_detection/analyze.py, or the mock) extracts PE
// features. It is the input the static ML stage will score, not a verdict.
const staticAnalysisStage = {
  name: "static_analysis",
  appliesTo: ["file"],
  async run(sample) {
    return { report: await runAnalyzer(sample.stored_path) };
  },
};

// Detonates the uploaded file in the team's sandbox VM
// (dynamic_telemetry/api.py) and stores its raw response. Files only: the
// sandbox can't render links yet (Week 8 in the plan).
function createSandboxStage({ url, detonationSeconds, timeoutMs, detonateFn = detonate }) {
  return {
    name: "sandbox",
    appliesTo: ["file"],
    async run(sample) {
      const response = await detonateFn(url, sample.stored_path, {
        filename: sample.original_filename || undefined,
        detonationSeconds,
        timeoutMs,
      });
      // Fail here, not in behavioral_ml, if the run produced no usable
      // telemetry (e.g. the Sysmon log never came back from the VM).
      checkSandboxResponse(response);
      return { report: response };
    },
  };
}

// Scores the sandbox telemetry with the ML team's service
// (ML/predict.py --serve), via the adapter in src/adapters/sandboxToMl.js.
function createBehavioralMlStage({ url, timeoutMs, callFn = callStage }) {
  return {
    name: "behavioral_ml",
    appliesTo: ["file"],
    async run(sample, ctx) {
      const sandboxReport = ctx.reports.sandbox;
      if (!sandboxReport) {
        const err = new Error("No sandbox report to score (the sandbox stage did not complete)");
        err.code = "NO_SANDBOX_REPORT";
        throw err;
      }
      const { report: mlInput, notes } = toMlReport(sandboxReport);
      const result = await callFn(url, mlInput, { timeoutMs });
      return { report: { ...result, input_summary: mlInput.summary, adapter_notes: notes } };
    },
  };
}

// Still to come, in pipeline order: static_ml (FR03) after static_analysis,
// llm (FR06) at the end.
const stages = [signatureStage, staticAnalysisStage];

// The sandbox and behavioral ML stages are off unless SANDBOX_URL is set, so
// the backend still runs (and its tests still pass) without the sandbox VM.
if (config.sandboxUrl) {
  stages.push(
    createSandboxStage({
      url: new URL("/detonate", config.sandboxUrl).href,
      detonationSeconds: config.sandboxDetonationSeconds,
      timeoutMs: config.sandboxTimeoutMs,
    }),
    createBehavioralMlStage({ url: config.behavioralMlUrl, timeoutMs: config.behavioralMlTimeoutMs })
  );
}

module.exports = { stages, signatureStage, staticAnalysisStage, createSandboxStage, createBehavioralMlStage };
