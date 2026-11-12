# Behavioral Feature Extraction and Machine Learning

## Purpose and status

The `ML/` component validates behavioral reports, builds a nine-feature vector, produces a heuristic risk result, optionally trains/loads classifier and anomaly models, exposes CLI/HTTP inference, and evaluates labeled records. Its status is **Partial** because no dataset, model artifact, model card, or evaluation result is included, and the code is behavioral rather than the required static-PE classifier.

## Source layout

| Path | Responsibility |
| --- | --- |
| `ML/config.py` | Feature names, keywords, default paths, threshold |
| `ML/report_parser.py` | Current/legacy report validation, normalization, features, heuristic risk/evidence |
| `ML/model_utils.py` | Convert records/reports into ordered model matrices |
| `ML/build_dataset.py` | Convert a manifest of reports/labels into feature CSV |
| `ML/train_classifier.py` | Train and save a Random Forest classifier |
| `ML/train_anomaly.py` | Train and save an Isolation Forest on known-benign reports |
| `ML/predict.py` | Heuristic/model inference through CLI or HTTP |
| `ML/evaluate.py` | Classifier/anomaly metrics from labeled JSON records |
| `ML/test_report_parser.py` | Normalization, feature, validation, persistence, and parity tests |

## Input contract

The parser accepts the expected sandbox shape with a nonnegative integer summary and arrays for processes, file drops, registry events, network connections, DNS queries, and remote threads. It also supports a documented legacy behavior/network shape.

Missing telemetry, invalid counts, invalid event arrays, or invalid signatures raise errors rather than silently becoming zero activity. Summary counts are authoritative because event arrays may be abbreviated. DNS queries are not counted as network connections.

The backend's `sandboxToMl.js` adapter maps currently known sandbox field names into this shape. Once producer and consumer agree on one schema, that adapter should be reduced or removed.

## Feature schema

The ordered features are:

1. `num_processes_created`
2. `num_files_written`
3. `num_registry_keys_set`
4. `num_network_connections`
5. `num_dns_requests`
6. `num_signatures_matched`
7. `max_signature_severity`
8. `has_persistence_signature`
9. `has_network_signature`

Persistence evidence includes signature keywords and raw behaviors such as Run/RunOnce registry paths or suspicious scheduled-task commands. Network evidence includes signature keywords or observed connection/DNS counts.

## Heuristic risk

`analyze_report()` applies bounded weights to the feature counts, transforms the sum with a logistic function, and labels the result using configured risk thresholds. This is a deterministic project heuristic. It is not a trained probability, calibration result, or measured detector accuracy.

Output contains `malicious`, `risk_score`, `risk_level`, features, evidence, and `prediction_source: heuristic` when no model is supplied.

## Optional models

`train_classifier.py` fits a scikit-learn Random Forest to reports with binary labels. `train_anomaly.py` fits an Isolation Forest to known-benign reports. Both persist with joblib. Inference may load either or both:

```bash
cd ML
python3 predict.py --file sandbox_example.json \
  --classifier-model random_forest.joblib \
  --anomaly-model isolation_forest.joblib
```

Classifier output requires `predict_proba()` and a malicious class labeled `1`. When models are loaded, output identifies `prediction_source: trained_model`, classifier probability/prediction, and/or anomaly result/score.

## HTTP inference

```bash
cd ML
python3 predict.py --serve --host 127.0.0.1 --port 8000
```

- `GET /` and `GET /health` return service health.
- `POST /`, `/analyze`, or `/analyze-report` accepts one JSON report.
- Valid analysis returns JSON; invalid JSON/report/model behavior returns a JSON error with status 400.
- Other paths return 404.

The backend uses `BEHAVIORAL_ML_URL` after a successful sandbox stage. The service has no authentication, TLS, request-size limit, rate limit, model hot-reload, or production server wrapper; bind it to loopback for local development.

## Training data and evaluation

Training and evaluation expect user-supplied JSON records and model artifacts. The repository does not include:

- Dataset name/version, source, license, collection period, counts, or families.
- Labeling/deduplication methodology.
- Train/validation/test split or leakage checks.
- A trained `.joblib` artifact or artifact hash.
- Threshold selection evidence.
- Accuracy, precision, recall, F1, ROC AUC, FPR, FNR, or held-out-family result.

`evaluate.py` can compute relevant metrics after those inputs exist, but the tool's presence is not an evaluation result.

## Test evidence

`ML/test_report_parser.py` contains fifteen tests for documented and zero activity, missing/invalid counts, invalid arrays/signatures, legacy input, nonmutation, persistence evidence, missing telemetry, and CLI/HTTP model parity.

Observed on 2026-11-03: the module failed import because `joblib` was not installed. No ML assertions ran. Install the root requirements in an isolated environment and rerun before reporting a passing result.

## Security and quality notes

- Joblib model files can execute code while loading; load only trusted artifacts with recorded hashes/provenance.
- Training data and sandbox telemetry may contain sensitive paths, domains, IPs, registry values, or user identifiers.
- The simple HTTP server is for development, not untrusted networks.
- Missing data intentionally fails closed at the parser boundary instead of scoring an empty report.
- Dataset licensing, class balance, family leakage, temporal leakage, and threshold calibration must be resolved before performance claims.

## Known limitations

- No static malware classifier despite FR03.
- No bundled data, artifacts, or metrics.
- No feature importance export from trained models.
- No cross-validation or hyperparameter search in the current scripts.
- No model registry/version field in inference output.
- Behavioral input cannot be produced end to end without the absent sandbox.

## Next work

1. Create dataset and model cards with licenses, counts, families, split, leakage checks, and hashes.
2. Implement the separate static-PE feature/model contract.
3. Train and evaluate versioned behavioral artifacts with reproducible commands.
4. Run the held-out-family experiment and compare individual/layered configurations.
5. Add calibrated thresholds, feature importance, artifact validation, and production service controls.

## Related documentation

- [Dynamic-analysis integration](dynamic-analysis.md)
- [Backend component](backend.md)
- [Architecture](../architecture.md)
- [Prototype Status](../prototype-status.md)
