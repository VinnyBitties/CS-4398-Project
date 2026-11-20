"""One versioned static + dynamic feature extractor for training and inference.

Missing evidence is an error, never a zero-valued behavior. Zero counts are
valid only inside an identity-bound, successfully collected observation.
"""
import datetime as dt
import math
import re
import uuid
import hashlib
from pathlib import Path

SCHEMA_VERSION = "cfd-static-dynamic-rf-v2"
INPUT_VERSION = "cfd-unified-input-v1"
STATIC_COLUMNS = ["static_file_size", "static_section_count", "static_mean_entropy", "static_max_entropy",
    "static_executable_sections", "static_writable_executable_sections", "static_imported_dll_count",
    "static_imported_api_count", "static_string_count", "static_is_dll", "static_is_pe64"]
DYNAMIC_COLUMNS = ["dynamic_process_count", "dynamic_network_count", "dynamic_dns_count",
    "dynamic_file_count", "dynamic_registry_count", "dynamic_remote_thread_count", "dynamic_observation_seconds"]
FEATURE_COLUMNS = STATIC_COLUMNS + DYNAMIC_COLUMNS
LISTS = ("processes", "network", "dns", "file_drops", "registry", "remote_threads")
EXTRACTOR_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class InputError(ValueError):
    def __init__(self, code, message):
        super().__init__(message); self.code = code


def require(condition, code, message):
    if not condition: raise InputError(code, message)


def number(value, name, maximum=1e9):
    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum,
        "MISSING_OR_INVALID_FEATURE", "Required numeric feature is missing or invalid: " + name)
    return float(value)


def boolean(value, name):
    require(type(value) is bool, "MISSING_OR_INVALID_FEATURE", "Required boolean feature is missing: " + name)
    return float(value)


def canonical_guid(value, *, allow_zero=False):
    try: valid = isinstance(value, str) and str(uuid.UUID(value)) == value and (allow_zero or uuid.UUID(value).int != 0)
    except (ValueError, TypeError, AttributeError): valid = False
    require(valid, "ATTRIBUTION_UNAVAILABLE", "An event actor or parent process GUID is missing or invalid.")
    return value


def attributed_counts(telemetry, collection, start, end):
    """Native Sysmon events only; GUID graph, never whole-guest/PID matching."""
    require(collection.get("attribution_schema") == "cfd-process-guid-v1", "ATTRIBUTION_UNAVAILABLE",
        "Complete actor/parent GUID preservation is required for sample-tree features.")
    root_guid = canonical_guid(collection.get("sample_process_guid"))
    processes, children = {}, {}
    for event in telemetry["processes"]:
        require(isinstance(event, dict), "ATTRIBUTION_UNAVAILABLE", "Invalid process observation.")
        guid = canonical_guid(event.get("process_guid"))
        parent = canonical_guid(event.get("parent_process_guid"), allow_zero=True)
        require(guid not in processes and guid != parent, "ATTRIBUTION_UNAVAILABLE", "Duplicate or self-parented process observation.")
        processes[guid] = event
        children.setdefault(parent, []).append(guid)
    require(root_guid in processes, "ATTRIBUTION_UNAVAILABLE", "Verified root process is missing.")

    def event_time(event):
        try: timestamp = dt.datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise InputError("ATTRIBUTION_UNAVAILABLE", "Event observation timestamp is missing or invalid.") from None
        require(timestamp.tzinfo is not None and start <= timestamp <= end, "ATTRIBUTION_UNAVAILABLE",
            "Event observation lies outside the verified collection window.")
        return timestamp

    root_start = event_time(processes[root_guid])
    scope, pending = {root_guid}, [root_guid]
    while pending:
        parent = pending.pop()
        for child in children.get(parent, []):
            require(child not in scope and event_time(processes[child]) >= event_time(processes[parent]),
                "ATTRIBUTION_UNAVAILABLE", "Invalid process-tree chronology or cycle.")
            scope.add(child); pending.append(child)
    counts = [float(len(scope))]
    for name in LISTS[1:]:
        count = 0
        for event in telemetry[name]:
            require(isinstance(event, dict), "ATTRIBUTION_UNAVAILABLE", "Invalid actor observation.")
            actor = canonical_guid(event.get("source_process_guid" if name == "remote_threads" else "process_guid"))
            timestamp = event_time(event)
            if actor in scope:
                require(timestamp >= event_time(processes[actor]), "ATTRIBUTION_UNAVAILABLE",
                    "Actor event precedes its process creation.")
                count += 1
        counts.append(float(count))
    duration = (end - root_start).total_seconds()
    require(duration > 0, "INPUTS_INCOMPLETE", "The sample has no observed execution window.")
    return counts + [duration]


