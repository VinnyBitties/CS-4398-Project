# Documentation Index

## How to use this index

Status statements describe `dev-branch` as of 2026-11-19. Start with the artifact matching your task. Broad documents summarize and link; source, executable configuration, schemas, tests, and narrow component contracts remain authoritative for exact behavior.

## Core documents

| Audience or question | Authoritative document | Owner | Status |
| --- | --- | --- | --- |
| What is Sentinel and how do I start it? | [Root README](../README.md) | Documentation / integration | Current prototype entry point |
| What was planned and what exists now? | [Project Overview](project-overview.md) | Documentation coordinator | Current baseline/status summary |
| How do stages and components interact? | [Architecture](architecture.md) | Integration lead | Current routing, data, and safety boundaries |
| How do I install, configure, test, and troubleshoot it? | [Setup and Operations](setup-and-operations.md) | Backend / integration | Default and optional development paths |
| Which requirements are complete? | [Prototype Status](prototype-status.md) | Documentation coordinator | Evidence and fresh-verification record |
| What structured facts drive the package? | [Evidence JSON](documentation-evidence.json) | Documentation coordinator | Machine-readable source record |
| How is issue-tracking automation operated? | [Contribution Tracker](CONTRIBUTION_TRACKER.md) | Project automation owner | Separate from product LLM behavior |

## Component documents

| Component | Current record | Narrow authoritative artifacts | Current status |
| --- | --- | --- | --- |
| Frontend | [Frontend component](components/frontend.md) | `website/dashboard/README.md`; backend API contract | Partial |
| Backend | [Backend component](components/backend.md) | [Backend README](../backend/README.md), [API contract](../backend/docs/api-contract.md), [database notes](../backend/docs/azure-database.md) | Partial |
| Malware detection | [Malware-detection component](components/malware-detection.md) | [Analyzer README](../malware_detection/README.md), [report contract](../malware_detection/REPORT_CONTRACT.md), [integration guide](../malware_detection/INTEGRATION.md), [reputation guide](../malware_detection/REPUTATION.md) | Implemented |
| Machine learning | [Machine-learning component](components/machine-learning.md) | [Synthetic workflow](../ML/SYNTHETIC_DATA.md); `ML/` source/tests | Partial |
| Dynamic analysis | [Dynamic-analysis component](components/dynamic-analysis.md) | [Dynamic service README](../dynamic_telemetry/README.md), `dynamic_telemetry/api.py`, backend client/adapter | Partial; live safety/operation not verified |
| LLM/threat intelligence | [LLM/threat-intelligence component](components/llm-threat-intelligence.md) | [Component README](../llm-threat-intelligence/README.md), [status](../llm-threat-intelligence/STATUS.md), backend adapter/bridge | Partial; ATT&CK mapping absent |

## Runtime and schema artifacts

| Artifact | Purpose | Consumers |
| --- | --- | --- |
| [Backend API contract](../backend/docs/api-contract.md) | Routes, request/response shapes, stages, errors, authentication | Frontend and integration |
| [Static analyzer report contract](../malware_detection/REPORT_CONTRACT.md) | PE report semantics and versioning | Backend, dashboard, future static ML, reporting |
| [Static analyzer JSON Schema](../malware_detection/output_schema.json) | Machine validation for report 1.2.0 | Analyzer tests and consumers |
| `backend/scripts/content_analyze.py` | Byte-based format identification and non-PE static evidence | Backend pipeline, Home, LLM |
| `backend/signatures/catalog.json` | Safe demonstration indicators | Backend signature stage |
| [ML sandbox example](../ML/sandbox_example.json) | Behavioral parser example input | ML development |
| [Backend environment template](../backend/.env.example) | Runtime configuration inventory | Developers/operators |
| `dynamic_telemetry/api.py` | Environment-specific FastAPI/KVM/QEMU/Sysmon prototype | Backend sandbox client |
| `llm-threat-intelligence/llm_analyzer.py` | Evidence prompt and optional Groq explanation | Backend LLM bridge |

## Word submission records

| Word file | Scope | Markdown evidence source | Assigned area |
| --- | --- | --- | --- |
| `Sentinel_Backend_Development_Documentation_Form.docx` | API, persistence, queue, auth, routing/pipeline | Backend component, architecture, setup, API contract | D.G / backend |
| `Sentinel_Documentation_All_Rounder_Documentation_Form.docx` | Inventory, milestones, auth/database support | This index, overview, status, setup | Cade / documentation |
| `Sentinel_Dynamic_Analysis_Documentation_Form.docx` | Service source, telemetry, safety gaps | Dynamic component, architecture, status | Vincent and Jarrel / dynamic analysis |
| `Sentinel_Frontend_Development_Documentation_Form.docx` | Screens, submission, history, results, tests | Frontend component, dashboard README, API contract | Sebastian / frontend |
| `Sentinel_LLM_Threat_Intelligence_Documentation_Form.docx` | Demo intelligence, provider/model, prompt, missing mappings | LLM component, architecture, status | J.J / threat intelligence |
| `Sentinel_Machine_Learning_Documentation_Form.docx` | Synthetic data, models, features, threshold, evaluation | ML component, synthetic workflow, status | Axel P and Diego / ML |
| `Sentinel_Malware_Detection_Documentation_Form.docx` | PE evidence, reputation, YARA, contract | Malware-detection component and narrow contracts | Kyle / malware detection |
| `Sentinel_Project_Wide_Documentation_Record.docx` | Requirements, architecture, milestones, risks, evaluation | Overview, architecture, status, this index | Cade / shared project record |

The generator retains recorded historical rows and adds one stable 2026-11-19 reconciliation entry per form. Unknown approvals, milestone dates, production environments, real dataset/model results, provider evaluation, and safety results remain explicit rather than inferred.

## Evidence priority

When artifacts disagree, use this order:

1. Source, executable configuration, and machine-readable schemas.
2. Tests and fresh command output, with environment and date.
3. Narrow owning contracts/READMEs.
4. Core/component summaries.
5. Historical plans, proposal statements, and old test counts.

Source presence is not automatically operational proof. In particular:

- `dynamic_telemetry/api.py` does not prove working sample transfer, EVTX export, containment, or live detonation.
- Synthetic ML tests do not prove real-world malware accuracy.
- An optional Groq call does not provide ATT&CK mapping, citations, or provider evaluation.

## Documentation maintenance

When behavior changes:

1. Update the owning source contract or component guide.
2. Update `documentation-evidence.json` with current status, limitations, and evidence paths.
3. Reconcile `prototype-status.md` plus affected setup/architecture sections.
4. Update documentation integrity tests when a new interface or artifact must remain synchronized.
5. Regenerate Word records with `python3 scripts/update_documentation_forms.py --source-root . --output-dir .`.
6. Validate with `python3 scripts/update_documentation_forms.py --source-root . --output-dir . --check`.
7. Run `python3 -m unittest discover -s tests/documentation -v`.

Do not add a current result without running the exact command and recording the environment/date. Do not turn a blocked or skipped check into a failing assertion count or a passing claim.
