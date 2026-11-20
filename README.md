# Coin-Flip Defense: Sentinel

Sentinel is a CS 4398 malware-analysis research prototype. It accepts files or URLs, records each scan, runs the analysis stages enabled for that submission, and exposes progress and stored evidence through an Express API and browser dashboard.

This documentation describes `dev-branch` as of 2026-11-19. Sentinel is not a production antivirus, EDR, or validated malware sandbox.

> **Safety warning:** Do not execute real malware with this repository. Use inert fixtures only. Although `dynamic_telemetry/` now contains sandbox-service source, sample transfer, EVTX export, network isolation, reset behavior, cleanup, and live containment have not been independently verified.

## Current prototype

| Area | Status | Current capability |
| --- | --- | --- |
| Frontend dashboard | Partial | Account or guest access, multi-format upload and URL submission, progress, paged scan history, behavioral summaries, and detailed PE evidence. Content-analysis and LLM reports do not yet have equivalent full viewers. |
| Backend API and orchestration | Partial | Sessions, uploads, SQLite/PostgreSQL storage, jobs, signatures, byte-based file routing, PE/content analysis, and optional sandbox, behavioral-ML, and LLM stages. Static ML is absent. |
| Static PE detection | Implemented | Bounded PE metadata, imports, sections, entropy, strings, resources, optional offline reputation and YARA, and report schema 1.2.0. The real analyzer is opt-in. |
| Non-PE content analysis | Implemented | Detects file content and inspects Office, PDF, scripts, source, archives, shortcuts, and web formats for bounded static evidence. |
| Behavioral machine learning | Partial | Heuristic scoring plus a reproducible synthetic-data, split, training, threshold, evaluation, artifact-metadata, CLI, and HTTP workflow. No real dataset or trained artifact is committed. |
| Dynamic analysis | Partial, not safety-verified | FastAPI/KVM/QEMU/Sysmon source and backend integration are present; live detonation, transfer, telemetry export, and containment are unverified. |
| LLM and threat intelligence | Partial | Demo indicator lookup plus an optional Groq explanation using `openai/gpt-oss-20b`; no MITRE ATT&CK mapping, citations, or production intelligence feed. |

See [Prototype Status](docs/prototype-status.md) for requirement-level evidence and verification results.

## Default scan flow

For a file submission, the default pipeline is:

1. `signature` checks the file SHA-256 against the local demonstration catalog.
2. `file_type` identifies content from bytes rather than trusting the extension.
3. PE/DOS files use `static_analysis`; recognized non-PE files use `content_analysis`. Unknown classifications run both `static_analysis` and `content_analysis` because they satisfy both current stage predicates.
4. When `SANDBOX_URL` is configured, `sandbox` runs and its usable telemetry is sent to `behavioral_ml`.
5. When `LLM_DIR` is configured, `llm` runs last over bounded earlier-stage evidence and indicators.

URL submissions currently use `signature` and, when configured, `llm`; the backend does not fetch submitted URLs. `static_ml` is not registered in the pipeline.

The dashboard polls stored scan state, loads paged history through `GET /api/samples`, and opens a selected result with `sample_id`. A failed optional stage remains visible without erasing earlier evidence.

## Quick start

### Prerequisites

- Node.js 22 LTS and npm.
- Python 3 for the default file-type/content analyzer and mock PE analyzer.
- Optional isolated Python environments for PE analysis, ML, LLM, or dynamic-service dependencies.

### Run the default local prototype

```bash
cd backend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:3000/`. The backend serves `website/` from the same origin, so the session cookie works without separate CORS configuration.

Safe smoke checks:

```bash
curl http://localhost:3000/api/health
curl -F "file=@test/fixtures/sample.bin" "http://localhost:3000/api/samples?wait=true"
curl -H "Content-Type: application/json" \
  -d '{"url":"http://malware.wicar.org/"}' \
  "http://localhost:3000/api/links?wait=true"
curl "http://localhost:3000/api/samples?limit=20&offset=0"
```

The default file path uses `backend/scripts/mock_analyze.py` for PE-shaped output and `backend/scripts/content_analyze.py` for file identification and non-PE evidence. Catalog matches and content findings demonstrate orchestration; they are not production threat verdicts.

