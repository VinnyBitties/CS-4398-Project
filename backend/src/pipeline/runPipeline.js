"use strict";

const store = require("../store/sampleStore");
const { stages: defaultStages } = require("./stages");

/**
 * Run every applicable stage for one sample, recording a `results` row per
 * stage: inserted as 'running' when the stage starts (so a client polling
 * mid-scan can see which stage is in progress) and updated to 'complete' or
 * 'failed' when it ends.
 *
 * A stage that throws is recorded as failed and the pipeline carries on.
 * This function itself only rejects on something unexpected (e.g. the
 * database), which the queue records as a failed job.
 */
async function runPipeline(sampleId, stages = defaultStages) {
  const sample = store.getSampleRow(sampleId);
  if (!sample) throw new Error(`Sample ${sampleId} does not exist`);

  // A retried job (server restarted mid-scan) starts its stages over.
  store.stmts.deleteRunningResults.run(sample.id);

  const ctx = { reports: {} };
  for (const stage of stages) {
    if (!stage.appliesTo.includes(sample.submission_type)) continue;

    const resultId = store.stmts.startResult.run(sample.id, stage.name).lastInsertRowid;
    try {
      const out = (await stage.run(sample, ctx)) || {};
      ctx.reports[stage.name] = out.report ?? null;
      store.stmts.finishResult.run(
        "complete",
        typeof out.signatureMatch === "boolean" ? Number(out.signatureMatch) : null,
        out.report === undefined ? null : JSON.stringify(out.report),
        null,
        resultId
      );
    } catch (err) {
      store.stmts.finishResult.run(
        "failed",
        null,
        null,
        JSON.stringify({
          code: err.code || "STAGE_ERROR",
          message: err.message,
          details: err.details || null,
        }),
        resultId
      );
    }
  }
}

module.exports = { runPipeline };
