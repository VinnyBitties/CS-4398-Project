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

Split before training, then choose the classifier threshold on validation data:

```powershell
python ML/split_dataset.py --data data/records.json --out-dir data/splits --seed 42
python ML/train_classifier.py --data data/splits/train.json --model-out models/random_forest.joblib
python ML/train_anomaly.py --data data/splits/train_benign.json --model-out models/isolation_forest.joblib
python ML/tune_threshold.py --validation-data data/splits/validation.json --model models/random_forest.joblib --out models/threshold.json
$mlThreshold = (Get-Content models/threshold.json -Raw | ConvertFrom-Json).threshold
python ML/evaluate.py --data data/splits/test.json --model models/random_forest.joblib --model-type classifier --threshold $mlThreshold
python ML/evaluate.py --data data/splits/test.json --model models/isolation_forest.joblib --model-type anomaly
python ML/predict.py --serve --classifier-model models/random_forest.joblib --anomaly-model models/isolation_forest.joblib --threshold $mlThreshold
```

Splitting defaults to 60% training, 20% validation, and 20% test within each
class, with rounding and at least one record of each class per partition.
`--validation-fraction` and `--test-fraction` customize the proportions. Small
datasets that cannot populate all partitions are rejected. `split_info.json`
records the seed, fractions, and actual counts. Existing split files are not
overwritten. `train_benign.json` is a subset of training only, not a fourth
independent partition.

Training and evaluation require integer labels 0 or 1; strings, booleans, and
fractional labels are rejected. The classifier requires both classes. The
anomaly trainer requires every record to be explicitly labeled 0 and rejects
mixed or unlabeled input rather than silently training on malicious examples.

Threshold tuning maximizes malicious-class F1 on validation probabilities.
Ties prefer the threshold closest to 0.5, then the higher threshold. The JSON
output records the selected value, validation F1, model path, and validation
input path. Evaluation and serving must receive that same threshold explicitly;
they do not automatically read the threshold file. The anomaly model keeps
its own fitted decision boundary; its output is not a malware probability.

Keep test data untouched until the model and threshold choices are final.
The tools cannot tell whether a caller mislabeled a training file as validation.
Splitting rejects identical reports and repeated job IDs to catch simple
duplication. Different runs of the same real sample, malware family, or other
related groups must be grouped before splitting real datasets; this random
record splitter does not establish independence between those groups.

All metrics on generated data remain synthetic demonstration results, not
evidence of real-world malware detection accuracy.

## Prediction sources and service health

`prediction_source` describes the source of `risk_score`, `risk_level`, and
`malicious`. It is `trained_model` only when a classifier supplies the verdict;
otherwise it is `heuristic`, even if an anomaly detector is loaded.
`anomaly_source` is `trained_model` when an anomaly detector is loaded and
`null` otherwise. The separate `anomaly_prediction` and `anomaly_score` fields
never replace the main verdict. An anomaly is unusual behavior, not proof of malware.

Prediction responses and `GET /health` include the active threshold, runtime
`feature_schema_version`, and `models.classifier` / `models.anomaly` information:
loaded status, estimator type, artifact version, recorded feature-schema
version, and whether that schema was verified. `/health` returning `status: ok`
means the service is running; check `models` to see whether it has trained models.

Artifact versions are SHA-256 hashes of the exact `.joblib` bytes loaded at
startup. Models supplied directly as Python objects have a null artifact
version unless loaded through `predict.load_model`. No local model paths are
exposed through these responses.

Both trainers now save the feature-schema version and ordered feature names
inside their estimators. The predictor rejects known incompatible schemas or
feature counts before starting the server. Older models without schema metadata
remain supported but report `schema_verified: false` and a null recorded schema
version; matching feature counts alone cannot verify extraction semantics.
Retrain to attach the current schema. Increment `FEATURE_SCHEMA_VERSION` when
feature ordering or extraction semantics change. These schema checks apply to
the predictor; evaluation and threshold tuning still load estimators directly.
