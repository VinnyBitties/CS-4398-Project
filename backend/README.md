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

- **Sandbox telemetry schema.** The team confirmed (2026-09-29) this project
  uses a custom virtual sandbox, not Cuckoo Sandbox. The ML team's
  `report_parser.py` (`ML-Axel` branch) is built specifically against Cuckoo's
  JSON shape (`signatures`, `network`, `behavior.summary.*`). Since the custom
  sandbox won't emit that exact format, someone needs to either make the
  sandbox Cuckoo-compatible or update `report_parser.py`'s field mapping —
  needs a conversation between Dynamic Analysis, ML (Axel, Diego), and
  backend before the behavioral-ML stage can be wired in for
  real. `src/stages/httpStage.js` (below) is ready on the backend side either
  way, since the HTTP-call pattern doesn't depend on the payload shape.
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
  first.
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

  A stage that fails is recorded as failed and the rest still run. Static
  ML, sandbox, behavioral ML and LLM stages are **not wired in**; adding one
  is a new object in `stages.js` and nothing else.
- **Signature catalog** — `src/signatures/catalog.js` loads
  `signatures/catalog.json` (curated entries: `sha256`, `domain`, `url`) plus
  an optional bulk hash list (`SIGNATURE_HASHLIST_PATH`, one SHA-256 per
  line). The committed catalog contains only harmless antivirus **test**
  artifacts (EICAR, WICAR, Safe Browsing test pages); no real threat feed has
  been chosen yet. A malformed entry stops the server at startup instead of
  silently never matching. YARA rules are not part of this.
- `src/stages/httpStage.js` — the integration pattern for a stage exposed as
  a long-running HTTP service (matches the ML team's `predict.py --serve`).
  Implemented and tested against a mock HTTP server, but not used by any
  stage yet — blocked on the sandbox telemetry schema question above.

### Trying it

```bash
curl -F "file=@package.json" "http://localhost:3000/api/samples?wait=true"
curl -H "Content-Type: application/json" -d '{"url":"http://malware.wicar.org/"}' "http://localhost:3000/api/links?wait=true"
curl "http://localhost:3000/api/samples"
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

29 tests across five files: the API end to end (`samples.test.js`), the job
queue (`jobQueue.test.js`), the signature catalog (`catalog.test.js`), the
HTTP stage runner (`httpStage.test.js`) and the real analyzer
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
3. Settle the sandbox telemetry schema, then add the `sandbox` and
   `behavioral_ml` stages.
4. Choose a real signature feed and point `SIGNATURE_HASHLIST_PATH` at it.
5. Decide on authentication and CORS before the API is reachable from
   anywhere but localhost.
