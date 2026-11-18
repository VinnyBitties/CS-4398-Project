/* Shared by the browser and Node regression tests; no HTML or network access. */
(function (root, factory) {
  const data = factory();
  if (typeof module === "object" && module.exports) module.exports = data;
  else root.ReportsData = data;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const STAGES = [
    ["signature", "Signature"], ["static_analysis", "Static analysis"],
    ["static_ml", "Static ML"], ["sandbox", "Sandbox"],
    ["behavioral_ml", "Behavioral ML"], ["llm", "LLM"],
  ];
  const ACTIVITY = [
    ["processes", "Processes", "processes_created", "process_count"],
    ["network", "Connections", "network_connections", "network_count"],
    ["dns", "DNS queries", "dns_queries", "dns_count"],
    ["file_drops", "Files created", "files_created", "file_drops_count"],
    ["registry", "Registry changes", "registry_modifications", "registry_count"],
  ];
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const probability = value => typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
  const active = sample => ["queued", "running"].includes(sample.status);
  const name = sample => sample.original_filename || sample.submitted_url || "Unnamed scan";
  function stage(sample, key) {
    return (Array.isArray(sample.results) ? sample.results : []).filter(r => r && r.stage === key).at(-1);
  }
  function report(sample, key) {
    const result = stage(sample, key);
    return result && result.status === "complete" && object(result.report) ? result.report : null;
  }
  function sandbox(sample) {
    const source = report(sample, "sandbox");
    const events = source && (object(source.telemetry) ? source.telemetry : source);
    const error = source && (source.error || source.parse_error || events.error || events.parse_error ||
      source.execution_succeeded === false || source.telemetry_collected === false);
    const counts = ACTIVITY.map(([key, label, normalized, raw]) => {
      const summary = source && object(source.summary) ? source.summary : {};
      const values = events && Array.isArray(events[key]) ? events[key] : null;
      const value = count(summary[normalized]) ? summary[normalized] :
        count(summary[raw]) ? summary[raw] : values ? values.length : null;
      return { key, label, value, events: values ? values.filter(object) : null };
    });
    const anyActivity = counts.some(item => item.value > 0) ||
      (source && source.summary && source.summary.remote_threads_injected > 0) ||
      (events && Array.isArray(events.remote_threads) && events.remote_threads.length > 0);
    const usable = Boolean(source && !error && anyActivity);
    let message = "Event totals from the sandbox report. Event lists may be abbreviated.";
    if (!source) message = "Unavailable — the sandbox has not returned a successful report.";
    else if (error) message = "Unavailable — sandbox execution or telemetry collection failed.";
    else if (!anyActivity) message = "Unavailable — no observed activity; this run is inconclusive.";
    return { usable, message, source, counts: counts.map(item => usable ? item : { ...item, value: null, events: null }) };
  }
  function view(sample) {
    const telemetry = sandbox(sample);
    // An explicitly failed/empty sandbox must not make historical ML output look reliable.
    const sandboxResult = stage(sample, "sandbox");
    const invalidTelemetry = sandboxResult && (sandboxResult.status === "failed" ||
      (sandboxResult.status === "complete" && !telemetry.usable));
    const ml = invalidTelemetry ? null : report(sample, "behavioral_ml");
    const risk = ml && probability(ml.risk_score) ? ml.risk_score : null;
    const signature = report(sample, "signature");
    const signatureMatch = signature ? (signature.matched ?? sample.signature_match) : null;
    const signatureName = signature && object(signature.match) && typeof signature.match.name === "string" ? signature.match.name : null;
    return {
      name: name(sample), active: active(sample), telemetry, risk,
      level: risk !== null && typeof ml.risk_level === "string" ? ml.risk_level : "Unavailable",
      source: risk === null ? "Unavailable" : ml.prediction_source === "trained_model" ? "Trained classifier" :
        ml.prediction_source === "heuristic" ? "Heuristic" : "Source not reported",
      threshold: ml && probability(ml.threshold) ? ml.threshold : null,
      anomaly: ml && ["anomaly", "known"].includes(ml.anomaly_prediction) ? ml.anomaly_prediction : null,
      anomalyScore: ml && typeof ml.anomaly_score === "number" && Number.isFinite(ml.anomaly_score) ? ml.anomaly_score : null,
      evidence: ml && Array.isArray(ml.evidence) ? ml.evidence.filter(value => typeof value === "string") : [],
      signatureMatch, signatureName,
      synthetic: Boolean(telemetry.source && telemetry.source.metadata && telemetry.source.metadata.synthetic === true),
      stages: STAGES.map(([key, label]) => {
        const result = stage(sample, key);
        const status = result && ["running", "complete", "failed"].includes(result.status) ? result.status : active(sample) ? "pending" : "not_run";
        return { key, label, status, error: status === "failed" ?
          (result.error && typeof result.error.message === "string" ? result.error.message : "This stage failed.") : null };
      }),
    };
  }
  return { STAGES, ACTIVITY, active, name, view };
});
