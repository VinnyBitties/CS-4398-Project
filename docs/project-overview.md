# Sentinel Project Overview

## Document purpose

This document separates the approved Sentinel capstone baseline from the implementation present in `dev-branch` on 2026-11-19. Source, executable configuration, schemas, and tests take precedence over older planning prose. [Prototype Status](prototype-status.md) carries the detailed evidence and current verification record.

## Purpose and research scope

Coin-Flip Defense: Sentinel is a modular malware-analysis research prototype. The planned system combines signature matching, static evidence and machine learning, isolated behavioral collection and machine learning, and an evidence-grounded LLM report with MITRE ATT&CK mappings. The research objective is to compare the contribution of each layer, including behavior on families excluded from training.

The original target is Windows executable analysis. The current upload path is broader: it identifies content from bytes and can statically inspect PE/DOS files, Office documents, PDFs, scripts, source code, archives, shortcuts, and web content. That broader inspection is evidence collection, not a cross-platform malware verdict.

Sentinel is not a production antivirus, EDR, or validated sandbox. Detection improvements remain hypotheses until evaluated against versioned, licensed, representative datasets with reproducible methods.

## Current-version summary

The branch provides a runnable local web/backend prototype with optional accounts, guest scans, multi-format file or URL submission, database-backed jobs, signature lookup, byte-based file routing, PE/content analysis, stored history, and a connected report dashboard.

Additional source is present but not a complete verified layered deployment:

- Static ML is not a registered backend stage.
- The behavioral ML tooling has a reproducible synthetic workflow and end-to-end saved-model test, but no real dataset or model artifact is committed.
- `dynamic_telemetry/api.py` expresses a KVM/QEMU/Sysmon detonation service, but sample transfer, EVTX export, containment, reset, and live operation are not verified.
- The LLM component can perform demo indicator lookup and optionally call Groq model `openai/gpt-oss-20b`; it does not implement ATT&CK mapping or evidence citations.
- The dashboard shows history, behavioral summaries, stage state, and detailed PE evidence; content-analysis and LLM output lack equivalent complete viewers.

## Planned analysis flow

1. Accept a Windows executable through a web upload or API.
2. Compute its SHA-256 hash, query known signatures, and apply curated YARA rules.
3. Extract static PE features and compute a static ML malicious probability.
4. Execute unknown binaries in an isolated, revertible VM and capture runtime telemetry.
5. Convert sandbox logs to behavioral features and compute a behavioral risk result.
6. Generate an evidence-grounded explanation and MITRE ATT&CK mapping.
7. Present scores, behavior, and reports in one dashboard and retain history for evaluation.

This remains the target architecture. The current implementation adds multi-format static routing before the planned PE/static-ML path. Score combination, short-circuit policy, and the complete evaluation protocol are not defined.

## Functional requirements

| ID | Requirement | Current status | Current evidence summary |
| --- | --- | --- | --- |
| FR01 | Accept files through web upload or API. | Implemented | Dashboard and `POST /api/samples` accept multi-format uploads; `file_type` identifies bytes after storage. |
| FR02 | Query file hashes against a known signature database. | Partial | Local safe-demo catalog, optional bulk list, analyzer reputation cache, and optional YARA exist; no production feed is selected. |
| FR03 | Compute a static ML malicious-probability score. | Planned/not present | No static feature pipeline, dataset, artifact, or `static_ml` stage exists. Behavioral ML does not satisfy this requirement. |
| FR04 | Detonate unknown binaries in an isolated sandbox. | Partial | Client, pipeline stage, FastAPI/KVM/QEMU/Sysmon source, and mock tests exist; live operation and isolation are unverified. |
| FR05 | Compute a behavioral ML risk score. | Partial | Parser, heuristic, synthetic data/training workflow, HTTP service, backend adapter, and tests exist; no real artifact and no verified live sandbox input. |
| FR06 | Generate an LLM report mapped to MITRE ATT&CK tactics. | Partial | Bounded evidence, demo intelligence, and optional Groq explanation exist; ATT&CK mapping and citations do not. |
| FR07 | Display scores, telemetry, and reports in one dashboard. | Partial | History, behavioral summaries, stage state, and PE detail are connected; content-analysis and LLM views remain incomplete. |
| FR08 | Log scan history for benchmarking and validation. | Implemented | Database records, stage results, account/guest scoping, paged API, and connected history UI exist; benchmark export is absent. |

## Quality requirements

| ID | Requirement | Current status | Current gap |
| --- | --- | --- | --- |
| NFR Safety | Isolate sandbox network/host and restore state. | Not verified | Snapshot/service code is present, but transfer, network policy, reset under failure, cleanup, and containment have no live evidence. |
| NFR Explainability | Report feature importance and connect explanations to evidence. | Partial | Static facts, heuristic evidence, and optional prose exist; model importance and sentence-level citations do not. |
| NFR Usability | Make the dashboard interpretable by non-experts. | Partial | Explicit history/loading/failure/unavailable states and browser tests exist; accessibility and user evaluation remain. |
| NFR Performance | Return static results within an interactive demonstration timeframe. | Not verified | Timeouts and queue limits exist; no numeric target, latency benchmark, or load result is recorded. |
| NFR Maintainability | Keep subsystems modular and use Git-based workflows. | Implemented | Modules, contracts, evidence records, and tests are separated; cross-component schemas and deployment definitions still need consolidation. |

