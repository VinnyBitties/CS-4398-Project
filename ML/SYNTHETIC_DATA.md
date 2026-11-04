# Synthetic sandbox reports

`synthetic_reports.py` adapts Diego's `ML/synthetic-reports.py` generator to
the normalized Sysmon report contract accepted by `report_parser.py` and
produced by the backend adapter. The underscore filename supports normal
Python imports and matches the original generator's documented command.

Run from the repository root:

```powershell
python ML/synthetic_reports.py --count 300 --seed 42
python ML/build_dataset.py --manifest data/manifest.csv --out data/records.json
python ML/build_dataset.py --manifest data/manifest.csv --out data/features.csv
```

The first command creates 300 reports in `data/synthetic_reports` and a CSV
manifest with `report_path,label` columns. Labels are 0 (benign) and 1
(malicious). `--malicious-ratio` defaults to 0.5; the malicious count is
`round(count * ratio)`, and labels are shuffled. All report content is
reproducible with the same seed and arguments. Manifest paths are absolute
local paths; regenerate the manifest when moving the dataset to another machine.

Use a new `--out-dir` and `--manifest` for another dataset. Existing report
files and manifests are not overwritten. Generated data is not required to
be committed to reproduce a run.

Each report contains summary counts derived from its event arrays, process
command lines, registry `target_object` paths, DNS `query_name`, network
destinations, and file events. Signatures are empty because the current
sandbox adapter does not produce them. Remote-thread events remain empty
to match the adapter's uncaptured default. Every report includes at least
one process event and a synthetic-data marker with a generator version.

Both classes contain quiet and active scenarios. Benign examples may include
network traffic, registry writes, autorun entries, task creation, or task
queries. Malicious examples include low-activity scenarios as well as autorun
and task creation/change events. All commands are inert report strings;
the generator does not execute them or contact network destinations.

These labels and scenario distributions are invented. Some examples from
different classes deliberately have indistinguishable feature vectors.
Synthetic evaluation measures behavior on these fixtures, not real malware
detection accuracy. This data is for pipeline development and demos.

The JSON export contains an array of `{"report": {...}, "label": 0}` records,
preserving the original reports and synthetic metadata. It is accepted directly
by `train_classifier.py`, `train_anomaly.py`, and `evaluate.py`. The feature CSV
is optional and useful for inspection; the training scripts still consume JSON.

The builder infers JSON from a `.json` output filename. `--format json` selects
JSON explicitly and defaults to `data/records.json` if `--out` is omitted.
Running without either option retains the existing `data/features.csv` default.
Manifest paths that are relative are resolved against the current working
directory, as before. The generator writes absolute paths.

Both export formats validate every report and require labels 0 or 1. Missing,
malformed, or unusable telemetry and empty manifests stop the export before
opening the output file. Reports are no longer silently skipped. Successful
exports replace an existing output at the requested path.

To check classifier training after exporting JSON:

```powershell
python ML/train_classifier.py --data data/records.json --model-out data/random_forest.joblib
```

For Isolation Forest, export a manifest containing only benign training reports
and pass that JSON file to `train_anomaly.py`. The current anomaly trainer does
not enforce benign-only input. Use separate training, validation, and test
datasets for evaluation; automatic splitting and training-side validation are
the separate priority 4 changes. These exports alone do not train a model.
