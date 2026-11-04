# Prototype Status and Requirements Traceability

## Reporting basis

This record describes `dev-branch` on 2026-11-03. It uses source, configuration, schemas, test inventory, and commands observed during this documentation update. Historical test counts remain historical unless rerun.

### Status vocabulary

- **Implemented:** code is present and has a concrete execution path.
- **Integrated:** producer and consumer code/contracts are present in this branch.
- **Partial:** meaningful code exists, but required behavior is incomplete.
- **Stubbed/configurable:** an adapter or placeholder exists but needs an unavailable component or configuration.
- **Planned/not present:** required implementation is absent.
- **Not verified:** code or a historical claim exists, but it was not exercised successfully in the current environment.

## Component maturity

| Component | Status | Evidence of current capability | Primary gap |
| --- | --- | --- | --- |
| Frontend dashboard | Partial | Login/guest flow, upload/URL submission, polling, stage progress | Reports page does not call history API or render detailed results |
| Backend API and orchestration | Partial | Express API, auth, SQLite/PostgreSQL, queue, signature/static stages, optional adapters | Static ML absent; external stages unavailable by default |
| Static malware detection and PE evidence | Implemented | Analyzer, schema 1.2.0, PE evidence, optional reputation/YARA | Not the backend default; current test environment lacks `pefile` |
| Behavioral feature extraction and machine learning | Partial | Parser, heuristic, model training/inference/evaluation tools | No dataset, trained artifact, static model, or evidenced metrics |
| Dynamic sandbox integration | Stubbed/configurable | Backend client, serialization, telemetry adapter, mock tests | Sandbox service, VM, collection, isolation, and reset absent |
| LLM and threat-intelligence integration | Stubbed/configurable | Bounded input/indicator adapter and Python bridge | External component, provider/model, explanation, and ATT&CK mapping absent |

## Functional requirements

| ID | Requirement | Status | Evidence | Gap or qualification |
| --- | --- | --- | --- | --- |
| FR01 | Accept executable files through web upload or API. | Implemented | `website/dashboard/home.html`, `website/api.js`, `backend/src/routes/samples.js` | Browser checks `.exe`; backend accepts upload then analysis validates PE format. |
| FR02 | Query file hashes against a known signature database. | Partial | Backend catalog and optional bulk list; analyzer cache/YARA modules | Committed catalog uses safe test indicators; no production feed selected. |
| FR03 | Compute a static ML malicious-probability score. | Planned/not present | PE extraction is a prerequisite | No static feature model, artifact, dataset, training path, or `static_ml` pipeline stage. |
| FR04 | Detonate unknown binaries in an isolated sandbox. | Stubbed/configurable | Sandbox HTTP client and mocked pipeline tests | Sandbox implementation and safety evidence are absent. |
| FR05 | Compute a behavioral ML risk score from runtime activity. | Stubbed/configurable | Parser/scorer/service and sandbox-to-ML adapter | Requires absent sandbox; no trained model artifact supplied. |
| FR06 | Generate an LLM report mapped to MITRE ATT&CK tactics. | Stubbed/configurable | Evidence adapter, bridge, ordering tests | External component, LLM invocation, explanation, and mapping absent. |
| FR07 | Display scores, telemetry, and reports in one dashboard. | Partial | Stage polling and progress labels | Report history/detail view is not integrated. |
| FR08 | Log scan history for benchmarking and validation. | Implemented | Samples/jobs/results tables and paged API | No history export or benchmark workflow consumes it. |

## Nonfunctional requirements

| ID | Requirement | Status | Evidence | Gap or qualification |
| --- | --- | --- | --- | --- |
| NFR Safety | Isolate sandbox network/host and restore state. | Planned/not present | Only client behavior and mocks are present | No real containment, sample handling, or reset test. |
| NFR Explainability | Report feature importance and evidence. | Partial | PE facts, heuristic evidence, bounded LLM input | No trained feature importance or cited generated explanation. |
| NFR Usability | Make the dashboard understandable to non-experts. | Partial | Plain-language progress states | No completed report view, accessibility audit, or user study. |
| NFR Performance | Return static results in interactive demo time. | Not verified | Configured timeouts and queue limits | No numeric target, benchmark, or load test. |
| NFR Maintainability | Keep a modular Git-based architecture. | Implemented | Separate modules, contracts, schemas, and tests | Optional source trees absent; some telemetry translation remains. |

## Implemented default demonstration

With no optional environment variables, the backend can:

1. Serve the static login/dashboard pages.
2. Register, log in, log out, or operate as a guest.
3. Accept a file or URL and persist the submission.
4. Queue a scan and expose status by polling.
5. Check the safe local signature catalog.
6. Run the mock analyzer for files.
7. Store stage results and return paged history through the API.

This demonstrates orchestration, not full malware detection efficacy.

## Integration state

