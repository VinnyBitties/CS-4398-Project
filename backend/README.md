# backend

Sentinel's core REST API: accepts sample uploads, runs them through the analysis
pipeline stages, stores scan history, and serves results to the dashboard. Scope
per `Sentinel_Backend_Development_Documentation_Form.docx`: REST API, database,
job queue/orchestration across signature → static ML → sandbox → behavioral ML →
LLM stages, and operational configuration.

## Why Node.js

`malware_detection`'s handoff document originally specified a "Future
Node.js integration (design only)" for calling into the Python static analyzer
via `child_process.spawn`. That section was dropped in Kyle's later
`dev-branch` rewrite, but the team confirmed (2026-09-29) Node.js is still the
plan. This backend implements that design in `src/analyzer/runAnalyzer.js`.

## Open coordination items

- **Sandbox telemetry schema.** The sandbox (`dynamic_telemetry/api.py`,
  `feature/dynamic-sandbox-engine`) and the ML parser (`ML/report_parser.py`,
  `ML-Axel`, updated 2026-10-17) still expect different field names
  (`process_count` vs `processes_created`, events under `telemetry` vs at the
  top level, `query` vs `query_name`, and so on). The backend no longer waits
  on this: `src/adapters/sandboxToMl.js` translates between them, and passes a
  report through untouched once both sides agree on one shape. Two things only
  the sandbox can fix: it does not capture injected remote threads yet (sent
  to ML as 0, and noted in the result), and `/detonate` does not appear to
  copy the sample into the VM or the Sysmon log back out, so real runs may
  return a `parse_error`, which the backend records as a failed `sandbox`
  stage rather than scoring empty telemetry.
- **Route naming.** `docs/component-plan.example.md` on `main` sketches
  `POST /scans`; this implementation uses `POST /api/samples`. Confirm which
  convention the frontend/dashboard expects before either becomes load-bearing.

## Setup

```bash
cd backend
npm install
cp .env.example .env
npm run dev     # starts on http://localhost:3000 by default
```

## Current status (what's implemented vs. stubbed)

The dashboard-facing contract for everything below is in
[`docs/api-contract.md`](docs/api-contract.md).

- `GET /api/health` — implemented.
- `POST /api/samples` (multipart, field `file`) — implemented. Hashes the
  upload, stores it, queues a scan job and returns `202` with a `sample_id`
  straight away. Add `?wait=true` to hold the request until the scan is done
  (`201`), which is the convenient form for curl and demos.
- `POST /api/links` (JSON `{"url": ...}`) — implemented for the signature
  stage. The backend validates and stores the URL and checks it against the
  catalog; it never fetches the URL itself. Deeper link analysis still
  depends on Dynamic Analysis extending the sandbox to render URLs (Week 8).
- `GET /api/samples/:id` — implemented; a sample, its job status and every
  stage result so far.
- `GET /api/samples?limit=&offset=` — implemented; scan history, newest
  first. Scoped to the signed-in user (guests see guest scans).
- **Login** — `POST /api/auth/register`, `POST /api/auth/login`,
  `POST /api/auth/logout`, `GET /api/auth/me`. Passwords are hashed with
  scrypt; the session is an HttpOnly cookie whose token is stored only as a
  SHA-256 (`users` and `sessions` tables). Signing in is optional. Details
  in `docs/api-contract.md`, "Accounts and login".
- **Dashboard pages** — served from `../website` at `http://localhost:3000/`,
  so the pages and the API share an origin and the login cookie works.
- **Job queue** — implemented in `src/queue/jobQueue.js`. Scans run in the
  background, `JOB_CONCURRENCY` at a time (default 2), through
  `queued → running → completed | failed`. The queue is the `jobs` table in
  SQLite rather than BullMQ + Redis: no extra service for teammates to
  install, and jobs survive a restart (anything interrupted is re-queued at
  startup). It runs inside the one Node process, so it does not scale across
  machines; that is a deliberate trade for a capstone demo.