## Committed component responsibilities

| Component | Baseline responsibility | Current repository state |
| --- | --- | --- |
| Signature analysis | SHA-256 lookup and YARA matching. | Local backend catalog plus optional analyzer reputation/YARA; production feed not selected. |
| File routing/content analysis | Identify content and gather non-PE static evidence. | Default `file_type`/`content_analysis` stages cover bounded multi-format evidence. |
| Static PE extraction | Headers, sections, entropy, imports, APIs, strings, and resources. | Implemented in `malware_detection/` with schema 1.2.0; opt-in behind backend routing. |
| Static ML | Train, validate, and score before execution. | Not implemented or integrated. |
| Dynamic sandbox | Isolated execution, snapshots, and guest instrumentation. | Service source and client present; working transfer/export/containment not verified. |
| Runtime telemetry | Processes, registry, files, network, and API behavior. | Sysmon EVTX parser and adapters present; no verified live collection result. |
| Behavioral ML | Parse telemetry, train/validate, and score behavior. | Synthetic workflow, parser, heuristic, models, thresholding, inference, evaluation, and tests present; no real artifact/data. |
| LLM threat analysis | Ground explanation, ATT&CK mapping, and recommendations in evidence. | Demo intelligence and optional Groq prose present; ATT&CK/citation contract absent. |
| Backend | API, database, jobs, orchestration, and history. | Implemented for current stages with optional gates. |
| Dashboard | Submission, scores, telemetry, report display, and history. | Submission/history/PE and behavioral views implemented; some stage renderers incomplete. |
| Evaluation | Compare layers and held-out families. | Synthetic pipeline tests and metric tools exist; real experiment inputs/results absent. |

## Selected technology stack

| Area | Current selection |
| --- | --- |
| Frontend | Static HTML, CSS, and browser JavaScript; Playwright browser tests |
| Backend | Node.js, Express, Multer, SQLite via `better-sqlite3`, optional PostgreSQL via `pg` |
| File/content analysis | Python standard library plus optional `oletools`, `py7zr`, `rarfile`, and `pycdlib` |
| Static PE analyzer | Python, `pefile`, optional `yara-python`, JSON Schema |
| Behavioral ML | Python, NumPy, scikit-learn, joblib |
| Dynamic service | FastAPI, Uvicorn, KVM/QEMU/libvirt, QEMU Guest Agent, Sysmon, `python-evtx` |
| Threat explanation | Python bridge, demo intelligence, optional Groq SDK/model `openai/gpt-oss-20b` |
| Authentication | Username/password, scrypt hashes, server-side hashed session tokens, HttpOnly cookie |
| Queue | Database-backed queue inside one backend process |

No production threat feed, real ML dataset/model, approved sandbox environment, or production deployment platform is selected and verified in this branch.

## Out of scope

- A full real-time antivirus or EDR agent.
- Custom kernel drivers or real-time filesystem interception.
- Automatic remediation or ransomware rollback.
- Live memory forensics.
- Real-time network intrusion detection.
- Treating generic non-PE findings as a validated cross-platform verdict.
- Commercial competition with enterprise security products.

## Team responsibilities

Assignments follow the approved baseline; repository identities, approvals, and current availability must not be inferred from names.

| Area | Assigned members | Responsibility |
| --- | --- | --- |
| Dynamic analysis | Vincent, Jarrel | Virtualization, snapshots, guest instrumentation, runtime telemetry, and containment evidence. |
| Machine learning | Axel P, Diego | Dataset curation, static/behavioral features, training, validation, and artifact records. |
| LLM and threat intelligence | J.J | Prompting, provider orchestration, ATT&CK mapping, grounding, and mitigation summaries. |
| Backend | D.G | REST API, database, queue, and service orchestration. |
| Frontend | Sebastian | Dashboard, visualizations, report rendering, and upload workflow. |
| Malware detection | Kyle | PE extraction, entropy, hash reputation, and YARA curation. |
| Documentation and general support | Cade | Milestones, documentation, backend support, authentication, and database notes. |
| Integration lead | Shared role | Architecture, subsystem interfaces, and milestone coordination. |

## Proposed schedule

These remain proposal-relative weeks rather than current completion claims.

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

Actual milestone completion and approval dates are not consistently recorded and require team confirmation.

## Evidence and change control

The machine-readable [documentation evidence record](documentation-evidence.json) links current statuses to source and tests. A behavior or interface change should update that record, the owning component page, [Prototype Status](prototype-status.md), and the corresponding generated Word record. Unknown values must remain explicit rather than inferred.
