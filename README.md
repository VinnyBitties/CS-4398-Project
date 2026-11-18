# Coin-Flip Defense: Sentinel

Sentinel is a CS 4398 malware-analysis research prototype. It accepts a file or URL, records a scan, runs the analysis stages available in the current configuration, and exposes progress and results through a browser dashboard and REST API.

The project is designed around six analysis stages—signature lookup, static PE analysis, static machine learning, sandbox detonation, behavioral machine learning, and an LLM-generated threat report—but this branch does **not** contain a complete end-to-end implementation of all six. The default runnable path is the backend, dashboard, signature catalog, and mock static analyzer.

> **Safety warning:** Sentinel is not a production antivirus, EDR, or validated malware sandbox. Do not execute real malware. Use inert fixtures until the missing sandbox implementation and its host, network, sample-handling, and snapshot controls have been independently validated.

## Current prototype at a glance

| Area | Current status | What is available |
| --- | --- | --- |
| Frontend dashboard | Partial | Login/guest access, file or URL submission, polling, and stage progress; report history is not connected. |
| Backend API and orchestration | Partial | Accounts, sessions, uploads, URL submissions, SQLite/PostgreSQL storage, job queue, signature lookup, static analyzer runner, and optional stage adapters. |
| Static malware detection | Implemented | Bounded PE parsing, SHA-256, imports, sections, entropy, strings, resources, optional offline reputation and YARA, and report schema 1.2.0. |
| Machine learning | Partial | Behavioral feature extraction, heuristic scoring, optional Random Forest/Isolation Forest training and inference; no dataset or trained artifact is included. |
| Dynamic sandbox | Stubbed/configurable | Backend client, telemetry adapter, and mock integration tests; the sandbox/VM implementation is absent. |
| LLM threat intelligence | Stubbed/configurable | Bounded evidence/indicator adapter and Python bridge; the external component, provider, model, explanation, and ATT&CK mapper are absent. |

The exact status and evidence for every functional and nonfunctional requirement is in [Prototype Status](docs/prototype-status.md).

## Default analysis flow

1. A user submits a file or URL in the dashboard or API.
2. The backend stores the submission, creates a database-backed job, and returns a sample record.
3. The signature stage checks a file SHA-256 or normalized URL/domain against the local catalog.
4. File submissions run through the configured static analyzer. The default is `backend/scripts/mock_analyze.py`; the real analyzer is opt-in.
5. Optional sandbox and behavioral-ML stages run only when `SANDBOX_URL` is configured.
6. The optional threat-intelligence bridge runs only when `LLM_DIR` is configured.
7. The dashboard polls the sample endpoint and displays each stored stage state. Later stage failure does not erase earlier results.

Static ML is not currently registered as a backend pipeline stage. The reports page also does not yet load the stored scan history.

## Quick start

### Prerequisites

- Node.js 22 LTS and npm. The backend documentation records 22 LTS as the tested line.
- Python 3 for the default mock analyzer.
- Optional Python dependencies for the real analyzer or ML tools; see [Setup and Operations](docs/setup-and-operations.md).

### Run the default prototype

```bash
cd backend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:3000/`. The backend serves `website/` from the same origin so the session cookie works without extra CORS setup.

API smoke checks:

```bash
curl http://localhost:3000/api/health
curl -F "file=@test/fixtures/sample.bin" "http://localhost:3000/api/samples?wait=true"
curl -H "Content-Type: application/json" \
  -d '{"url":"http://malware.wicar.org/"}' \
  "http://localhost:3000/api/links?wait=true"
curl http://localhost:3000/api/samples
```

The committed catalog uses safe antivirus test indicators. A catalog match is a pipeline demonstration, not evidence that production threat intelligence is configured.

### Use the real static analyzer

Install its dependency and point the backend at the script:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r malware_detection/requirements.txt
```

Set these values in `backend/.env`:

```dotenv
PYTHON_PATH=../.venv/bin/python
ANALYZER_SCRIPT_PATH=../malware_detection/analyze.py
```

On Windows, use the virtual environment's `python.exe` path. The real analyzer rejects non-PE input; that failure is recorded on the `static_analysis` stage without discarding other stage results.

## Tests and verification

Repository test inventory is broader than the tests observed in the documentation environment. On 2026-11-03:

- `python3 -m unittest discover -s tests/contribution_tracker -v`: **30 tests passed**.
- `cd backend && npm test`: tests did not start because the available npm shim reported unsupported WSL 1.
- Malware-detection tests: did not import because `pefile` was not installed.
- ML tests: did not import because `joblib` was not installed.

These are environment-specific observations, not claims that the blocked suites contain failing assertions. See [Prototype Status](docs/prototype-status.md#verification-record) for the complete record and [Setup and Operations](docs/setup-and-operations.md#troubleshooting) for fixes.

## Repository map

```text
backend/             Express API, persistence, queue, pipeline, auth, adapters
malware_detection/   Static PE evidence, reputation, YARA, schema and tools
ML/                  Behavioral parsing, training, inference and evaluation
website/             Login and analyst dashboard pages
docs/                Project, architecture, status and operational documentation
scripts/             Contribution tracker and documentation utilities
tests/               Project automation and documentation integrity tests
```

## Documentation

- [Project Overview](docs/project-overview.md) — purpose, scope, requirements, team responsibilities, and current-version summary.
- [Architecture](docs/architecture.md) — component boundaries, data flow, persistence, and stage behavior.
- [Setup and Operations](docs/setup-and-operations.md) — installation, configuration, startup, safety, and troubleshooting.
- [Prototype Status](docs/prototype-status.md) — component maturity, requirement traceability, verification, risks, and deferred work.
- [Documentation Index](docs/documentation-index.md) — authoritative sources and Word-form mapping.
- [Frontend](docs/components/frontend.md)
- [Backend](docs/components/backend.md)
- [Malware Detection](docs/components/malware-detection.md)
- [Machine Learning](docs/components/machine-learning.md)
- [Dynamic Analysis](docs/components/dynamic-analysis.md)
- [LLM and Threat Intelligence](docs/components/llm-threat-intelligence.md)

Narrow authoritative contracts remain in [the backend API contract](backend/docs/api-contract.md) and [the static analyzer report contract](malware_detection/REPORT_CONTRACT.md).

## Prototype limitations

- No real sandbox implementation or validated containment environment is included.
- No static-ML backend stage exists.
- No dataset, trained model, benchmark output, or held-out-family result is included.
- No LLM provider, model invocation, explanation, or MITRE ATT&CK mapping implementation is included.
- The dashboard reports page is a placeholder and has no detailed result viewer.
- The default analyzer is a mock; enable the real analyzer explicitly.
- Uploaded files and scan records need a documented retention/deletion policy before use beyond a local demonstration.

## Scope

Sentinel is a capstone research and demonstration system. A real-time antivirus agent, EDR sensor, kernel driver, automated remediation system, memory-forensics platform, network IDS, and cross-platform executable scanner remain out of scope.
