# Coin-Flip Defense: Sentinel

## Purpose

Coin-Flip Defense is a CS 4398 capstone project. The proposal calls the system **Sentinel**: a modular malware detection pipeline for Windows executable files that combines signature matching, static machine learning, and behavioral machine learning. An LLM explains the findings and maps supporting evidence to MITRE ATT&CK.

The project aims to measure what each detection layer adds beyond signature matching, especially when evaluating malware families excluded from training. This is a research and demonstration system, not a production antivirus replacement. Improvements in detection are hypotheses to evaluate, not established results.

## Status and source of truth

This document summarizes the project proposal and supplies context for GitHub issue tracking. It describes planned scope, not verified implementation progress. Current issues, pull requests, code, and recorded test results establish what has actually been completed. Week numbers below are the proposal's relative schedule, not calendar dates or current progress.

The repository's Gemini issue-tracking automation is a development aid. It is separate from Sentinel's product-facing LLM threat-analysis layer. Selecting Gemini for issue tracking does not establish the provider for the product.

## Planned analysis flow

1. Accept a Windows `.exe` through a web upload or API.
2. Compute its SHA-256 hash, look up known malicious signatures, and apply YARA rules.
3. Extract static PE features and produce a static ML malicious-probability score.
4. Execute unknown binaries in an isolated, revertible VM and capture runtime telemetry.
5. Convert sandbox logs into behavioral features and produce a behavioral ML risk score.
6. Generate an evidence-grounded LLM explanation, MITRE ATT&CK mapping, and recommendations.
7. Present scores, observed behavior, and the report in a web dashboard; retain historical scan results for evaluation.

The proposal does not specify routing thresholds, how scores combine into a final verdict, or whether known signature matches bypass later stages. Those decisions need explicit implementation requirements.

## Committed scope

| Component | Planned responsibilities |
| --- | --- |
| Signature analysis | SHA-256 lookup against known malicious catalogs and YARA pattern matching. |
| Static feature extraction | PE headers, section entropy, imported APIs, strings, and section information. |
| Static ML | Feature engineering, baseline training, hyperparameter tuning, validation, and pre-execution benign/malicious scoring. |
| Dynamic sandbox | Isolated VM execution, automated snapshots/restoration, and guest instrumentation. |
| Runtime telemetry | Process trees, registry edits, filesystem changes, network requests, and API calls. |
| Behavioral ML | Convert raw JSON sandbox logs into feature vectors; train, validate, and integrate a post-execution classifier. |
| LLM threat analysis | Ground plain-language explanations, MITRE ATT&CK mappings, and recommendations in telemetry and model outputs. |
| Backend | REST API, database, job queue, pipeline orchestration, and historical scan records. |
| Dashboard | File submission, score visualization, telemetry inspection, and AI report display. |
| Evaluation | Compare detection layers and evaluate performance on malware families withheld from training. |

Behavioral classifier training and integration are required even though the proposal's task table does not give them a separate numbered task.

## Functional requirements

Preserve these proposal IDs when referencing requirements in issues and reports.

| ID | Requirement |
| --- | --- |
| 01 | Accept executable files (`.exe`) through a web upload or API. |
| 02 | Query file hashes against a known signature database. |
| 03 | Compute a static ML malicious-probability score. |
| 04 | Detonate unknown binaries within an isolated sandbox. |
| 05 | Compute a behavioral ML risk score from recorded runtime activity. |
| 06 | Generate an automated LLM report mapped to MITRE ATT&CK tactics. |
| 07 | Display scores, telemetry, and generated reports in a unified dashboard. |
| 08 | Log historical scan results for benchmarking and validation. |

## Quality requirements and evaluation

- **Safety:** Complete host and network isolation for the sandbox, with snapshot restoration. Capturing network requests does not imply unrestricted external network access.
- **Explainability:** Report feature importance and connect explanations to observed evidence.
- **Usability:** Make the dashboard interpretable by non-expert analysts.
- **Performance:** Return static analysis results within interactive demonstration timeframes; the proposal gives no numeric latency target.
- **Maintainability:** Keep subsystems modular and use standard Git-based development workflows.
- **Evaluation:** Report accuracy, precision, recall, F1, ROC-AUC, and false-positive/false-negative rates. Compare detection layers and run the held-out-family experiment reproducibly. The proposal sets no numeric performance targets.

## Out of scope

- A full real-time antivirus or EDR agent.
- Custom kernel drivers or real-time filesystem interception.
- Automatic remediation or ransomware rollback.
- Live memory forensics.
- Real-time network intrusion detection.
- Cross-platform executable support beyond Windows executables.
- Competing commercially with enterprise security products.

## Team responsibilities

Names and assignments below follow the proposal.

| Area | Assigned members | Responsibility |
| --- | --- | --- |
| Dynamic analysis | Vincent, Jarrel | Virtualization, snapshots, guest instrumentation, and runtime telemetry. |
| Machine learning | Axel P, Diego | Dataset curation, static/behavioral features, and model training/validation. |
| LLM and threat intelligence | J.J | Prompt engineering, API orchestration, ATT&CK mapping, and mitigation summaries. |
| Backend | D.G | REST API, database, pipeline queue, and service orchestration. |
| Frontend | Sebastian | Dashboard, visualizations, report rendering, and upload workflow. |
| Malware detection | Kyle | PE extraction, entropy parsers, and YARA rule curation. |
| Documentation and general support | Cade | Milestone tracking, documentation, backend support, Gmail authentication, and login/database work. |
| Integration lead | Shared role | Architecture oversight, subsystem interfaces, and milestone coordination. |

GitHub usernames are not specified. Do not infer account identities from these names. Authentication appears in the delegation table but has no detailed functional specification; define that scope in its own issue.

## Proposed schedule

| Weeks | Phase |
| --- | --- |
| 1–2 | Architecture and setup |
| 3–4 | Static analysis pipeline |
| 5–6 | Static ML classifier |
| 5–8 | Dynamic sandbox, in parallel with static ML work |
| 7–9 | Behavioral features |
| 8–10 | LLM integration |
| 9–11 | Dashboard development |
| 11–13 | Integration and system testing |
| 14–15 | Evaluation and final capstone report |

## Technology decisions still open

The proposal requires a labeled benign/malware dataset, ML libraries, snapshot-capable virtualization, LLM API access, a backend service, a database, and a frontend framework. It does not select specific languages, frameworks, model algorithms, dataset sources, sandbox software, database products, or an LLM provider.

Record selected technologies, component interfaces, telemetry schemas, routing rules, and score-combination rules as the team agrees on them. Do not treat an unspecified choice as an existing requirement.

