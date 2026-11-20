# Prototype Status and Requirements Traceability

## Reporting basis

This record describes `dev-branch` on 2026-11-19. Source, executable configuration, schemas, current test inventory, and commands run during this update take precedence over historical prose.

### Status vocabulary

- **Implemented:** code is present and has a concrete execution path.
- **Integrated:** producer and consumer code/contracts are present and exercised at their boundary.
- **Partial:** meaningful implementation exists, but required behavior or evidence is incomplete.
- **Stubbed/configurable:** an adapter or placeholder exists and needs unavailable implementation/configuration.
- **Planned/not present:** required implementation is absent.
- **Not verified:** source or a historical claim exists, but current operational evidence is absent.

## Component maturity

| Component | Status | Evidence of current capability | Primary gap |
| --- | --- | --- | --- |
| Frontend dashboard | Partial | Multi-format submission, auth/guest flow, polling, paged history, behavioral summaries, detailed PE evidence, Node/Playwright tests | Content-analysis and LLM details are incomplete; accessibility/user evaluation absent |
| Backend API and orchestration | Partial | Express API, sessions, SQLite/PostgreSQL, jobs, signature, file routing, PE/content analysis, optional service gates | Static ML absent; optional services require separate verified environments |
| Static malware detection and PE evidence | Implemented | Analyzer, schema 1.2.0, bounded PE evidence, optional reputation/YARA | Opt-in behind mock default; current verification recorded below |
| Behavioral feature extraction and machine learning | Partial | Parser, heuristic, synthetic generation/export/split/training/threshold/evaluation, CLI/HTTP, artifact metadata, tests | No real dataset, committed model, static classifier, or held-out-family result |
| Dynamic sandbox integration | Partial | Backend client/adapter plus FastAPI/KVM/QEMU/Sysmon service source | Sample transfer, EVTX export, containment, cleanup, and live detonation not verified |
| LLM and threat-intelligence integration | Partial | Bounded evidence, demo indicator analysis, optional Groq `openai/gpt-oss-20b` explanation, bridge tests | No ATT&CK mapping, citations, production feed, or provider evaluation |

## Functional requirements

| ID | Requirement | Status | Evidence | Gap or qualification |
| --- | --- | --- | --- | --- |
| FR01 | Accept files through web upload or API. | Implemented | `website/dashboard/home.html`, `website/api.js`, `backend/src/routes/samples.js` | Browser list is a convenience; `file_type` byte detection is authoritative. |
| FR02 | Query file hashes against a known signature database. | Partial | Backend catalog/bulk list; analyzer cache/YARA modules | Default catalog is safe demonstration data; no production feed selected. |
| FR03 | Compute a static ML malicious-probability score. | Planned/not present | PE report is available as a possible future input | No static features/model/data/artifact or `static_ml` stage; behavioral ML is separate. |
| FR04 | Detonate unknown binaries in an isolated sandbox. | Partial | Client, pipeline stage, `dynamic_telemetry/api.py`, mock tests | Transfer, EVTX export, live execution, reset, network isolation, and containment unverified. |
| FR05 | Compute a behavioral ML risk score from runtime activity. | Partial | Parser, heuristic/models, synthetic end-to-end test, sandbox adapter | No real artifact or dataset; live input depends on the unverified sandbox. |
| FR06 | Generate an LLM report mapped to MITRE ATT&CK tactics. | Partial | Evidence adapter, demo intelligence, bridge, optional Groq explanation | No ATT&CK mapping, cited claims, production feed, or provider evaluation. |
| FR07 | Display scores, telemetry, and reports in one dashboard. | Partial | Paged history, stage state, behavioral summary, signature state, detailed PE viewer | `file_type`, `content_analysis`, and LLM lack equivalent complete report views. |
| FR08 | Log historical scan results for benchmarking and validation. | Implemented | Samples/jobs/results persistence, account scoping, paged API and history UI | No benchmark/export workflow consumes the history. |

## Nonfunctional requirements