def extract(payload):
    require(isinstance(payload, dict) and payload.get("schema_version") == INPUT_VERSION,
        "INPUT_SCHEMA_MISMATCH", "Unified input schema is not supported.")
    sha, run = payload.get("sha256"), payload.get("run_id")
    require(isinstance(sha, str) and re.fullmatch("[a-f0-9]{64}", sha), "IDENTITY_MISMATCH", "Sample SHA-256 is required.")
    try: valid_run = str(uuid.UUID(run)) == run
    except (ValueError, TypeError, AttributeError): valid_run = False
    require(valid_run, "IDENTITY_MISMATCH", "A canonical analysis run UUID is required.")
    reports = []
    for name in ("static", "dynamic"):
        evidence = payload.get(name)
        require(isinstance(evidence, dict) and evidence.get("sha256") == sha and evidence.get("run_id") == run,
            "IDENTITY_MISMATCH", "Static and dynamic evidence must belong to the same sample and run.")
        report = evidence.get("report")
        require(isinstance(report, dict), "INPUTS_INCOMPLETE", name + " evidence is missing.")
        reports.append(report)
    static, dynamic = reports
    require(static.get("sha256") == sha, "IDENTITY_MISMATCH", "Static evidence hash does not match.")
    require(static.get("schema_version") in {"1.0.0", "1.1.0", "1.2.0"}, "STATIC_SCHEMA_MISMATCH", "Static evidence schema is unsupported.")
    collection = dynamic.get("collection", {})
    require(dynamic.get("job_id") == run and collection.get("job_id") == run and collection.get("sha256") == sha,
        "IDENTITY_MISMATCH", "Dynamic collection identity does not match.")
    require(collection.get("status") == "complete" and dynamic.get("cleanup", {}).get("status") == "complete"
        and collection.get("collector_version") == "cfd-sysmon-v1", "INPUTS_INCOMPLETE", "Verified complete telemetry and cleanup are required.")
    coverage = collection.get("sysmon_event_ids")
    require(isinstance(coverage, list) and all(type(x) is int for x in coverage) and {1, 3, 8, 11, 12, 13, 22}.issubset(coverage),
        "INPUTS_INCOMPLETE", "Required Sysmon coverage is missing.")
    require(isinstance(collection.get("raw_sha256"), str) and re.fullmatch("[a-f0-9]{64}", collection["raw_sha256"]),
        "INPUTS_INCOMPLETE", "Raw telemetry checksum is missing.")
    telemetry = dynamic.get("telemetry", {})
    require(isinstance(telemetry, dict) and not telemetry.get("parse_error") and all(isinstance(telemetry.get(name), list)
        and len(telemetry[name]) <= 50000 for name in LISTS), "INPUTS_INCOMPLETE", "A required telemetry event list is missing or invalid.")
    launches = [event for event in telemetry["processes"] if isinstance(event, dict)
        and event.get("attribution") == "verified_sample_launch"
        and event.get("process_guid") == collection.get("sample_process_guid")]
    require(bool(collection.get("sample_process_guid")) and len(launches) == 1,
        "INPUTS_INCOMPLETE", "The verified sample launch is missing.")
    try:
        start = dt.datetime.fromisoformat(collection["started_at"].replace("Z", "+00:00"))
        end = dt.datetime.fromisoformat(collection["finished_at"].replace("Z", "+00:00"))
        duration = (end - start).total_seconds()
        require(start.tzinfo is not None and end.tzinfo is not None and 0 < duration <= 300,
            "INPUTS_INCOMPLETE", "Observation window is invalid.")
    except (KeyError, ValueError, TypeError, AttributeError):
        raise InputError("INPUTS_INCOMPLETE", "Observation timestamps are missing or invalid.") from None
    sections, summary, pe = static.get("sections"), static.get("summary", {}), static.get("pe", {})
    require(isinstance(sections, list) and 0 < len(sections) <= 96 and all(isinstance(s, dict) for s in sections),
        "MISSING_OR_INVALID_FEATURE", "PE sections are missing or invalid.")
    count = number(summary.get("section_count"), "section_count", 96)
    require(count == len(sections), "MISSING_OR_INVALID_FEATURE", "Static section count does not match extracted sections.")
    entropy = [number(row.get("entropy"), "section_entropy", 8) for row in sections]
    executable = [boolean(row.get("executable"), "section_executable") for row in sections]
    writable = [boolean(row.get("writable"), "section_writable") for row in sections]
    require(pe.get("format") in {"PE32", "PE32+"}, "MISSING_OR_INVALID_FEATURE", "PE format is missing or unsupported.")
    values = [number(static.get("file_size"), "file_size", 25 * 1024 ** 2), count, sum(entropy) / count, max(entropy),
        sum(executable), sum(a * b for a, b in zip(executable, writable)),
        number(summary.get("imported_dll_count"), "imported_dll_count"), number(summary.get("imported_api_count"), "imported_api_count"),
        number(summary.get("string_count"), "string_count"), boolean(pe.get("is_dll"), "is_dll"), float(pe["format"] == "PE32+")]
    values += attributed_counts(telemetry, collection, start, end)
    return dict(zip(FEATURE_COLUMNS, values))
