"use strict";

/**
 * Translate the sandbox service's /detonate response into the report shape
 * the behavioral ML service (ML/report_parser.py on the ML-Axel branch)
 * accepts.
 *
 * Why this exists: the two were built against different shapes and nothing
 * else translates between them yet.
 *
 *   Sandbox (dynamic_telemetry/api.py)      ML (report_parser.normalize_report)
 *   ---------------------------------       -----------------------------------
 *   filename                                original_filename
 *   summary.process_count                   summary.processes_created
 *   summary.network_count                   summary.network_connections
 *   summary.dns_count                       summary.dns_queries
 *   summary.file_drops_count                summary.files_created
 *   summary.registry_count                  summary.registry_modifications
 *   (not captured)                          summary.remote_threads_injected
 *   telemetry.{processes,network,...}       top-level processes, network, ...
 *   telemetry.dns[].query                   dns[].query_name
 *
 * If the sandbox and ML teams later agree on one shape, a report that is
 * already in the ML shape is passed through untouched, so this file can be
 * deleted without anything else changing.
 */

class SandboxReportError extends Error {
  constructor(message, code, details) {
    super(message);
    this.name = "SandboxReportError";
    this.code = code; // 'BAD_SANDBOX_REPORT' | 'TELEMETRY_PARSE_ERROR'
    this.details = details || null;
  }
}

const EVENT_LISTS = ["processes", "network", "dns", "file_drops", "registry"];

// sandbox summary key -> [ML summary key, event list it counts]
const COUNT_MAP = {
  process_count: ["processes_created", "processes"],
  network_count: ["network_connections", "network"],
  dns_count: ["dns_queries", "dns"],
  file_drops_count: ["files_created", "file_drops"],
  registry_count: ["registry_modifications", "registry"],
};

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function isCount(v) {
  return Number.isInteger(v) && v >= 0;
}

function isEventList(v) {
  return Array.isArray(v) && v.every(isPlainObject);
}

/** True if the report is already in the shape report_parser.py expects. */
function isMlShape(report) {
  return isPlainObject(report) && isPlainObject(report.summary) && "processes_created" in report.summary;
}

/**
 * Check a raw /detonate response before it is stored, so a broken sandbox
 * run fails the sandbox stage instead of producing an all-zero ML score.
 * Throws SandboxReportError; returns nothing.
 */
function checkSandboxResponse(response) {
  if (!isPlainObject(response)) {
    throw new SandboxReportError("Sandbox response is not a JSON object", "BAD_SANDBOX_REPORT");
  }
  if (isMlShape(response)) return;

  const telemetry = response.telemetry;
  if (!isPlainObject(telemetry)) {
    throw new SandboxReportError("Sandbox response has no telemetry object", "BAD_SANDBOX_REPORT");
  }
  // api.py's parse_sysmon_evtx catches its own errors and returns empty event
  // lists plus parse_error. Empty lists there mean "we don't know", not
  // "nothing happened", so they must not be scored.
  if (telemetry.parse_error) {
    throw new SandboxReportError("Sandbox could not parse the Sysmon log", "TELEMETRY_PARSE_ERROR", {
      parse_error: String(telemetry.parse_error),
      job_id: response.job_id ?? null,
    });
  }
  for (const list of EVENT_LISTS) {
    if (!isEventList(telemetry[list])) {
      throw new SandboxReportError(`telemetry.${list} must be an array of event objects`, "BAD_SANDBOX_REPORT");
    }
  }
}

/**
 * Build the ML request body from a /detonate response.
 * @returns {{ report: object, notes: string[] }} notes list every value the
 *   adapter had to fill in, so the stored result says so.
 */
function toMlReport(response) {
  checkSandboxResponse(response);
  if (isMlShape(response)) return { report: response, notes: [] };

  const telemetry = response.telemetry;
  const summaryIn = isPlainObject(response.summary) ? response.summary : {};
  const notes = [];

  const summary = {};
  for (const [sandboxKey, [mlKey, list]] of Object.entries(COUNT_MAP)) {
    // The sandbox's counts are len(list) today; fall back to the list if a
    // count is ever missing rather than inventing a zero.
    summary[mlKey] = isCount(summaryIn[sandboxKey]) ? summaryIn[sandboxKey] : telemetry[list].length;
  }

  let remoteThreads = [];
  if (isEventList(telemetry.remote_threads)) {
    remoteThreads = telemetry.remote_threads;
    summary.remote_threads_injected = remoteThreads.length;
  } else {
    // Sysmon event 8 (CreateRemoteThread) is not parsed by the sandbox yet.
    summary.remote_threads_injected = 0;
    notes.push("remote_threads_injected is not captured by the sandbox yet; sent as 0");
  }

  const report = {
    job_id: response.job_id ?? null,
    original_filename: response.filename ?? null,
    timeout_seconds: response.timeout_seconds ?? null,
    summary,
    processes: telemetry.processes,
    network: telemetry.network,
    dns: telemetry.dns.map(({ query, ...rest }) =>
      query === undefined ? rest : { query_name: query, ...rest }
    ),
    file_drops: telemetry.file_drops,
    registry: telemetry.registry,
    remote_threads: remoteThreads,
    signatures: [],
  };
  return { report, notes };
}

module.exports = { toMlReport, checkSandboxResponse, SandboxReportError };
