# Backend API and Orchestration

## Purpose and status

The backend accepts submissions, manages optional accounts, stores history, queues scan jobs, runs analysis stages, and serves the dashboard. Its status is **Partial**: the core API and default stages are implemented, while static ML is absent and later stages depend on unavailable external components.

## Source layout

| Path | Responsibility |
| --- | --- |
| `backend/src/app.js` | Express middleware, routes, static site, JSON error boundary |
| `backend/src/server.js` | Startup, database readiness, queue lifecycle, listener |
| `backend/src/config.js` | Environment parsing and defaults |
| `backend/src/db.js` | Shared SQLite/PostgreSQL adapter and schema |
| `backend/src/routes/` | Health, account/session, sample, URL, history endpoints |
| `backend/src/store/` | User/session and sample/job/result persistence |
| `backend/src/queue/jobQueue.js` | In-process database-backed queue |
| `backend/src/pipeline/` | Stage definitions and independent stage execution |
| `backend/src/stages/` | Python, JSON HTTP, and multipart sandbox clients |
| `backend/src/adapters/` | Sandbox-to-ML and pipeline-to-LLM conversion |
| `backend/src/signatures/` | Catalog loading, validation, normalization, matching |

## REST API

| Method and path | Purpose | Authentication |
| --- | --- | --- |
| `GET /api/health` | Liveness response | None |
| `POST /api/auth/register` | Create user and session | Guest; optional by configuration |
| `POST /api/auth/login` | Validate credentials and create session | Guest |
| `POST /api/auth/logout` | Delete current session and cookie | Session or no-op |
| `GET /api/auth/me` | Return current user | Returns 401 for guest |
| `POST /api/samples` | Store multipart field `file`, create scan job | Account or guest |
| `POST /api/links` | Validate/store HTTP(S) URL, create scan job | Account or guest |
| `GET /api/samples` | Paged history for current user or guest scope | Account or guest |
| `GET /api/samples/:id` | One sample, job, and stage results | Owner scope |

Submission normally returns `202`. Query `?wait=true` waits up to `WAIT_TIMEOUT_MS` and returns `201` only if processing finishes. See the [API contract](../../backend/docs/api-contract.md) for schemas and error codes.

## Pipeline

The queue calls the stages in `backend/src/pipeline/stages.js`. Each applicable stage is stored as running, then completed or failed. One stage failure does not stop later independent stages.

| Stage | Enablement | Input | Output/current state |
| --- | --- | --- | --- |
| `signature` | Always | File SHA-256 or submitted URL | Match metadata from local catalog/bulk hash list |
| `static_analysis` | Always for files | Stored path | Mock report by default; real report when configured |
| `static_ml` | Not present | Intended static report | No stage registered |
| `sandbox` | `SANDBOX_URL` | Stored file | External detonation response; service absent here |
| `behavioral_ml` | With sandbox | Normalized telemetry | HTTP score/evidence response |
| `llm` | `LLM_DIR` | Bounded prior reports/indicators | External bridge result; external component absent here |

## Queue and persistence

Jobs move `queued → running → completed | failed`. `JOB_CONCURRENCY` controls local parallelism. Jobs left running by a process stop are re-queued on startup for the same `WORKER_ID`. The queue is durable through the database but executes inside one Node process; it is not a distributed worker system.

SQLite is the no-service default. Setting `DATABASE_URL` selects PostgreSQL with the same logical tables. Because uploaded files live on the receiving machine, worker ownership prevents another backend using the shared database from processing a path it cannot access.

Stored records include users, hashed sessions, samples, jobs, stage results, and threat-intelligence indicator results. No retention job or deletion API exists.

## Authentication and controls

- Passwords are hashed with scrypt and per-password salts.
- Session tokens are random; only their SHA-256 is stored.
- Cookie is HttpOnly, `SameSite=Lax`, and conditionally Secure.
- Login failure behavior avoids distinguishing unknown user from wrong password.
- Per-process username/IP failure tracking applies a temporary lockout.
- Registration can be disabled.
- CORS permits credentials only for configured origins.

This is appropriate for a local prototype, not a complete production identity system. There is no password reset, email verification, role model, account deletion, CSRF token, or external identity provider.

## Configuration

Configuration is centralized in `backend/src/config.js` and documented in [Setup and Operations](../setup-and-operations.md). Important defaults include port 3000, 25 MiB uploads, job concurrency 2, a 30-second synchronous wait, 15-second analyzer timeout, 15-second requested detonation, 120-second sandbox request timeout, and a seven-day session lifetime.

## Test inventory and observed result

Eight Node test files cover:

- API submission/history and stable failure behavior.
- Registration, login, sessions, ownership, CORS, and static serving.
- Signature catalog validation and matching.
- Queue transitions, concurrency, crash recovery, ownership, and wait timeout.
- Generic HTTP-stage errors.
- Sandbox client, telemetry adapter, behavioral-ML integration, and serialized detonations.
- LLM input filtering/bounding, bridge behavior, ordering, and independent failure.
- Real static-analyzer boundary, conditionally skipped without its dependency.

On 2026-11-03, `npm test` did not start because the available npm shim reported unsupported WSL 1. No backend test assertion result was observed in that environment. Historical counts in `backend/README.md` are not substituted for this result.

## Operational and security notes

- The backend stores arbitrary uploads before PE validation; protect and isolate the upload directory.
- `COOKIE_SECURE=false` is for local HTTP only.
- The default catalog contains safe test indicators, not a production feed.
- URL submissions are normalized and checked but never fetched by the backend signature stage.
- Optional external services receive file content, telemetry, or indicators; review their data handling first.
- The static analyzer output is schema-version checked and size bounded by the subprocess runner.
- Tests must use a disposable PostgreSQL database because the PostgreSQL suite clears its tables.

## Known limitations

- Default mock analyzer means the easiest startup does not extract real PE features.
- No static-ML stage.
- No real sandbox or threat-intelligence source tree in this branch.
- Single-process queue and local upload storage limit scaling.
- No upload/record deletion or retention policy.
- Guest scans are allowed.
- No deployment proxy, TLS, monitoring, structured audit, backup, or disaster-recovery configuration.

## Next work

1. Run the suite under supported Node/WSL and update observed evidence.
2. Decide when the real analyzer becomes the default.
3. Add static ML behind a versioned contract and artifact configuration.
4. Validate sandbox safety and real telemetry before enabling detonation.
5. Connect dashboard history/detail views.
6. Add retention/deletion and production deployment controls.

## Related documentation

- [Backend README](../../backend/README.md)
- [API contract](../../backend/docs/api-contract.md)
- [Database notes](../../backend/docs/azure-database.md)
- [Architecture](../architecture.md)
- [Prototype Status](../prototype-status.md)
