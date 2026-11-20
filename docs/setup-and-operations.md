# Sentinel Setup and Operations

## Supported use

These instructions cover local development and inert demonstrations for `dev-branch` as of 2026-11-19.

> **Safety:** Do not execute real malware. The committed dynamic-service source has not established working sample transfer, EVTX export, network isolation, failure-safe reset, cleanup, or host containment. Use files you are authorized to analyze and disposable local data.

## Prerequisites

| Capability | Required software |
| --- | --- |
| Default backend/site | Node.js 22 LTS, npm, Python 3 |
| Real PE analyzer | Python 3 plus `malware_detection/requirements.txt` |
| Optional YARA/schema development | `malware_detection/requirements-dev.txt` |
| Richer Office/archive content analysis | `backend/scripts/requirements-content.txt` |
| Behavioral ML workflow/service | Root `requirements.txt` (`joblib`, NumPy, scikit-learn) |
| Optional Groq explanation | Root `requirements.txt` plus `GROQ_API_KEY` |
| Dynamic-service development | Linux/KVM/QEMU/libvirt, Windows guest, QEMU Guest Agent, Sysmon, and `dynamic_telemetry/requirements.txt` |
| Browser verification | Backend dev dependencies and a compatible Playwright Chromium/Chrome executable |

Use isolated Python virtual environments. Joblib artifacts and uploaded samples are untrusted data; never load or execute artifacts from an unknown source.

## Default local startup

```bash
cd backend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:3000/`. The backend serves `website/` by default, so pages and API share an origin and the HttpOnly session cookie works without separate CORS configuration.

The default file pipeline is:

```text
signature → file_type → static_analysis (PE/DOS/unknown)
                      → content_analysis (every non-PE, including unknown)
```

`static_analysis` uses `backend/scripts/mock_analyze.py` unless configured otherwise. `file_type` and `content_analysis` use `backend/scripts/content_analyze.py` and Python's standard library by default.

Unknown classifications run both `static_analysis` and `content_analysis`; this is the current predicate behavior, not an exclusive branch.

Safe API checks:

```bash
curl http://localhost:3000/api/health
curl -F "file=@test/fixtures/sample.bin" "http://localhost:3000/api/samples?wait=true"
curl -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/"}' \
  "http://localhost:3000/api/links?wait=true"
curl "http://localhost:3000/api/samples?limit=20&offset=0"
```

The default fixture and catalog demonstrate routing and persistence, not malicious/benign accuracy.

## File-type and content analysis

The browser exposes a broad supported-extension list, but the backend does not trust the filename. `file_type` uses magic bytes, container structure, and bounded text heuristics. It reports extension mismatch and filename tricks when applicable.

Recognized non-PE formats use `content_analysis`, including:

- Office/OLE/OOXML, RTF, OneNote, and CSV.
- PDF.
- PowerShell, batch, VBScript/JScript, WSF/HTA, Python, and shell scripts.
- C/C++, C#, Go, Rust, and Java source.
- ZIP, tar, gzip, and optional RAR/7z/ISO inspection.
- LNK/URL shortcuts, HTML, SVG, and CHM/web content.

Install optional parsers in the backend's Python environment for deeper macro and archive inspection:

```bash
python -m pip install -r backend/scripts/requirements-content.txt
```

Without optional packages, the analyzer reports reduced coverage; it must not infer safety.

Disable both stages only when deliberately testing the legacy fallback path:

```dotenv
CONTENT_ANALYZER_PATH=
```

## Real PE analyzer

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r malware_detection/requirements.txt
```

Configure `backend/.env`:

```dotenv
PYTHON_PATH=../.venv/bin/python
ANALYZER_SCRIPT_PATH=../malware_detection/analyze.py
ANALYZER_TIMEOUT_MS=15000
```

On Windows, use the virtual environment's `python.exe`. `file_type` routes recognized non-PE uploads away from the PE analyzer. Unknown content still uses the PE fallback and can produce a controlled PE-format stage failure.

Optional offline reputation and trusted YARA sources are configured through the component tools/environment described in [malware_detection/README.md](../malware_detection/README.md). A missing feed or no match is not a benign verdict.

## Behavioral ML workflow

Install dependencies in a separate environment:

```bash
python3 -m venv .venv-ml
source .venv-ml/bin/activate
python -m pip install -r requirements.txt
```

Run the complete ML regression suite:

```bash
python -B -m unittest discover -s ML -p "test_*.py" -v
```

[ML/SYNTHETIC_DATA.md](../ML/SYNTHETIC_DATA.md) gives exact generation, export, split, training, validation-threshold, evaluation, and HTTP-service commands. The core service command is:

```bash
python ML/predict.py --serve \
  --classifier-model models/random_forest.joblib \
  --anomaly-model models/isolation_forest.joblib \
  --threshold 0.5
