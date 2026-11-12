"use strict";
// Synthetic UI fixtures only. They do not represent a live sandbox detonation.
function complete(id = 1) {
  return {
    sample_id: id, original_filename: "Synthetic sample.exe", submission_type: "file",
    sha256: "a".repeat(64), created_at: "2026-11-10T15:00:00Z", status: "completed", signature_match: true,
    results: [
      { stage: "signature", status: "complete", report: { matched: true, match: { name: "Synthetic signature" } } },
      { stage: "sandbox", status: "complete", report: {
        metadata: { synthetic: true }, summary: { processes_created: 3, network_connections: 2,
          dns_queries: 2, files_created: 4, registry_modifications: 12 },
        processes: [{ image: "sample.exe", command_line: '<img src=x onerror="window.injected=true">', parent: "explorer.exe", pid: "123" }],
        network: [{ dest_ip: "192.0.2.10", dest_port: "443", protocol: "tcp" }],
        dns: [{ query_name: "fixture.example.test" }], file_drops: [{ target_filename: "sample.dat" }],
        registry: [{ target_object: "HKCU\\Software\\Example\\Run", details: "sample.exe" }],
      } },
      { stage: "behavioral_ml", status: "complete", report: { risk_score: .72, risk_level: "high", threshold: .26,
        prediction_source: "trained_model", anomaly_prediction: "anomaly", anomaly_score: -.17,
        evidence: ['Synthetic evidence: <img src=x onerror="window.injected=true">', "Persistence-related behavior detected"] } },
    ],
  };
}
function raw() {
  const sample = complete(), current = sample.results[1].report;
  sample.results[1].report = {
    metadata: current.metadata,
    summary: { process_count: 3, network_count: 2, dns_count: 2, file_drops_count: 4, registry_count: 12 },
    telemetry: Object.fromEntries(["processes", "network", "dns", "file_drops", "registry"].map(key => [key, current[key]])),
  };
  return sample;
}
module.exports = { complete, raw };
