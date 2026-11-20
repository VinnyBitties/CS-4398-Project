# Behavioral Feature Extraction and Machine Learning

## Purpose and status

`ML/` validates behavioral reports, builds a fixed nine-feature vector, produces a heuristic risk result, trains optional classifier/anomaly models, selects a validation threshold, serves CLI/HTTP inference, and evaluates labeled records. Its status is **Partial**.

The repository now has a reproducible end-to-end synthetic workflow, but it has no real dataset, committed trained artifact, model card, held-out-family result, or real-world performance evidence. The code is behavioral; it does not satisfy FR03's missing static-PE classifier.

## Source layout

| Path | Responsibility |
| --- | --- |
| `ML/config.py` | Ordered features, feature-schema version, keywords, defaults |
| `ML/report_parser.py` | Validation, normalization, features, heuristic risk/evidence |
| `ML/model_utils.py` | Strict record/label handling, matrices, model schema metadata |
| `ML/synthetic_reports.py` | Deterministic inert sandbox-compatible report generation |
| `ML/build_dataset.py` | Strict manifest-to-JSON records or feature CSV export |
| `ML/split_dataset.py` | Stratified train/validation/test and train-benign partitions |
| `ML/train_classifier.py` | Random Forest training with schema metadata |
| `ML/train_anomaly.py` | Isolation Forest training on explicit benign records |
| `ML/tune_threshold.py` | Validation-only F1 threshold selection |
| `ML/evaluate.py` | Classifier/anomaly metrics from labeled records |
| `ML/predict.py` | Heuristic/model CLI and HTTP inference plus health metadata |
| `ML/test_end_to_end.py` | Generation-to-saved-model HTTP integration test |

Exact commands and cautions are in [ML/SYNTHETIC_DATA.md](../../ML/SYNTHETIC_DATA.md).

## Input contract

The parser accepts a current sandbox shape with nonnegative summary counts and event arrays for processes, files, registry, network, DNS, and remote threads. A documented legacy shape is also normalized.

Missing/unusable telemetry, invalid counts, invalid arrays, or invalid signatures raise errors rather than becoming zero activity. Summary counts are authoritative because event arrays can be abbreviated. The backend's `sandboxToMl.js` maps known producer fields into this contract.

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

`FEATURE_SCHEMA_VERSION` and the ordered names are attached to newly trained estimators. Prediction rejects known incompatible schema/count metadata. Older models can load but report `schema_verified: false`; feature-count equality alone cannot prove semantic compatibility.

## Heuristic and model output

Without a classifier, `risk_score` comes from a deterministic heuristic and `prediction_source` is `heuristic`. This score is not a calibrated probability.

With a classifier, the malicious-class probability is compared with the explicitly supplied threshold and `prediction_source` is `trained_model`. Anomaly output is separate: `anomaly_prediction`/`anomaly_score` do not replace the main risk verdict.

Health and prediction responses include:

- Active threshold and runtime feature schema.
- Classifier/anomaly loaded state and estimator type.
- SHA-256 artifact version for models loaded from disk.
- Recorded schema version and `schema_verified` state.

Local model paths are not exposed.

## Reproducible synthetic workflow

The development path is:

```text
ML/synthetic_reports.py
  → ML/build_dataset.py
  → ML/split_dataset.py
  → train classifier/anomaly
  → ML/tune_threshold.py on validation
  → evaluate untouched synthetic test split
  → ML/predict.py --serve
```

Generation uses inert report strings and a fixed seed. Export rejects invalid reports/labels. Splitting is stratified, rejects duplicate reports/job IDs, and reserves train, validation, and test partitions. Threshold tuning maximizes malicious-class F1 on validation probabilities with deterministic tie-breaking.

The committed end-to-end test is designed to exercise this development workflow, but the current end-to-end test was blocked when `split_dataset.py` could not import NumPy. Synthetic labels/scenarios are invented, some classes intentionally share feature vectors, and metrics are not real-world malware-detection evidence. Real sample-family grouping and temporal/leakage controls remain the team's responsibility.

## HTTP inference

```bash
python ML/predict.py --serve \
  --classifier-model models/random_forest.joblib \
  --anomaly-model models/isolation_forest.joblib \
  --threshold 0.5
```

- `GET /` and `/health` return service/model metadata.
- `POST /`, `/analyze`, and `/analyze-report` accept one report.
- Invalid JSON/report/model input returns JSON with status 400.

The server is a development `ThreadingHTTPServer` with no authentication, TLS, request-size/rate controls, or production lifecycle. Bind it to loopback unless protected by a reviewed deployment boundary.

## Tests

Six modules contain 39 tests:

- `ML/test_report_parser.py`
- `ML/test_build_dataset.py`
- `ML/test_synthetic_reports.py`
- `ML/test_training.py`
- `ML/test_prediction_metadata.py`
- `ML/test_end_to_end.py`

Run:

```bash
python3 -B -m unittest discover -s ML -p "test_*.py" -v
```

The end-to-end test generates 300 synthetic reports in a temporary directory, exports/splits, trains both model types, tunes the classifier threshold, evaluates the synthetic test partition, starts the actual HTTP process, verifies artifact/schema metadata, compares CLI/HTTP output, and rejects empty telemetry. It does not call the backend or live sandbox.

Fresh 2026-11-19 results appear in [Prototype Status](../prototype-status.md#verification-record).

## Security and quality

- Joblib can execute code while loading; use only trusted artifacts with provenance and hashes.
- Reports can contain sensitive paths, commands, domains, IPs, registry values, and identifiers.
- Synthetic development data must remain clearly labeled.
- Real evaluation needs licensed data, deduplication, family-aware/temporal separation, immutable test data, calibrated thresholds, and confidence intervals as appropriate.
- `health.status: ok` means the service runs; inspect model metadata to learn whether trained models are loaded.

## Known limitations

- No static malware classifier or backend `static_ml` stage.
- No real dataset, trained artifact, model/dataset card, or reproducible real benchmark.
- No held-out-family result.
- No feature-importance export or calibration workflow.
- Random record splitting cannot establish independence between related real samples/families.
- Live behavioral input depends on a sandbox whose transfer/export/containment path is unverified.

## Next work

1. Create real dataset/model cards with licenses, counts, families, hashes, and split policy.
2. Add family-aware/temporal leakage controls and immutable evaluation artifacts.
3. Implement the separate static-PE ML contract and stage.
4. Export interpretable model evidence and calibration results.
5. Harden/authenticate the service and verify it with inert live sandbox output.

## Related documentation

- [Synthetic workflow](../../ML/SYNTHETIC_DATA.md)
- [Dynamic analysis](dynamic-analysis.md)
- [Backend](backend.md)
- [Architecture](../architecture.md)
- [Prototype Status](../prototype-status.md)
