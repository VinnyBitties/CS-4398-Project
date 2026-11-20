# CFD native measurement handoff

This is a copy of genuine retained measurements, not synthetic data, a new
collection, or a training run. No model, executable sample, sample archive,
dropped file, credential file, private key, or operational configuration is
included. Treat report text as untrusted observations, not commands to run.

## Dataset boundaries

| Folder | Records | Benign label (0) | Malicious label (1) |
|---|---:|---:|---:|
| development | 287 | 133 | 154 |
| historical-test | 96 | 50 | 46 |

Development combines the original 177 accepted records, an earlier 50-record
independent test already consumed for development, and 60 v3 additions (54
original additions, five supplement-01, one supplement-02). Entropy/managed views
support 286 development records; the remaining record is retained and supports
the target-only view. Consult explicit feature availability.

**historical-test is not training data.** These 96 records were independently
evaluated on November 20, 2026. That evaluation and failed release decision remain
historical evidence. Training, tuning, feature design, threshold selection, or
error-driven changes informed by these records require a new, untouched
independent test afterward. Do not describe revised results here as independent
validation. SHA and software-group separation between the two folders was checked.

## Files and provenance

Each dataset contains:

- manifest.json / manifest.csv: SHA-256, actual run ID, publisher label, label
  source/confidence, software group, original split, source references and report
  paths. Hashes, run IDs, groups, labels, sources and paths are NOT predictors.
- records/<sha>/static-analysis.json: actual static report, including retained
  strings, imports and sections. This is not a model summary.
- sandbox-telemetry.json: complete normalized native sandbox report copied from
  the retained input's /dynamic/report, including sample and background telemetry,
  capture evidence and cleanup.
- native-input.json: actual retained static/dynamic input envelope with SHA/run
  binding and both report objects.
  Its static report includes the recorded run/SHA evidence binding added after
  static analysis; the separate original static report need not contain that
  binding. Their measurement values are verified equal.
- managed-metadata.json: existing recorded CLI supplement; no executable is
  needed to reproduce report-based features.
- capture-quality.json and capture-quality-index.json: clock/window evidence,
  attribution, cleanup, collection status and support/rejection per feature view.
- features-{targets,entropy,managed,categories,native-v2}.csv: SHA and run ID,
  then named numeric predictors in exact extractor order. Every retained record
  appears in every CSV. Unsupported views have EMPTY predictor cells, never zeros.
- report-provenance.json: source file checksum, JSON pointer for projections,
  export checksum, and redaction/reserialization status.

development/splits preserves actual original native partitions and latest
grouped development folds with their original SHA order. Original train,
validation and test membership is historical; all 287 are now development.
No split or fold has been invented.

source-files.json records original manifests, inputs, reports, supplements and
code hashes; they were rechecked after export. Full operational manifests are not
copied wholesale: handoff rows identify their exact source JSON entry.
checksums.json covers every package file except itself. The ZIP has a separate
checksum. export-summary.json records counts and verification.

## Feature definitions

code/ contains byte-identical server sources: native_release_features.py,
native_features_semantic.py, native_features.py, unified_features.py,
managed_metadata.py and release_grouping.py. Exact versions, hashes, order and
groups are in feature-schema.json. Replay uses Python's standard library.

Column names containing "log" mean natural log1p(x), NOT log10.
The selected managed contract has 12 static and six behavioral predictors:

| Predictor | Measurement before any log1p |
|---|---|
| static_log_file_size | Submitted PE size in bytes |
| static_section_count | PE section count |
| static_weighted_entropy | Section entropy weighted by raw byte size, bits/byte |
| static_max_entropy | Maximum recorded section entropy, bits/byte |
| static_log_imported_dll_count | Recorded imported DLL entry count |
| static_log_imported_api_count | Recorded imported API entry count |
| static_log_string_density_per_kib | String count times 1024 / PE size |
| static_executable_section_weighted_entropy | Raw-size-weighted executable-section entropy |
| static_cli_present | Recorded CLI presence, 0/1 or unknown |
| static_log_cli_declared_type_refs | Declared CLI TypeRef row count |
| static_log_cli_declared_methods | Declared CLI MethodDef row count |
| static_cli_measurement_unavailable | Explicit unavailable-CLI flag |
| dynamic_log_child_process_count | Sample-tree process count minus verified root |
| dynamic_log_network_count | Attributed native Sysmon network-event count |
| dynamic_log_unique_dns_targets | Distinct normalized attributed DNS targets |
| dynamic_log_unique_file_targets | Distinct normalized attributed file-create targets |
| dynamic_log_unique_registry_targets | Distinct normalized attributed registry targets |
| dynamic_archive_named_create_observed | Attributed file-create target with archive suffix |

