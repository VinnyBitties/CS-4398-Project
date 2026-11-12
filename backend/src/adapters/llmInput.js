"use strict";

/**
 * Builds the input for the LLM/Threat Intelligence component
 * (llm-threat-intelligence/) from a sample and the reports of the stages
 * that ran before it.
 *
 * `report` matches what llm_analyzer.build_security_prompt() reads:
 *   filename, sha256, static_analysis, ml_analysis, dynamic_analysis
 * plus a few fields it ignores today but may use later (submission_type,
 * url, signature). A stage that didn't run or failed contributes {}.
 *
 * `indicators` are what threat_intel.analyze_indicator() looks up:
 * the file hash, the submitted URL and its host, and the public domains and
 * IPs the sample contacted in the sandbox.
 */

const net = require("node:net");

// Sandbox telemetry can run to thousands of events; the prompt only needs
// enough to show what the sample did.
const MAX_EVENTS_PER_LIST = 25;
const MAX_INDICATORS = 50;

function trimTelemetry(telemetry) {
  if (!telemetry || typeof telemetry !== "object") return {};
  const trimmed = {};
  const omitted = {};
  for (const [key, value] of Object.entries(telemetry)) {
    if (Array.isArray(value) && value.length > MAX_EVENTS_PER_LIST) {
      trimmed[key] = value.slice(0, MAX_EVENTS_PER_LIST);
      omitted[key] = value.length - MAX_EVENTS_PER_LIST;
    } else {
      trimmed[key] = value;
    }
  }
  if (Object.keys(omitted).length) trimmed.omitted_events = omitted;
  return trimmed;
}

// Loopback, private, link-local and unspecified addresses say nothing a
// threat feed can look up.
function isPublicIp(ip) {
  const version = net.isIP(ip);
  if (version === 4) {
    const [a, b] = ip.split(".").map(Number);
    return !(
      a === 0 ||
      a === 10 ||
      a === 127 ||
      (a === 169 && b === 254) ||
      (a === 172 && b >= 16 && b <= 31) ||
      (a === 192 && b === 168) ||
      a >= 224
    );
  }
  if (version === 6) {
    const lower = ip.toLowerCase();
    return !(lower === "::" || lower === "::1" || /^f[cd]/.test(lower) || /^fe[89ab]/.test(lower));
  }
  return false;
}

function collectIndicators(sample, reports) {
  const seen = new Set();
  const indicators = [];
  function add(indicator, type) {
    if (typeof indicator !== "string") return;
    const value = indicator.trim().replace(/\.$/, "");
    if (!value || indicators.length >= MAX_INDICATORS) return;
    const key = `${type}:${value.toLowerCase()}`;
    if (seen.has(key)) return;
    seen.add(key);
    indicators.push({ indicator: value, type });
  }

  if (sample.submission_type === "file") {
    add(sample.sha256, "hash");
  } else if (sample.submitted_url) {
    add(sample.submitted_url, "url");
    try {
      const host = new URL(sample.submitted_url).hostname.replace(/^\[|\]$/g, "");
      if (net.isIP(host)) {
        if (isPublicIp(host)) add(host, "ip");
      } else {
        add(host, "domain");
      }
    } catch (_) {
      /* the route already validated the URL; nothing more to extract */
    }
  }

  const telemetry = (reports.sandbox && reports.sandbox.telemetry) || {};
  for (const event of Array.isArray(telemetry.dns) ? telemetry.dns : []) {
    if (event && typeof event.query === "string" && !net.isIP(event.query)) add(event.query, "domain");
  }
  for (const event of Array.isArray(telemetry.network) ? telemetry.network : []) {
    if (event && isPublicIp(event.dest_ip)) add(event.dest_ip, "ip");
  }
  return indicators;
}

function buildLlmInput(sample, reports = {}) {
  const ml = {};
  if (reports.static_ml) ml.static = reports.static_ml;
  if (reports.behavioral_ml) ml.behavioral = reports.behavioral_ml;

  const sandbox = reports.sandbox;
  const dynamic = sandbox ? { summary: sandbox.summary || {}, telemetry: trimTelemetry(sandbox.telemetry) } : {};

  return {
    report: {
      filename: sample.original_filename || sample.submitted_url || "Unknown",
      submission_type: sample.submission_type,
      sha256: sample.submission_type === "file" ? sample.sha256 : null,
      url: sample.submitted_url || null,
      signature: reports.signature || {},
      static_analysis: reports.static_analysis || {},
      ml_analysis: ml,
      dynamic_analysis: dynamic,
    },
    indicators: collectIndicators(sample, reports),
  };
}

module.exports = { buildLlmInput, collectIndicators, isPublicIp, MAX_EVENTS_PER_LIST, MAX_INDICATORS };