| ID | Requirement | Status | Evidence | Gap or qualification |
| --- | --- | --- | --- | --- |
| NFR Safety | Isolate sandbox network/host and restore state. | Not verified | Snapshot/service source exists | No verified transfer, network policy, failure-safe reset, cleanup, or containment. |
| NFR Explainability | Report feature importance and connect explanations to evidence. | Partial | PE facts, heuristic evidence, bounded prompt, optional prose | No trained-model importance or sentence-level citations. |
| NFR Usability | Make the dashboard understandable to non-experts. | Partial | Explicit loading/failure/unavailable states, responsive browser coverage | No accessibility audit or user study; not every stage has a detail renderer. |
| NFR Performance | Return static results in interactive demo time. | Not verified | Timeouts, queue concurrency, bounded static reads | No numeric target, latency benchmark, or load test. |
| NFR Maintainability | Keep a modular Git-based architecture. | Implemented | Separate components/contracts, evidence record, documentation checks, unit/integration tests | Cross-team schemas and deployment definitions still need consolidation. |

## Default runnable demonstration

With optional service variables empty, the backend can:

1. Serve account and dashboard pages.
2. Register/login/logout or operate as a guest.
3. Accept files or URLs and persist scoped scans.
4. Queue jobs and expose status/history.
5. Check the safe local signature catalog.
6. Identify file content from bytes.
7. Run mock PE analysis for PE/DOS or unknown input and content analysis for every detected non-PE format. Unknown classifications run both `static_analysis` and `content_analysis`.
8. Render history, stage state, behavioral availability, and PE evidence when available.

This demonstrates orchestration and evidence handling, not detection efficacy.

## Integration state

| Integration | Producer | Consumer | Current evidence | State |
| --- | --- | --- | --- | --- |
| Dashboard → backend API | Browser modules | Express routes | Source plus Node/Playwright tests | Integrated |
| Backend → file/content analyzer | Python standard-library script | Pipeline | Routing/content tests | Integrated |
| Backend → mock PE analyzer | Mock script | Pipeline/dashboard | Default inert path | Integrated |
| Backend → real PE analyzer | PE analyzer | Pipeline/PE viewer | Versioned contract and tests; environment result below | Integrated; current execution may be dependency-limited |
| Real PE analyzer → static ML | PE report only | No static model/stage | None | Planned/not present |
| Backend → dynamic service | Client | FastAPI source | Mock boundary tests; no live transfer/export evidence | Partial / Not verified live |
| Dynamic service → behavioral ML | Telemetry/adapter | ML HTTP service | Mock backend tests plus synthetic ML end-to-end test | Partial; no live sandbox evidence |
| Pipeline → threat intelligence | Adapter/bridge | Committed component | Bridge tests, demo lookup, optional provider call | Partial; live provider not verified |
| Backend history → reports page | Paged routes | Reports UI | Node/Playwright tests | Integrated |

## Verification record

The normalized [evidence record](documentation-evidence.json) contains the exact results from this update. A blocked command is not a passing component result, and test inventory is not substituted for execution.

| ID | Command | Current record | Interpretation |
| --- | --- | --- | --- |
| DOC-VER-000 | `python3 -m unittest discover -s tests/documentation -v` | The pre-update documentation suite ran 23 tests and passed; this established that the old checks did not detect the November implementation drift. | Baseline only. |
| DOC-VER-001 | `python3 -m unittest discover -s tests/contribution_tracker -v` | Ran 30 tests; all passed. | Project automation only; not product analysis. |
| DOC-VER-002 | `cd backend && npm test` | Exited 1 before Node tests ran: npm reported 'WSL 1 is not supported. Please upgrade to WSL 2 or above.' and 'Could not determine Node.js install directory'. | Blocked by this platform; no Node assertions ran. |
| DOC-VER-003 | `python3 -m unittest discover -s malware_detection/tests -v` | Discovered six test modules; all six failed to import because pefile is not installed (ModuleNotFoundError: No module named 'pefile'); no assertions ran. | Blocked by a required dependency. |
| DOC-VER-004 | `python3 -B -m unittest discover -s ML -p "test_*.py" -v` | Ran 9 discovered test entries: four synthetic-report tests passed, four modules failed to import because numpy or joblib is not installed, and the end-to-end test failed when split_dataset.py could not import numpy. | Partially executed and dependency-blocked; no model-performance claim. |
| DOC-VER-005 | `cd backend && npm run test:dashboard` | Exited 1 before Playwright ran: npm reported 'WSL 1 is not supported. Please upgrade to WSL 2 or above.' and 'Could not determine Node.js install directory'; browser availability was not reached. | Blocked by Node/npm platform detection before browser validation. |
| DOC-VER-006 | `python3 -m unittest discover -s tests/documentation -v && python3 scripts/update_documentation_forms.py --source-root . --output-dir . --check` | Ran 33 documentation tests; all passed, and generator check validated all eight Word forms. | Content/structure validation; visual Office layout still needs a Word-compatible renderer. |

