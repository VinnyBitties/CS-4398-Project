# Documentation Index

## How to use this index

Start with the artifact matching your task. Broad documents summarize and link; narrow component contracts remain authoritative for exact fields and behavior. Status statements are current as of 2026-11-03 unless a document says otherwise.

## Core documents

| Audience or question | Authoritative document | Owner | Status |
| --- | --- | --- | --- |
| What is Sentinel and how do I start it? | [Root README](../README.md) | Documentation / integration | Current prototype entry point |
| What was approved and what exists now? | [Project Overview](project-overview.md) | Documentation coordinator | Current baseline and status summary |
| How do components and stages interact? | [Architecture](architecture.md) | Integration lead | Current branch architecture |
| How do I install, configure, and troubleshoot it? | [Setup and Operations](setup-and-operations.md) | Backend / integration | Current runnable and optional paths |
| Which requirements are complete? | [Prototype Status](prototype-status.md) | Documentation coordinator | Evidence-based traceability |
| What facts drive the documentation? | [Evidence JSON](documentation-evidence.json) | Documentation coordinator | Machine-readable source record |
| How is issue-tracking automation operated? | [Contribution Tracker](CONTRIBUTION_TRACKER.md) | Project automation owner | Separate from product LLM behavior |

## Component documents

| Component | Current record | Narrow authoritative artifacts | Current status |
| --- | --- | --- | --- |
| Frontend | [Frontend component](components/frontend.md) | `website/` source; backend API contract | Partial |
| Backend | [Backend component](components/backend.md) | [Backend README](../backend/README.md), [API contract](../backend/docs/api-contract.md), [database notes](../backend/docs/azure-database.md) | Partial |
| Malware detection | [Malware-detection component](components/malware-detection.md) | [Analyzer README](../malware_detection/README.md), [report contract](../malware_detection/REPORT_CONTRACT.md), [integration guide](../malware_detection/INTEGRATION.md), [reputation guide](../malware_detection/REPUTATION.md) | Implemented |
| Machine learning | [Machine-learning component](components/machine-learning.md) | `ML/` source and test module | Partial |
| Dynamic analysis | [Dynamic-analysis component](components/dynamic-analysis.md) | Backend sandbox client/adapter only | Stubbed/configurable |
| LLM/threat intelligence | [LLM/threat-intelligence component](components/llm-threat-intelligence.md) | Backend input adapter and bridge only | Stubbed/configurable |

## Word submission records

| Word file | Scope | Markdown evidence source | Assigned area |
| --- | --- | --- | --- |
| `Sentinel_Backend_Development_Documentation_Form.docx` | API, persistence, queue, auth, pipeline | Backend component, architecture, setup, API contract | D.G / backend |
| `Sentinel_Documentation_All_Rounder_Documentation_Form.docx` | Documentation inventory, milestones, auth/database support | This index, overview, status, setup | Cade / documentation |
| `Sentinel_Dynamic_Analysis_Documentation_Form.docx` | Sandbox environment, telemetry, safety | Dynamic-analysis component, status | Vincent and Jarrel / dynamic analysis |
| `Sentinel_Frontend_Development_Documentation_Form.docx` | Screens, submission, results, accessibility | Frontend component, API contract | Sebastian / frontend |
| `Sentinel_LLM_Threat_Intelligence_Documentation_Form.docx` | Provider/prompt/evidence/mappings | LLM component, architecture, status | J.J / threat intelligence |
| `Sentinel_Machine_Learning_Documentation_Form.docx` | Data, models, features, evaluation | ML component, status | Axel P and Diego / ML |
| `Sentinel_Malware_Detection_Documentation_Form.docx` | Static evidence, reputation, YARA, contract | Malware-detection component and narrow contracts | Kyle / malware detection |
| `Sentinel_Project_Wide_Documentation_Record.docx` | Requirements, architecture, milestones, risks, evaluation | Overview, architecture, status, this index | Cade / shared project record |

The forms summarize current evidence and retain their historical rows. Unknown approvals, dates, models, datasets, metrics, and safety results are marked as not recorded or requiring confirmation rather than inferred.

## Source and schema artifacts

| Artifact | Purpose | Consumer |
| --- | --- | --- |
| [Backend API contract](../backend/docs/api-contract.md) | Routes, request/response shapes, errors, authentication | Frontend and integration |
| [Static analyzer report contract](../malware_detection/REPORT_CONTRACT.md) | JSON report semantics and versioning | Backend, ML, dashboard, reporting |
| [Static analyzer JSON Schema](../malware_detection/output_schema.json) | Machine validation for report 1.2.0 | Analyzer tests and consumers |
| [Signature catalog](../backend/signatures/catalog.json) | Safe demonstration indicators | Backend signature stage |
| [ML sandbox example](../ML/sandbox_example.json) | Behavioral parser example input | ML development |
| [Backend environment template](../backend/.env.example) | Runtime configuration inventory | Operators and developers |

## Documentation maintenance

When behavior changes:

1. Update the owning source contract or component documentation.
2. Update `documentation-evidence.json` with the new status and evidence path.
3. Reconcile `prototype-status.md` and any affected setup or architecture section.
4. Regenerate the affected Word forms with `scripts/update_documentation_forms.py`.
5. Run `python3 -m unittest discover -s tests/documentation -v`.

Do not add current test results without running the exact command and recording its environment and date.
