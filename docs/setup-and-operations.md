# Setup and Operations

## Purpose

This guide covers the runnable default prototype, optional component configuration, safe operation, and troubleshooting. Commands assume the repository root unless they begin with `cd backend` or `cd ML`.

## Safety before setup

Use only inert fixtures or files you are authorized to analyze. The current branch does not contain or validate the promised sandbox isolation controls. Do not configure `SANDBOX_URL` for real malware until the VM, network boundary, snapshot restoration, sample transfer, and log export have been reviewed and tested independently.

Never commit malware samples, `.env` files, API keys, database credentials, session data, provider tokens, uploaded files, SQLite databases, reputation databases, model artifacts, private datasets, or reports containing sensitive identifiers.

## Prerequisites

### Default web prototype

- Node.js 22 LTS and npm.
- Python 3 available as `python3` or configured through `PYTHON_PATH`.
- A modern browser.

### Real static analyzer

- Python 3.
- `pefile` from `malware_detection/requirements.txt`.
- Optional development dependencies from `malware_detection/requirements-dev.txt` for schema/YARA tests.

### Machine learning tools

- `joblib`, `numpy`, and `scikit-learn` from the root `requirements.txt`.
- A compatible telemetry report, and optional trained `.joblib` artifacts.

The repository does not supply the sandbox hypervisor/guest prerequisites or an LLM provider SDK.

## Default local startup

```bash
cd backend
npm install
cp .env.example .env
npm run dev
```

Expected default behavior:

- Site and API listen on `http://localhost:3000`.
- `website/` is served from the same origin.
- SQLite is created at the configured `DATABASE_PATH` on first start.
- Uploads are stored beneath `backend/uploads/` unless overridden.
- Signature lookup and the mock static analyzer run.
- Sandbox, behavioral ML, and LLM stages are disabled.

Check health:

```bash
curl http://localhost:3000/api/health
```

Run a safe API demonstration with the inert backend fixture:

```bash
curl -F "file=@backend/test/fixtures/sample.bin" \
  "http://localhost:3000/api/samples?wait=true"
```

The dashboard's browser picker accepts `.exe`; use a known inert PE fixture for UI demonstrations.

## Accounts and guest use

Accounts are optional by default. Registering signs the new user in. Guest submissions are stored with a null user identity, and guest history queries return guest scans. To disable new registrations:

```dotenv
ALLOW_REGISTRATION=false
```

For HTTPS deployment:

```dotenv
COOKIE_SECURE=true
```

This flag prevents the session cookie from traveling over plain HTTP. It does not configure TLS; a secure deployment still needs an HTTPS reverse proxy or platform endpoint.

## Real static analyzer

Create an isolated Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r malware_detection/requirements.txt
```

Set the backend environment:

```dotenv
PYTHON_PATH=../.venv/bin/python
ANALYZER_SCRIPT_PATH=../malware_detection/analyze.py
ANALYZER_TIMEOUT_MS=15000
```

Windows paths may point to `.venv\Scripts\python.exe`. Relative backend paths resolve from `backend/`, not the shell's current directory.

Direct analyzer usage:

```bash
python3 malware_detection/analyze.py path/to/inert.exe > report.json
python3 malware_detection/validate_report.py --require-current report.json
```

Optional offline enrichment:

```bash
python3 malware_detection/analyze.py path/to/inert.exe \
  --hash-cache path/to/reputation.sqlite \
  --yara-rules malware_detection/rules/wannacry.yar
```

The analyzer performs no reputation network lookup. `update_reputation.py` is the separate, deliberate import/download path. Treat third-party rules and feeds as untrusted inputs until their source, license, update time, and coverage are recorded.

## Behavioral ML tools

Install the root Python requirements in an isolated environment:

```bash
python3 -m venv .venv-ml
source .venv-ml/bin/activate
pip install -r requirements.txt
```

Heuristic CLI analysis:

```bash
cd ML
python3 predict.py --file sandbox_example.json
```

Local HTTP service:

```bash
cd ML
python3 predict.py --serve --host 127.0.0.1 --port 8000
```

The backend default `BEHAVIORAL_ML_URL` is `http://127.0.0.1:8000/`, but it calls this service only when `SANDBOX_URL` enables the preceding sandbox stage.

Optional model arguments:

```bash
python3 predict.py --file sandbox_example.json \
  --classifier-model random_forest.joblib \
  --anomaly-model isolation_forest.joblib
```

No model files are committed. Heuristic output uses `prediction_source: heuristic`; do not describe that score as trained-model probability.

## Optional sandbox integration

Backend configuration:

```dotenv
SANDBOX_URL=http://127.0.0.1:9000
SANDBOX_DETONATION_SECONDS=15
SANDBOX_TIMEOUT_MS=120000
BEHAVIORAL_ML_URL=http://127.0.0.1:8000/
BEHAVIORAL_ML_TIMEOUT_MS=15000
```

Expected service contract:

- `POST /detonate` accepts multipart file content and a timeout.
- Response is JSON with usable telemetry and a parseable execution result.
- The backend permits only one concurrent detonation because the design assumes one VM.
- Empty or parse-error telemetry fails the sandbox stage and is not forwarded as benign behavior.

