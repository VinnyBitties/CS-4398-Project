# Sentinel Project Overview

## Document purpose

This document records both the approved project baseline and the state of the prototype in `dev-branch` on 2026-11-03. The baseline explains what the capstone intends to deliver; the current-status statements identify what the repository actually contains. Source, configuration, schemas, and executable tests take precedence over older planning prose.

## Project purpose

Coin-Flip Defense: Sentinel is a modular malware-analysis research prototype for Windows executable files. The planned system combines signature matching, static analysis and machine learning, isolated behavioral analysis and machine learning, and an evidence-grounded LLM report with MITRE ATT&CK mappings. Its research objective is to compare the contribution of each layer, including behavior on malware families excluded from training.

Sentinel is not intended to replace production antivirus or EDR software. Detection improvements remain hypotheses until evaluated against versioned, licensed datasets with reproducible methods.

## Current-version summary

The current branch supplies a runnable web/backend demonstration with account or guest access, file and URL submission, local persistence, queued jobs, signature checks, and static-analysis orchestration. It also supplies a detailed Python PE analyzer and a separate behavioral ML toolkit.

The complete conceptual pipeline does not run by default:

- The backend defaults to a mock static analyzer; the real analyzer is opt-in.
- Static ML is not registered as a pipeline stage.
- Sandbox and behavioral-ML orchestration exists, but the actual sandbox implementation is absent.
- LLM input and bridge code exists, but its external threat-intelligence component and model invocation are absent.
- The dashboard submits and polls scans, while its reports page remains disconnected.

See [Prototype Status](prototype-status.md) for evidence and [Architecture](architecture.md) for the actual data flow.

## Planned analysis flow

1. Accept a Windows `.exe` through a web upload or API.
2. Compute its SHA-256 hash, look up known malicious signatures, and apply YARA rules.
3. Extract static PE features and produce a static ML malicious-probability score.
4. Execute unknown binaries in an isolated, revertible VM and capture runtime telemetry.
5. Convert sandbox logs into behavioral features and produce a behavioral ML risk score.
6. Generate an evidence-grounded LLM explanation, MITRE ATT&CK mapping, and recommendations.
7. Present scores, observed behavior, and the report in a web dashboard; retain historical scan results for evaluation.

This remains the target architecture. Routing thresholds, score combination, and whether signature matches should bypass later stages are not defined in the current implementation.

## Functional requirements

These identifiers remain stable across issues, forms, tests, and final reports.

| ID | Requirement | Current status | Current evidence summary |
| --- | --- | --- | --- |
| FR01 | Accept executable files through web upload or API. | Implemented | Dashboard and `POST /api/samples`; backend analysis determines whether an upload is a PE. |
| FR02 | Query file hashes against a known signature database. | Partial | Local catalog, optional bulk list, offline analyzer cache, and optional YARA; no production feed selected. |
| FR03 | Compute a static ML malicious-probability score. | Planned/not present | PE extraction is a prerequisite, but no static model, artifact, dataset, feature pipeline, or `static_ml` stage exists. |
| FR04 | Detonate unknown binaries in an isolated sandbox. | Stubbed/configurable | Backend client and mock tests exist; sandbox/VM implementation and safety validation are absent. |
| FR05 | Compute a behavioral ML risk score. | Stubbed/configurable | Parser/scorer/service and adapter exist; end-to-end input depends on the absent sandbox. |
| FR06 | Generate an LLM report mapped to MITRE ATT&CK tactics. | Stubbed/configurable | Evidence adapter and bridge exist; external component, LLM call, and mappings are absent. |
| FR07 | Display scores, telemetry, and reports in one dashboard. | Partial | Stage progress works; report history and detailed result rendering do not. |
| FR08 | Log scan history for benchmarking and validation. | Implemented | Database records, stage results, account scoping, and paged history endpoint exist; no benchmark export workflow exists. |

## Quality requirements

| ID | Requirement | Current status | Current gap |
| --- | --- | --- | --- |
| NFR Safety | Isolate the sandbox network and host and restore a known state. | Planned/not present | No sandbox source, environment record, or real isolation/reset test is in this branch. |
| NFR Explainability | Report feature importance and connect explanations to evidence. | Partial | Evidence facts and heuristic explanations exist; trained feature importance and cited LLM explanation do not. |
| NFR Usability | Make the dashboard interpretable by non-experts. | Partial | Progress labels exist; report visualization, accessibility, and user evaluation remain. |
| NFR Performance | Return static results within an interactive demonstration timeframe. | Not verified | Timeouts exist, but no numeric target, latency benchmark, or load result is recorded. |
| NFR Maintainability | Keep subsystems modular and use Git-based workflows. | Implemented | Components and contracts are separated, though cross-team schemas still need consolidation. |