- **Pipeline** — `src/pipeline/stages.js` is the ordered list of stages.
  Two are wired in:
  - `signature` — looks the hash (or URL/domain) up in the catalog.
  - `static_analysis` — runs the static analyzer as a subprocess. Still the
    **mock** (`scripts/mock_analyze.py`) by default, which mimics
    `analyze.py`'s I/O contract (`malware_detection/REPORT_CONTRACT.md`,
    schema `1.2.0`). The real analyzer works too and is one `.env` line
    away; see below.

  - `sandbox` — uploads the file to the sandbox service's `/detonate` and
    stores its response. Files only; one detonation at a time, because the
    sandbox has a single VM. **Off unless `SANDBOX_URL` is set.**
  - `behavioral_ml` — converts the sandbox report with
    `src/adapters/sandboxToMl.js` and POSTs it to the ML service
    (`predict.py --serve`, `BEHAVIORAL_ML_URL`). Runs with `sandbox`.

  A stage that fails is recorded as failed and the rest still run. Static
  ML and LLM stages are **not wired in**; adding one is a new object in
  `stages.js` and nothing else.
- **Signature catalog** — `src/signatures/catalog.js` loads
  `signatures/catalog.json` (curated entries: `sha256`, `domain`, `url`) plus
  an optional bulk hash list (`SIGNATURE_HASHLIST_PATH`, one SHA-256 per
  line). The committed catalog contains only harmless antivirus **test**
  artifacts (EICAR, WICAR, Safe Browsing test pages); no real threat feed has
  been chosen yet. A malformed entry stops the server at startup instead of
  silently never matching. YARA rules are not part of this.
- `src/stages/httpStage.js` — the integration pattern for a stage exposed as
  a long-running HTTP service (matches the ML team's `predict.py --serve`).
  Used by the `behavioral_ml` stage. `src/stages/sandboxClient.js` is the
  multipart-upload equivalent for the sandbox.

### Trying it

```bash
curl -F "file=@package.json" "http://localhost:3000/api/samples?wait=true"
curl -H "Content-Type: application/json" -d '{"url":"http://malware.wicar.org/"}' "http://localhost:3000/api/links?wait=true"
curl "http://localhost:3000/api/samples"

# Log in with a cookie jar, then scan as that user
curl -c jar.txt -H "Content-Type: application/json" -d '{"username":"demo","password":"demo-pass-1"}' http://localhost:3000/api/auth/register
curl -b jar.txt http://localhost:3000/api/auth/me
```

## Switching from the mock analyzer to the real one

The real analyzer is in this repo at `malware_detection/analyze.py` (merged to
`main` on 2026-10-06). The backend still defaults to the mock so that
`npm run dev` works with nothing but Node and Python installed. To use the
real one, install its one dependency and point `.env` at it:

```bash
pip install -r ../malware_detection/requirements.txt
```

```
ANALYZER_SCRIPT_PATH=../malware_detection/analyze.py
```

If `pefile` lives in a virtual environment, set `PYTHON_PATH` to that
environment's interpreter.

The backend accepts analyzer contract versions `1.0.0` to `1.2.0`
(`supportedSchemaVersions` in `src/config.js`); the real analyzer emits
`1.2.0`. A file that is not a valid PE makes the analyzer exit 1, which shows
up as a failed `static_analysis` stage carrying the analyzer's own reason
(for example `PEFormatError`), not as a failed scan.

## Tests

```bash
npm test
```

43 tests across six files: the API end to end (`samples.test.js`), the job
queue (`jobQueue.test.js`), the signature catalog (`catalog.test.js`), the
HTTP stage runner (`httpStage.test.js`), the sandbox and behavioral ML stages
against mock services (`sandboxStages.test.js`) and the real analyzer
(`realAnalyzer.test.js`). All but the last run against the mock analyzer and
an in-memory SQLite database, with no network access. The two real-analyzer
tests are skipped unless `pefile` is installed for `python3`; they build an
inert PE with the analyzer's own test helper, so no binary is committed.

## Next steps

1. Try the real analyzer against real Windows executables (so far it has
   only been run on the analyzer's small synthetic test PE), then decide
   whether it should become the default.
2. Agree the API contract with the dashboard (`docs/api-contract.md`, "Open
   questions"), starting with route names.
3. Run the `sandbox` and `behavioral_ml` stages against the real sandbox VM
   once `/detonate` returns real telemetry, and agree one telemetry shape with
   Dynamic Analysis and ML so the adapter can be removed.
4. Choose a real signature feed and point `SIGNATURE_HASHLIST_PATH` at it.
5. Decide whether scanning should require an account before the API is reachable from
   anywhere but localhost.
