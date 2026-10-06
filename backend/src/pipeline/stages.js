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

const { runAnalyzer } = require("../analyzer/runAnalyzer");
const { getCatalog } = require("../signatures/catalog");

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

// Not wired in yet, in pipeline order: static_ml (FR03), sandbox,
// behavioral_ml (FR05, via src/stages/httpStage.js), llm (FR06).
const stages = [signatureStage, staticAnalysisStage];

module.exports = { stages };