The external service and VM do not exist in this branch. Configuration alone does not create a safe sandbox.

## Optional LLM/threat-intelligence integration

```dotenv
LLM_DIR=../llm-threat-intelligence
LLM_BRIDGE_PATH=./scripts/llm_bridge.py
LLM_TIMEOUT_MS=30000
```

`LLM_DIR` must contain the external Python component expected by `backend/scripts/llm_bridge.py`. The current branch defines no provider, model, prompt version, credential name, cost control, redaction policy, explanation schema, or MITRE mapping validator. Do not enable external transmission until those decisions and the data policy are documented.

## Database options

### SQLite default

```dotenv
DATABASE_PATH=./data/sentinel.db
```

SQLite requires no separate service and is appropriate for a single local backend.

### PostgreSQL

```dotenv
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/DATABASE
DATABASE_SSL=true
DATABASE_POOL_SIZE=5
WORKER_ID=developer-machine:3000
```

Use a separate disposable database for tests through `TEST_DATABASE_URL`. The PostgreSQL test command empties its test tables; never point it at shared or production data. See [Azure database notes](../backend/docs/azure-database.md).

## Configuration reference

| Group | Variables | Operational meaning |
| --- | --- | --- |
| Server/site | `PORT`, `WEBSITE_DIR`, `CORS_ORIGINS` | Listener, static site root, and credentialed development origins |
| Upload | `UPLOAD_DIR`, `MAX_UPLOAD_BYTES` | Local storage and maximum accepted multipart file size |
| Database | `DATABASE_PATH`, `DATABASE_URL`, `DATABASE_SSL`, `DATABASE_POOL_SIZE` | Persistence backend and connection behavior |
| Queue | `WORKER_ID`, `JOB_CONCURRENCY`, `WAIT_TIMEOUT_MS` | Host ownership, local parallelism, and synchronous-wait limit |
| Static analysis | `PYTHON_PATH`, `ANALYZER_SCRIPT_PATH`, `ANALYZER_TIMEOUT_MS` | Python process and analyzer selection |
| Signatures | `SIGNATURE_CATALOG_PATH`, `SIGNATURE_HASHLIST_PATH` | Curated catalog and optional bulk SHA-256 list |
| URLs | `MAX_URL_LENGTH` | URL submission length limit |
| Sandbox | `SANDBOX_URL`, `SANDBOX_DETONATION_SECONDS`, `SANDBOX_TIMEOUT_MS` | Optional detonation stage |
| Behavioral ML | `BEHAVIORAL_ML_URL`, `BEHAVIORAL_ML_TIMEOUT_MS` | Optional scoring service after sandbox |
| Threat intelligence | `LLM_DIR`, `LLM_BRIDGE_PATH`, `LLM_TIMEOUT_MS` | Optional external bridge stage |
| Authentication | `SESSION_TTL_HOURS`, `COOKIE_SECURE`, `ALLOW_REGISTRATION`, `MAX_FAILED_LOGINS` | Session lifetime and account controls |

Use `backend/.env.example` as the exhaustive value template. Do not commit the copied `.env`.

## Test commands

```bash
cd backend
npm test
cd ..
```

```bash
python3 -m unittest discover -s malware_detection/tests -v
```

```bash
cd ML
python3 -m unittest test_report_parser -v
cd ..
```

```bash
python3 -m unittest discover -s tests/contribution_tracker -v
```

```bash
python3 -m unittest discover -s tests/documentation -v
```

## Troubleshooting

### npm reports WSL 1 is unsupported

The shell is finding a Windows npm shim from WSL 1 rather than a supported Linux Node installation. Use WSL 2, run the backend from Windows PowerShell with a supported Node.js installation, or install Node.js inside a supported Linux environment. This is an environment startup failure, not a Node test assertion failure.

### `ModuleNotFoundError: pefile`

Activate the analyzer virtual environment and run `pip install -r malware_detection/requirements.txt`.

### `ModuleNotFoundError: joblib`

Activate the ML virtual environment and run `pip install -r requirements.txt`.

### Static analysis reports `PEFormatError`

The real analyzer received a file that is empty, truncated, not a PE, or otherwise malformed. Verify the input is an inert Windows PE. The stage failure is expected behavior; it should not crash the whole server.

### A scan completes with skipped stages

Unset optional components are omitted by design. Check `SANDBOX_URL` and `LLM_DIR`, then compare the active list in `backend/src/pipeline/stages.js`. Static ML will remain absent because it has no registered stage.

### Sandbox stage reports no telemetry or parse error

Do not substitute zero counts. Verify the external service copied the sample into the VM, exported the log, and returned the shape expected by `sandboxToMl.js`. Treat this as an integration failure.

### Login cookie is missing

Serve the site from the backend when possible. For a separate development origin, add that exact origin to `CORS_ORIGINS`, keep `credentials: include`, and leave `COOKIE_SECURE=false` only for local HTTP.

## Shutdown and cleanup

Stop the backend and optional services with their process controls. Before deleting data, confirm paths in `.env`; uploads and databases may contain user data. This repository provides no deletion endpoint or automated retention job. Prefer a disposable development database and inert upload directory for demonstrations.

Do not recursively delete broad directories or a shared PostgreSQL database as a cleanup shortcut.