targets omits executable entropy and CLI (7 static + 6 behavioral). entropy adds
executable entropy (8 + 6). categories adds dynamic_executable_named_create_observed
(.exe/.dll/.sys/.scr suffixes) and dynamic_autorun_location_observed (the frozen
Run/RunOnce target rules). Names do not establish contents, persistence or intent.
native-v2 preserves the 7-static/5-behavioral count contract: DNS/file/registry
columns count events instead of distinct targets. Do not interchange columns.
CSV headers and included source code are authoritative.

Export uses the original pinned Python 3.11.2 analysis runtime and compares
previously saved feature values exactly. Python 3.12+ changed floating-point
summation, which can cause last-bit replay differences. The portable verifier
uses 1e-12 absolute/relative tolerance for numerical replay only; file checksums,
null/support handling and identity checks remain exact. CSV values are not rounded.

Behavior uses the first measured **30 seconds after verified sample launch**.
Boundaries use guest UTC; host and guest clocks are not subtracted. Collection
must begin before launch and cover the complete window. Raw captures can be longer
and include unrelated Windows activity. Process GUIDs and parent GUIDs identify
the sample root and descendants; only attributed events enter predictors. PID
alone is insufficient. Sysmon counts are not CAPE API-call counts.

Zero activity is valid only after identity, capture, window, attribution and
cleanup checks. Missing telemetry is unavailable, never a benign zero.
One record has UNDEFINED_EXECUTABLE_ENTROPY: no measured executable-section
bytes. It remains target-view eligible. Explicitly unavailable CLI measurements
remain null for three CLI values, with the unavailable flag set. Export does not
impute. Any future imputer must be fit inside training folds only.
Process creation is verified; successful application initialization and exit
status are not fully measured. Quiet malicious-labeled records remain present.
Capture duration and health are quality metadata, not predictors.

## Labels, scope and redactions

Source: https://huggingface.co/datasets/Thcrull/win-exe-malware-analysis
Pinned revision: dbda5905c9dd0cb00acdc33d9a63dd5000381e16.
Labels are unverified publisher source-category labels, NOT Qwen/Groq predictions
or independently adjudicated ground truth. Source/class confounding remains;
unknown software relatives may remain. The dataset card was recorded as MIT;
third-party rights remain with their owners. No executable or publisher CAPE
payload is redistributed.

The population is security-permitted, supported, complete native captures, not
inputs refused by Windows protection or missing measurements. Historical-test
accepted 96 instead of the intended 100. Do not infer broad reliability or call
uncalibrated model scores malware probabilities.

No numeric measurement is changed. Credential-like values, key material and long
opaque potentially binary encodings are conservatively replaced with distinct
SHA-based markers, without decoding. This can remove non-executable encodings too.
redactions.json lists the file, JSON pointer, reason, length and original text
hash without exposing removed values. All other report values/strings remain.
Unchanged JSON retains original bytes; projected/redacted copies are identified
in provenance. Every feature view was replayed before and after redaction.
Server evidence was only read and remains intact.

## Loading and verification

From this directory, run: python -B verify_handoff.py

The verifier checks checksums, counts, report/SHA/run alignment, group separation,
column order, unavailable handling, and feature replay. It never trains,
downloads, or executes samples.

Optional pandas example:

    import json
    from pathlib import Path
    import pandas as pd
    root = Path(".")
    schema = json.loads((root / "feature-schema.json").read_text())
    meta = pd.read_csv(root / "development/manifest.csv")
    features = pd.read_csv(root / "development/features-managed.csv")
    data = meta.merge(features, on=["sample_sha256", "run_id"], validate="one_to_one")
    X = data[schema["managed"]["columns"]]
    y = data["publisher_label"]
    groups = data["software_group"]

Use feature_availability to select supported rows; do not blindly drop all nulls
because supported CLI inputs can intentionally be unknown. Preserve software
groups in development splits. Keep historical-test separate.