```

Configure a local backend to call the analysis endpoint:

```dotenv
BEHAVIORAL_ML_URL=http://127.0.0.1:8000/analyze
BEHAVIORAL_ML_TIMEOUT_MS=15000
```

The backend only adds `behavioral_ml` when `SANDBOX_URL` is also set. Synthetic labels, thresholds, and metrics are development evidence, not real-world detection accuracy. Load only trusted joblib files.

## Optional LLM and demo threat intelligence

Install the root Python requirements in the interpreter named by `PYTHON_PATH`, then set:

```dotenv
LLM_DIR=../llm-threat-intelligence
LLM_BRIDGE_PATH=./scripts/llm_bridge.py
LLM_TIMEOUT_MS=30000
```

The stage runs for files and links after earlier applicable stages.

- Without `GROQ_API_KEY`, demo indicator lookup and prompt construction still complete; `explanation_status` is `skipped`.
- With a key, `llm_analyzer.py` calls Groq model `openai/gpt-oss-20b` with `max_tokens=500`.
- Provider/network/key errors produce `explanation_status: "error"` and do not discard the prompt or demo intelligence.

Never commit the key. Before sending non-synthetic data externally, approve provider retention/training terms, data classes, redaction, and cost controls. The current component has no ATT&CK mapping or evidence-citation schema.

## Dynamic-service source

`dynamic_telemetry/api.py` defines `/health` and `/detonate` using FastAPI, KVM/QEMU/libvirt commands, QEMU Guest Agent calls, and Sysmon EVTX parsing. Its constants, service account, VM name, snapshot name, paths, and example network address are deployment-specific examples.

Do not copy the committed address as a default. A development operator would need to supply and review all of the following outside source:

1. Dedicated Linux virtualization host and hardened Windows guest.
2. Exact VM/snapshot identity and a proven revert procedure.
3. A sample-transfer mechanism that does not expose host shares or credentials.
4. A verified EVTX export mechanism from guest to host.
5. Network isolation/simulation policy and egress tests.
6. Authentication, upload limits, resource limits, cleanup, logging, and retention.
7. Inert end-to-end canary tests proving transfer, execution, telemetry, and reset.
8. Independent containment review before any real malware.

After those controls exist, configure the backend with the reviewed service base URL:

```dotenv
SANDBOX_URL=http://sandbox-host.example:8000
SANDBOX_DETONATION_SECONDS=15
SANDBOX_TIMEOUT_MS=120000
```

The backend appends `/detonate` and serializes requests within one Node process. That client lock is not VM isolation or distributed coordination.

## Environment configuration

Use `backend/.env.example` as the exhaustive template.

| Group | Variables | Purpose |
| --- | --- | --- |
| Server/site | `PORT`, `WEBSITE_DIR`, `CORS_ORIGINS` | Listen port, static site, development origins |
| Database | `DATABASE_URL`, `DATABASE_PATH`, `DATABASE_SSL`, `DATABASE_POOL_SIZE`, `WORKER_ID` | PostgreSQL or SQLite and local job ownership |
| Upload/queue | `UPLOAD_DIR`, `MAX_UPLOAD_BYTES`, `JOB_CONCURRENCY`, `WAIT_TIMEOUT_MS` | Storage, limits, concurrency, synchronous wait |
| Python/PE | `PYTHON_PATH`, `ANALYZER_SCRIPT_PATH`, `ANALYZER_TIMEOUT_MS` | PE analyzer subprocess |
| File/content | `CONTENT_ANALYZER_PATH`, `CONTENT_ANALYZER_TIMEOUT_MS` | Default byte detection/non-PE analysis |
| Signatures | `SIGNATURE_CATALOG_PATH`, `SIGNATURE_HASHLIST_PATH` | Curated catalog and optional bulk hashes |
| Sandbox | `SANDBOX_URL`, `SANDBOX_DETONATION_SECONDS`, `SANDBOX_TIMEOUT_MS` | Optional detonation service |
| Behavioral ML | `BEHAVIORAL_ML_URL`, `BEHAVIORAL_ML_TIMEOUT_MS` | Optional score service after sandbox |
| LLM | `LLM_DIR`, `LLM_BRIDGE_PATH`, `LLM_TIMEOUT_MS`, `GROQ_API_KEY` | Optional demo intelligence/explanation |
| Accounts | `SESSION_TTL_HOURS`, `COOKIE_SECURE`, `ALLOW_REGISTRATION`, `MAX_FAILED_LOGINS` | Session and registration controls |

Never commit `.env`, API keys, feeds, uploads, databases, reports containing sensitive data, or model artifacts with unknown provenance.

## Test commands

From the repository root unless noted:

```bash
python3 -m unittest discover -s tests/documentation -v
python3 -m unittest discover -s tests/contribution_tracker -v
python3 -B -m unittest discover -s ML -p "test_*.py" -v
python3 -m unittest discover -s malware_detection/tests -v
```

```bash
cd backend
npm test
npm run test:dashboard
```

Browser tests require a Playwright Chromium installation or `DASHBOARD_BROWSER_PATH` pointing to compatible Chrome. The browser suite uses synthetic fixtures and a temporary inert backend workflow; it does not verify live detonation.

Fresh results and environment-specific blockers are recorded in [Prototype Status](prototype-status.md#verification-record).

## Troubleshooting

### `npm` reports unsupported WSL or cannot find Node

The shell may be resolving a Windows npm shim from an unsupported WSL environment. Use WSL 2, Windows PowerShell with supported Node.js, or a Linux Node installation. This is a tooling startup failure, not a failed assertion.

### `ModuleNotFoundError: pefile`

Activate the PE environment and install `malware_detection/requirements.txt`.

### `ModuleNotFoundError: joblib`, `numpy`, or `sklearn`

Activate the ML environment and install the root `requirements.txt`.

### Optional macro/archive depth is unavailable

Install `backend/scripts/requirements-content.txt`. Re-run with an inert fixture and inspect the report's tool/coverage notes.

### A PE stage reports a format error

Check the preceding `file_type` result. A recognized non-PE reaches `content_analysis`. Unknown input also reaches the PE analyzer and can fail there safely while its content-analysis result remains separate.

### A scan has no `file_type` or `content_analysis` row

Check whether `CONTENT_ANALYZER_PATH` is empty, the Python stage failed, or the file was routed to PE analysis. A skipped conditional stage creates no result row.

### Sandbox reports no telemetry

Do not substitute zero counts. Verify sample transfer, guest execution, EVTX export, parser output, and response shape. Treat the run as inconclusive/failed.

### LLM explanation is skipped or errored

Inspect `explanation_status` and `explanation_error`. `skipped` normally means no `GROQ_API_KEY`; `error` means the optional call failed. Demo threat intelligence and the prompt may still be available.

### Reports page lacks a content-analysis/LLM detail view

This is a current UI limitation. Home displays summarized content findings; the reports page specializes in PE, signature, sandbox, and behavioral evidence.

### Login cookie is missing

Prefer serving the site from the backend. For a separate origin, add the exact origin to `CORS_ORIGINS`, use credentialed requests, and leave `COOKIE_SECURE=false` only for local HTTP.

## Shutdown and cleanup

Stop backend and optional services with their process controls. Before deleting anything, resolve the explicit `UPLOAD_DIR`, `DATABASE_PATH`, generated ML output directory, and any sandbox staging directory. They can contain user data or untrusted files.

The repository supplies no deletion endpoint or retention job. Prefer disposable directories and a local database for demonstrations. Never recursively delete a broad directory or shared database as a cleanup shortcut.
