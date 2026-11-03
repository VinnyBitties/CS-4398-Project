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
  const sample = await store.getSampleRow(sampleId);
  if (!sample) throw new Error(`Sample ${sampleId} does not exist`);

  // A retried job (server restarted mid-scan) starts its stages over.
  await store.deleteRunningResults(sample.id);

  const ctx = { reports: {} };
  for (const stage of stages) {
    if (!stage.appliesTo.includes(sample.submission_type)) continue;

    const resultId = await store.startResult(sample.id, stage.name);
    let outcome;
    try {
      const out = (await stage.run(sample, ctx)) || {};
      ctx.reports[stage.name] = out.report ?? null;
      outcome = {
        status: "complete",
        signatureMatch: typeof out.signatureMatch === "boolean" ? Number(out.signatureMatch) : null,
        reportJson: out.report === undefined ? null : JSON.stringify(out.report),
      };
    } catch (err) {
      outcome = {
        status: "failed",
        errorMessage: JSON.stringify({
          code: err.code || "STAGE_ERROR",
          message: err.message,
          details: err.details || null,
        }),
      };
    }
    // Outside the try: a database error here is not the stage's fault, and
    // should fail the job rather than be recorded as a stage failure.
    await store.finishResult(resultId, outcome);
  }
}

module.exports = { runPipeline };