## Committed component responsibilities

| Component | Baseline responsibility | Current repository state |
| --- | --- | --- |
| Signature analysis | SHA-256 lookup and YARA matching. | Local backend catalog plus analyzer reputation/YARA modules; production feed not selected. |
| Static extraction | PE headers, sections, entropy, imports, APIs, strings, and resources. | Implemented in `malware_detection/` with schema 1.2.0. |
| Static ML | Train, validate, and score before execution. | Not specifically implemented or integrated. |
| Dynamic sandbox | Isolated execution, snapshots, and guest instrumentation. | Backend client only; implementation absent. |
| Runtime telemetry | Processes, registry, files, network, and API behavior. | Expected by adapters; collection implementation absent. |
| Behavioral ML | Parse telemetry, train/validate, and score runtime behavior. | Parser, heuristic, training, inference, and evaluation scripts present; no artifact/dataset. |
| LLM threat analysis | Ground explanation, ATT&CK mapping, and recommendations in evidence. | Input adapter and external bridge present; actual generation absent. |
| Backend | API, database, job queue, orchestration, and history. | Implemented for the current stages with optional integration gates. |
| Dashboard | Submission, scores, telemetry, report display, and history. | Submission/progress implemented; results/history incomplete. |
| Evaluation | Compare layers and held-out families. | Metric tooling exists; experiment data and results absent. |

## Selected technology stack

| Area | Current selection |
| --- | --- |
| Frontend | Static HTML, CSS, and browser JavaScript |
| Backend | Node.js, Express, Multer, SQLite through `better-sqlite3`, optional PostgreSQL through `pg` |
| Static analyzer | Python, `pefile`, optional `yara-python`, JSON Schema |
| Machine learning | Python, NumPy, scikit-learn, joblib |
| Authentication | Username/password, scrypt password hashes, server-side hashed session tokens, HttpOnly cookie |
| Queue | Database-backed queue inside one backend process |
| Optional services | HTTP sandbox and behavioral-ML service; Python subprocess bridge for threat intelligence |

No hypervisor, guest image, LLM provider/model, production threat feed, dataset source, or deployment platform is selected in this branch.

## Out of scope

- A full real-time antivirus or EDR agent.
- Custom kernel drivers or real-time filesystem interception.
- Automatic remediation or ransomware rollback.
- Live memory forensics.
- Real-time network intrusion detection.
- Cross-platform executable support beyond Windows PE files.
- Commercial competition with enterprise security products.

## Team responsibilities

Assignments below follow the approved baseline. Repository account identities and current approvals must not be inferred from names.

| Area | Assigned members | Responsibility |
| --- | --- | --- |
| Dynamic analysis | Vincent, Jarrel | Virtualization, snapshots, guest instrumentation, and runtime telemetry. |
| Machine learning | Axel P, Diego | Dataset curation, static/behavioral features, training, and validation. |
| LLM and threat intelligence | J.J | Prompting, API orchestration, ATT&CK mapping, and mitigation summaries. |
| Backend | D.G | REST API, database, queue, and service orchestration. |
| Frontend | Sebastian | Dashboard, visualizations, report rendering, and upload workflow. |
| Malware detection | Kyle | PE extraction, entropy parsing, hash reputation, and YARA curation. |
| Documentation and general support | Cade | Milestones, documentation, backend support, authentication, and database notes. |
| Integration lead | Shared role | Architecture, subsystem interfaces, and milestone coordination. |

## Proposed schedule

These are proposal-relative weeks, not current completion claims.

| Weeks | Phase |
| --- | --- |
| 1–2 | Architecture and setup |
| 3–4 | Static analysis pipeline |
| 5–6 | Static ML classifier |
| 5–8 | Dynamic sandbox |
| 7–9 | Behavioral features |
| 8–10 | LLM integration |
| 9–11 | Dashboard development |
| 11–13 | Integration and system testing |
| 14–15 | Evaluation and final capstone report |

Actual milestone completion dates are not consistently recorded and require team confirmation.

## Evidence and change control

The machine-readable [documentation evidence record](documentation-evidence.json) links each status to source and tests. Meaningful scope or interface changes should update that record, the affected component page, [Prototype Status](prototype-status.md), and the corresponding Word form. Do not replace unknown values with assumptions.
