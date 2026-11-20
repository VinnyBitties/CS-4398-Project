# Sentinel Backend

The backend is Sentinel's Express REST API, database, job queue, analysis orchestrator, and static-site host. This guide describes `dev-branch` on 2026-11-19.

## Quick start

```bash
cd backend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:3000/`. The default path needs Node.js plus Python 3 and uses local SQLite, the safe signature catalog, byte-based file detection/content analysis, and a mock PE analyzer.

> Use inert fixtures only. Configuring `SANDBOX_URL` does not prove that the dynamic environment is safe for real malware.

## API

- `GET /api/health`
- `POST /api/auth/register`, `/login`, `/logout`; `GET /api/auth/me`
- `POST /api/samples` multipart field `file`
- `POST /api/links` JSON `{ "url": "https://..." }`
- `GET /api/samples?limit=&offset=` newest-first scoped history
- `GET /api/samples/:id` scoped scan detail

Submit routes return `202` by default. `?wait=true` waits up to `WAIT_TIMEOUT_MS`, returning `201` only when the job finishes in time. Exact fields/errors are in [docs/api-contract.md](docs/api-contract.md).

## Pipeline

`src/pipeline/stages.js` defines the order:

1. `signature` for files and links.
2. `file_type` for files when `CONTENT_ANALYZER_PATH` is nonempty.
3. `static_analysis` for PE/DOS, unknown fallback, or missing type output; `content_analysis` for every detected non-PE format. Unknown classifications run both `static_analysis` and `content_analysis`.
4. `sandbox` and `behavioral_ml` when `SANDBOX_URL` is set.
5. `llm` when `LLM_DIR` is set.

`static_ml` is not registered.

A conditional stage that does not apply creates no result row. A thrown stage error is stored on that stage and later stages are still considered.

### File type and non-PE content

`scripts/content_analyze.py` identifies content from bytes and gathers bounded evidence from Office, PDF, scripts, source, archives, shortcuts, web content, and generic binaries. It uses the standard library by default; `scripts/requirements-content.txt` adds deeper macro and RAR/7z/ISO inspection.

```dotenv
CONTENT_ANALYZER_PATH=./scripts/content_analyze.py
CONTENT_ANALYZER_TIMEOUT_MS=30000
```

Set `CONTENT_ANALYZER_PATH=` only to disable both `file_type` and `content_analysis` deliberately.

### PE analyzer

The default `scripts/mock_analyze.py` emits inert PE-shaped data. To use the real analyzer:

```bash
python3 -m venv ../.venv
source ../.venv/bin/activate
python -m pip install -r ../malware_detection/requirements.txt
```

```dotenv
PYTHON_PATH=../.venv/bin/python
ANALYZER_SCRIPT_PATH=../malware_detection/analyze.py
```

The backend accepts PE report schema 1.0.0 through 1.2.0. Recognized non-PE content other than the `unknown` category is routed away from this stage. Unknown fallback input also reaches content analysis and may fail static analysis with a controlled PE-format error.

### Sandbox and behavioral ML

The backend posts multipart files to `<SANDBOX_URL>/detonate`, validates usable telemetry, normalizes known field variants, and calls `BEHAVIORAL_ML_URL`.

The checked-in `dynamic_telemetry/api.py` does not yet demonstrate working guest sample transfer or EVTX export. Mock client/adapter tests are not live detonation or containment evidence.

### LLM and demo intelligence

Set `LLM_DIR=../llm-threat-intelligence` to enable the final stage. The bridge returns demo indicator results and an evidence prompt. Explanation status is:

- `generated`: optional Groq call succeeded.
- `skipped`: no `GROQ_API_KEY`.
- `error`: optional provider call failed.
- `not_generated`: loaded component has no generator.

With a key, the committed component requests Groq model `openai/gpt-oss-20b`. Missing credentials or provider errors do not discard prompt/intelligence output. ATT&CK mapping is not implemented.

## Persistence, queue, and sessions

`src/db.js` exposes one logical schema over SQLite or PostgreSQL. Uploaded files stay on the receiving host, so `WORKER_ID` limits shared-database job ownership. The queue runs inside one Node process with configurable concurrency and re-queues interrupted owned jobs at startup.

Passwords use scrypt. The HttpOnly session cookie contains a random token whose SHA-256 is stored server-side. Account use is optional; scans are scoped to the signed-in user or guest scope.

## Configuration groups

| Area | Variables |
| --- | --- |
| Server/site | `PORT`, `WEBSITE_DIR`, `CORS_ORIGINS` |
| Database | `DATABASE_URL`, `DATABASE_PATH`, `DATABASE_SSL`, `DATABASE_POOL_SIZE`, `WORKER_ID` |
| Upload/jobs | `UPLOAD_DIR`, `MAX_UPLOAD_BYTES`, `JOB_CONCURRENCY`, `WAIT_TIMEOUT_MS` |
| PE/content | `PYTHON_PATH`, `ANALYZER_SCRIPT_PATH`, `ANALYZER_TIMEOUT_MS`, `CONTENT_ANALYZER_PATH`, `CONTENT_ANALYZER_TIMEOUT_MS` |
| Signatures | `SIGNATURE_CATALOG_PATH`, `SIGNATURE_HASHLIST_PATH` |
| Sandbox/ML | `SANDBOX_URL`, `SANDBOX_DETONATION_SECONDS`, `SANDBOX_TIMEOUT_MS`, `BEHAVIORAL_ML_URL`, `BEHAVIORAL_ML_TIMEOUT_MS` |
| LLM | `LLM_DIR`, `LLM_BRIDGE_PATH`, `LLM_TIMEOUT_MS`, inherited `GROQ_API_KEY` |
| Accounts | `SESSION_TTL_HOURS`, `COOKIE_SECURE`, `ALLOW_REGISTRATION`, `MAX_FAILED_LOGINS` |

See [.env.example](.env.example) for defaults and comments. Never commit `.env`, credentials, feeds, uploads, or databases.

## Tests

```bash
npm test
```

This runs `test/*.test.js`, including auth, routes, persistence, queue, catalog, content analysis, dashboard data, HTTP stages, sandbox/ML, LLM, and real-analyzer boundaries. Tests use isolated SQLite/mock services; real-analyzer cases can skip without `pefile`.

```bash
npm run test:dashboard
```

This runs Playwright tests in `test/dashboard/` and requires a compatible browser or `DASHBOARD_BROWSER_PATH`. The suite uses synthetic fixtures and a temporary inert backend; it does not call a live sandbox/provider.

For a disposable PostgreSQL test database:

```bash
TEST_DATABASE_URL=postgres://user:pass@localhost:5432/sentinel_test \
TEST_DATABASE_SSL=false npm run test:pg
```

The PostgreSQL suite empties its test tables. Never point it at shared/project data.

Fresh command results are recorded in [the project status](../docs/prototype-status.md#verification-record).

## Current limitations

- No static-ML stage or unified overall verdict.
- Default PE output is a mock.
- Dynamic safety/live operation is unverified.
- Optional ML/LLM services require separate dependency and policy setup.
- Single-process queue and host-local uploads limit horizontal scaling.
- No upload/record deletion endpoint or retention job.
- No production audit/metrics/tracing, artifact storage, TLS, backup, or secret manager.

## Related documentation

- [API contract](docs/api-contract.md)
- [Database notes](docs/azure-database.md)
- [Backend component record](../docs/components/backend.md)
- [Setup and Operations](../docs/setup-and-operations.md)