| Integration | Producer available | Consumer available | Real end-to-end evidence | State |
| --- | --- | --- | --- | --- |
| Dashboard → backend API | Yes | Yes | Source-connected; Node suite not rerun | Integrated |
| Backend → mock analyzer | Yes | Yes | Default code path | Integrated |
| Backend → real analyzer | Yes | Yes | Contract and conditional tests; blocked locally by dependency | Integrated, not verified here |
| Real analyzer → static ML | PE report only | No static model/stage | No | Planned/not present |
| Backend → sandbox | Client only | No service in branch | No | Stubbed/configurable |
| Sandbox → behavioral ML | Adapter and ML service | Sandbox absent | Mocked only | Stubbed/configurable |
| Pipeline → threat intelligence | Adapter/bridge | External component absent | Mocked only | Stubbed/configurable |
| Backend history → reports page | API yes | UI no | No | Partial |

## Verification record

### Observed on 2026-11-03

| ID | Command | Result | Interpretation |
| --- | --- | --- | --- |
| DOC-VER-001 | `python3 -m unittest discover -s tests/contribution_tracker -v` | 30 tests ran and passed. | Observed passing result. |
| DOC-VER-002 | `cd backend && npm test` | Tests did not start; the available npm shim reported WSL 1 is unsupported and could not determine the Node.js installation directory. | Environment/tooling block; no backend assertions ran. |
| DOC-VER-003 | `python3 -m unittest discover -s malware_detection/tests -v` | Six test modules failed to import because pefile is not installed; no assertions ran. | Dependency block; no analyzer assertions ran. |
| DOC-VER-004 | `cd ML && python3 -m unittest test_report_parser -v` | The test module failed to import because joblib is not installed; no assertions ran. | Dependency block; no ML assertions ran. |

### Repository test inventory

- Backend: eight `.test.js` files covering API, auth, queue, catalog, HTTP runner, sandbox/ML integration, LLM stage, and real-analyzer boundary.
- Malware detection: six Python modules covering analyzer behavior, contract, extraction, reputation, YARA, and consumers.
- ML: fifteen tests in `ML/test_report_parser.py`.
- Frontend: no dedicated unit or browser-automation suite.
- Documentation: integrity tests validate the evidence record, local links, Word structure, and cross-format status consistency.

Do not copy historical counts into a current-results table without rerunning the corresponding command.

## Open risks

| ID | Risk | Impact | Response |
| --- | --- | --- | --- |
| RISK-001 | Sandbox containment is absent and unverified. | Critical if real malware is executed. | Use inert fixtures until isolation, reset, and handling are independently validated. |
| RISK-002 | Static ML is absent and dynamic/LLM components are optional or missing. | No complete layered pipeline from this branch. | Demonstrate the default path honestly and track integrations separately. |
| RISK-003 | Dataset/model provenance and results are absent. | Accuracy, leakage, licensing, and generalization cannot be assessed. | Add dataset/model cards, exact splits, thresholds, and reproduction commands. |
| RISK-004 | Uploads, telemetry, URLs, and records may be sensitive. | Local or external disclosure. | Define retention, access, deletion, redaction, and external-transmission policies. |
| RISK-005 | Several suites were blocked in the documentation environment. | Current confidence is lower than historical prose may imply. | Re-run under supported Node/WSL and isolated Python environments. |

## Known limitations and technical debt

- The root frontend uses large inline scripts and alert-style validation.
- Reports history is an empty in-memory scaffold.
- Guest scanning is enabled by default.
- The backend has no upload or scan deletion endpoint.
- The queue is intentionally single-process; PostgreSQL does not turn it into a distributed worker fleet.
- The signature catalog is demonstration-only.
- The real analyzer is not the backend default.
- A telemetry adapter bridges current sandbox/ML schema differences.
- ML heuristic scores are not calibrated probabilities.
- No model card, dataset card, benchmark table, held-out-family experiment, or trained artifact is present.
- No LLM data policy, provider/model selection, prompt artifact, citations, or mapping review exists.
- No deployment, TLS, monitoring, backup, disaster recovery, or production secrets-management guide exists.

## Deferred work by priority

1. Validate and document sandbox safety before any real detonation.
2. Select and document a licensed dataset; build the missing static ML path.
3. Produce and evaluate versioned behavioral model artifacts.
4. Complete the reports page and detailed result rendering.
5. Supply and validate the threat-intelligence/LLM component with evidence citations and ATT&CK review.
6. Add retention/deletion controls and deployment security guidance.
7. Run all suites in supported environments and record exact results.
8. Execute the layered and held-out-family evaluation with reproducible commands.

## Source of truth

The normalized [documentation evidence record](documentation-evidence.json) carries paths and status data used for this package. Detailed component behavior is documented in [the component index](documentation-index.md), while narrow API and report schemas remain authoritative in their owning directories.