## Test inventory

- Backend: top-level Node tests for routes, auth, persistence, jobs, signatures, file/content routing, HTTP stages, sandbox/ML, LLM, dashboard data, and PE boundary behavior.
- Dashboard: seven Node data-model tests and eight Playwright browser/inert-backend tests.
- Malware detection: six Python modules covering analyzer behavior, contract, extraction, reputation, YARA, and consumers.
- ML: six modules with 39 tests covering parsing, generation, export, splitting, training, thresholds, metadata, and end-to-end serving.
- Documentation: evidence, Markdown links/current-state, Office structure/content, and cross-format checks.
- Contribution tracker: Git/issue automation tests, separate from product threat intelligence.

No mock, synthetic, or unit test replaces a live sandbox containment review or live provider evaluation.

## Open risks

| ID | Risk | Impact | Response |
| --- | --- | --- | --- |
| RISK-001 | Sandbox source can be mistaken for proven containment. | Critical if real malware is executed. | Use inert fixtures until transfer, export, isolation, reset, cleanup, and handling are independently validated. |
| RISK-002 | Static ML is absent; optional stages are environment-dependent. | No verified default six-layer pipeline. | Demonstrate the default route honestly and track optional integrations separately. |
| RISK-003 | Synthetic workflow can be mistaken for real efficacy. | Unsupported accuracy/generalization claims. | Label generated metrics synthetic; add real dataset/model cards, family grouping, thresholds, and reproducible results. |
| RISK-004 | Uploads, telemetry, URLs, indicators, hashes, and accounts may be sensitive. | Local or external disclosure. | Define retention, deletion, access, redaction, and provider-data policies. |
| RISK-005 | Verification may be limited by dependencies, browsers, or unavailable services. | Source presence may be reported as exercised behavior. | Record exact commands and blockers; separate unit/mock results from live checks. |

## Known limitations and technical debt

- Guest scanning remains enabled by default.
- No upload/scan deletion endpoint or retention job exists.
- The queue is single-process; PostgreSQL does not create a distributed worker fleet.
- The default PE analyzer is a mock.
- Static ML is absent.
- Report history does not fully render every current stage.
- Dynamic constants and service configuration are environment-specific; live safety is unverified.
- Remote-thread telemetry can remain an adapter blind spot.
- No real dataset, model card, trained artifact, held-out-family experiment, or efficacy result is committed.
- LLM output has no citations, ATT&CK mapper, prompt version, production feed, or evaluation.
- No production deployment, TLS, monitoring, backup, disaster recovery, artifact storage, or secrets-management design is supplied.

## Deferred work by priority

1. Resolve and test sandbox sample transfer and EVTX export with inert canaries.
2. Independently validate containment, network policy, reset, cleanup, and handling before real detonation.
3. Create the missing static-ML pipeline and versioned contract.
4. Establish real dataset/model cards, family-aware splits, trained artifacts, and reproducible evaluation.
5. Add complete content-analysis and LLM report views plus accessibility/user evaluation.
6. Define cited, versioned LLM/ATT&CK output and provider privacy/cost policy.
7. Add retention/deletion controls and production deployment security.
8. Execute the layered and held-out-family research evaluation.

## Source of truth

The [documentation evidence record](documentation-evidence.json) carries machine-readable status, paths, verification, and risks. [Documentation Index](documentation-index.md) maps audiences to authoritative guides. Exact API and PE report fields remain authoritative in their owning component contracts.