## Optional analysis paths

### Real PE analyzer

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r malware_detection/requirements.txt
```

In `backend/.env`:

```dotenv
PYTHON_PATH=../.venv/bin/python
ANALYZER_SCRIPT_PATH=../malware_detection/analyze.py
```

The `file_type` stage routes recognized non-PE files to `content_analysis`, while the PE analyzer is invoked for PE/DOS or unknown fallback input. Unknown classifications run both `static_analysis` and `content_analysis`. Windows users should set `PYTHON_PATH` to the virtual environment's `python.exe`.

### Richer content analysis

The default content analyzer uses the Python standard library. Optional macro and archive parsers add deeper coverage:

```bash
python -m pip install -r backend/scripts/requirements-content.txt
```

### Behavioral ML

[ML/SYNTHETIC_DATA.md](ML/SYNTHETIC_DATA.md) documents the reproducible synthetic workflow and `ML/predict.py --serve`. Generated labels and metrics are synthetic development evidence, not real-world detection accuracy.

### LLM explanation

Set `LLM_DIR=../llm-threat-intelligence` to enable the local bridge. Without `GROQ_API_KEY`, the stage still returns demo threat intelligence and the evidence prompt with `explanation_status: "skipped"`. With a key, the component calls Groq model `openai/gpt-oss-20b`; provider errors are recorded as an optional explanation error rather than failing the whole stage.

### Dynamic service

`dynamic_telemetry/api.py` is an environment-specific FastAPI/KVM/QEMU prototype. Do not point the backend at it for real malware until the transfer/export gaps and containment controls in [Dynamic Analysis](docs/components/dynamic-analysis.md) have been independently resolved and tested.

## Verification

The repository includes documentation integrity, contribution-tracker, backend, dashboard-browser, ML, and malware-detection suites. Fresh results and exact blockers for this snapshot are maintained in [Prototype Status](docs/prototype-status.md#verification-record). A source file or passing mock test is not evidence that a live sandbox or external provider was exercised.

## Repository map

```text
backend/                  Express API, persistence, queue, pipeline, auth, adapters
malware_detection/        Static PE evidence, reputation, YARA, schema and tools
ML/                       Behavioral data, training, inference and evaluation workflow
dynamic_telemetry/        Environment-specific KVM/QEMU/Sysmon service prototype
llm-threat-intelligence/  Demo intelligence and optional Groq explanation
website/                  Login, scan center, history, and report views
docs/                     Project, architecture, status, component and operations docs
scripts/                  Contribution tracker and documentation-form generator
tests/                    Project automation and documentation integrity tests
```

## Documentation

- [Project Overview](docs/project-overview.md) — baseline, current scope, requirements, stack, and responsibilities.
- [Architecture](docs/architecture.md) — components, routing, persistence, optional services, and failure behavior.
- [Setup and Operations](docs/setup-and-operations.md) — installation, configuration, startup, testing, safety, and troubleshooting.
- [Prototype Status](docs/prototype-status.md) — maturity, requirement traceability, verification, risks, and deferred work.
- [Documentation Index](docs/documentation-index.md) — authoritative sources and Word-record mapping.
- [Frontend](docs/components/frontend.md)
- [Backend](docs/components/backend.md)
- [Malware Detection](docs/components/malware-detection.md)
- [Machine Learning](docs/components/machine-learning.md)
- [Dynamic Analysis](docs/components/dynamic-analysis.md)
- [LLM and Threat Intelligence](docs/components/llm-threat-intelligence.md)

Exact REST fields remain authoritative in the [backend API contract](backend/docs/api-contract.md); exact PE report semantics remain authoritative in the [static analyzer report contract](malware_detection/REPORT_CONTRACT.md).

## Scope and limitations

Sentinel is a capstone research and demonstration system. Real-time antivirus/EDR agents, kernel drivers, automatic remediation, memory forensics, network IDS, a production malware sandbox, and measured real-world detection efficacy remain out of scope for this snapshot.

Uploaded files and scan records also need approved retention, deletion, access, and backup policies before use beyond a disposable local demonstration.
