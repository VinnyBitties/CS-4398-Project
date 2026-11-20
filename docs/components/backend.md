# Backend API and Orchestration

## Purpose and status

The backend accepts submissions, manages optional accounts, stores history, queues jobs, runs applicable analysis stages, and serves the dashboard. Its status is **Partial**: the local API/default pipeline is concrete and tested, while static ML is absent and optional sandbox/ML/LLM paths need separate configuration and verification.

## Source layout

| Path | Responsibility |
| --- | --- |
| `backend/src/app.js`, `server.js` | Express composition, site serving, startup/shutdown |
| `backend/src/routes/` | Health, auth, file/URL submission, history/detail |
| `backend/src/db.js` | SQLite/PostgreSQL logical schema and adapters |
| `backend/src/store/` | User/session/sample/job/result persistence |
| `backend/src/queue/jobQueue.js` | Database-backed in-process worker queue |
| `backend/src/pipeline/stages.js` | Stage order, routing, and optional gates |
| `backend/scripts/content_analyze.py` | Byte-based type detection and non-PE static analysis |
| `backend/src/analyzer/runAnalyzer.js` | Mock/real PE subprocess boundary |
| `backend/src/stages/` | Sandbox, HTTP, and Python stage runners |
| `backend/src/adapters/` | Sandbox-to-ML and LLM evidence translation |
| `backend/signatures/catalog.json` | Safe demonstration indicators |

## Routes and ownership

- `GET /api/health`
- `POST /api/auth/register`, `/login`, `/logout`; `GET /api/auth/me`
- `POST /api/samples`; `POST /api/links`
- `GET /api/samples?limit=&offset=`; `GET /api/samples/:id`

Signed-in users see their own scans; guests see guest-scope scans. Detail requests return `404` for another account's scan. Exact fields and stable error codes are in [the API contract](../../backend/docs/api-contract.md).

## Pipeline

| Order | Stage | Gate/routing | Output |
| --- | --- | --- | --- |
| 1 | `signature` | Always | Local hash or URL/domain match |
| 2 | `file_type` | File; `CONTENT_ANALYZER_PATH` nonempty | Byte-derived category/format and filename warnings |
| 3a | `static_analysis` | PE/DOS, unknown, or missing/failed type report | Mock or real PE report |
| 3b | `content_analysis` | Every detected non-PE format, including unknown | Format-specific bounded findings and indicators |
| — | `static_ml` | Not registered | Planned/not present |
| 4 | `sandbox` | `SANDBOX_URL` | Raw detonation response after validation |
| 5 | `behavioral_ml` | Added with sandbox | Score/evidence plus input summary and adapter notes |
| 6 | `llm` | `LLM_DIR` | Demo threat intelligence, prompt, optional explanation state |

`file_type` and `content_analysis` are enabled by default. Unknown classifications run both `static_analysis` and `content_analysis`; other recognized non-PE categories skip the PE stage. Conditional stages that do not apply create no result row. A stage exception fails that stage but does not erase earlier results or automatically stop later independent stages.

## Persistence and queue

The backend supports local SQLite or configured PostgreSQL with one logical schema for users, sessions, samples, jobs, results, and threat-intelligence indicator results. Uploaded files remain on the receiving host. `worker_id` prevents a backend using a shared database from processing jobs whose local upload belongs to another host.

The queue runs in one backend process with configurable concurrency. Interrupted jobs owned by the worker are re-queued at startup. This is not a distributed worker system.

## Authentication and browser boundary

Passwords use scrypt. The `sentinel_session` cookie carries a random token; only its SHA-256 is stored. Cookies are HttpOnly and SameSite=Lax. Enable `COOKIE_SECURE` behind HTTPS. Failed logins are rate-limited per username/IP in process.

Serving `website/` from this backend is the supported local shape. A separate frontend needs an allowed `CORS_ORIGINS` entry and credentialed requests.

## Configuration

| Group | Variables |
| --- | --- |
| Server/site | `PORT`, `WEBSITE_DIR`, `CORS_ORIGINS` |
| Database | `DATABASE_URL`, `DATABASE_PATH`, `DATABASE_SSL`, `DATABASE_POOL_SIZE`, `WORKER_ID` |
| Upload/jobs | `UPLOAD_DIR`, `MAX_UPLOAD_BYTES`, `JOB_CONCURRENCY`, `WAIT_TIMEOUT_MS` |
| PE analyzer | `PYTHON_PATH`, `ANALYZER_SCRIPT_PATH`, `ANALYZER_TIMEOUT_MS` |
| Content analyzer | `CONTENT_ANALYZER_PATH`, `CONTENT_ANALYZER_TIMEOUT_MS` |
| Signatures | `SIGNATURE_CATALOG_PATH`, `SIGNATURE_HASHLIST_PATH` |
| Sandbox/ML | `SANDBOX_URL`, `SANDBOX_DETONATION_SECONDS`, `SANDBOX_TIMEOUT_MS`, `BEHAVIORAL_ML_URL`, `BEHAVIORAL_ML_TIMEOUT_MS` |
| LLM | `LLM_DIR`, `LLM_BRIDGE_PATH`, `LLM_TIMEOUT_MS`, inherited `GROQ_API_KEY` |
| Accounts | `SESSION_TTL_HOURS`, `COOKIE_SECURE`, `ALLOW_REGISTRATION`, `MAX_FAILED_LOGINS` |

Use `backend/.env.example` for defaults and comments.

## Tests

`npm test` runs top-level `backend/test/*.test.js` covering auth, routes, storage, jobs, catalog behavior, content routing, dashboard data, HTTP stages, sandbox/ML, LLM bridge, and PE analyzer boundaries. `npm run test:dashboard` runs Playwright tests from `backend/test/dashboard/`.

Fresh results are recorded in [Prototype Status](../prototype-status.md#verification-record). Mock sandbox/provider tests verify consumer boundaries, not live service safety or external-provider behavior.

## Failure behavior

- Validation errors use stable JSON error codes; oversized uploads return `413`.
- Invalid catalog configuration stops startup.
- Python/HTTP launch, timeout, nonzero, status, and JSON errors are stored on their stage.
- Empty/parse-failed sandbox output is rejected rather than scored as zero activity.
- `llm` explanation states are `generated`, `skipped`, `error`, or `not_generated`; missing credentials/provider errors do not discard demo intelligence and prompt output.
- A scan may reach job status `completed` with one or more failed stages.

## Security and operational limits

- Uploaded files and reports need retention/deletion policy and access controls.
- Guest scanning is enabled by default.
- Local upload storage plus one-process queue constrain horizontal scaling.
- The default PE analyzer is a mock; findings are not a production verdict.
- Optional services can receive sensitive telemetry/indicators and need independent authentication, TLS, and policy review.
- No production audit log, metrics/tracing stack, backup, artifact storage, or secret manager is supplied.

## Next work

1. Define and implement the missing static-ML stage and contract.
2. Consolidate stage schemas and expose capabilities to the frontend.
3. Add retention/deletion endpoints and policy.
4. Add production auth/TLS/observability/secrets guidance.
5. Verify dynamic/ML/LLM integrations with inert end-to-end fixtures and versioned outputs.

## Related documentation

- [Backend README](../../backend/README.md)
- [API contract](../../backend/docs/api-contract.md)
- [Architecture](../architecture.md)
- [Setup and Operations](../setup-and-operations.md)
- [Prototype Status](../prototype-status.md)
