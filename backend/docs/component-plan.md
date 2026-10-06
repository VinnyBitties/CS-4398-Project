# Backend component plan

Status: active

## Purpose

Accept scan submissions, orchestrate analysis across pipeline stages, and provide
stored results to the dashboard. Scope per `Sentinel_Backend_Development_Documentation_Form.docx`
and `docs/project-overview.md`'s Committed scope table: REST API, database, job
queue, pipeline orchestration, and historical scan records (FR01, FR02, FR08).

## Committed tasks

- [x] [backend-01] Implement `POST /api/samples` accepting Windows `.exe` uploads
      and returning a sample ID. (Named `/api/samples`, not `/scans` -- confirm
      with the team whether the dashboard/frontend contract expects a specific
      route name before this is load-bearing.)
- [x] [backend-02] Create queued/running/completed/failed job states and a worker
      interface. `src/queue/jobQueue.js` runs scans in the background off a
      SQLite `jobs` table; `src/pipeline/stages.js` is the worker interface a
      new stage plugs into. Uploads return `202` and are polled.
- [x] [backend-03] Persist sample ID, filename, hash, and per-stage results
      (`samples` + `results` tables, SQLite for dev). Telemetry reference and
      full report storage exist as a generic `report_json` column per stage.
- [ ] [backend-04] Wire the static ML stage (FR03) into the pipeline once it
      exists -- not started by any team member yet as of this writing.
- [ ] [backend-05] Wire the behavioral ML stage (FR05) into the pipeline.
      `src/stages/httpStage.js` implements the HTTP-call pattern the ML team's
      `predict.py --serve` expects, tested against a mock server, but not
      wired into a route -- blocked on the sandbox telemetry schema (see
      Dependencies below).
- [ ] [backend-06] Wire the LLM threat-analysis stage (FR06) into the pipeline.
      Not started; no LLM/Threat Intel branch exists yet as of this writing.
- [x] [backend-08] Accept link/URL submissions (professor feedback, suggestion
      4). `POST /api/links` validates, stores and signature-checks a URL
      without fetching it. Rendering the page is the sandbox stage's job.
- [x] [backend-09] Scan history listing (FR08): `GET /api/samples` with paging.
- [x] [backend-07] Validate upload type and return useful errors for unsupported
      files. `POST /api/samples` returns structured error codes
      (`missing_file`, `upload_rejected`, ...) rather than a bare 500; analyzer
      failures (`NONZERO_EXIT`, `TIMEOUT`, etc.) are recorded on the
      `static_analysis` stage result.

## Dependencies and acceptance details

- **Static analysis (Kyle, `malware_detection/`):** merged to `main` on
  2026-10-06. `runAnalyzer.js` runs it as a subprocess and accepts report
  contract versions 1.0.0 to 1.2.0. Verified end to end against the real
  `analyze.py` with a synthetic PE (`test/realAnalyzer.test.js`); the default
  configuration still points at `scripts/mock_analyze.py` so the backend
  runs without `pefile`.
- **Signature lookup (FR02):** `src/signatures/catalog.js` loads
  `signatures/catalog.json` plus an optional bulk hash list. The committed
  catalog holds only antivirus test artifacts; choosing a real feed (and any
  YARA source, per the Week 3 plan) is still open.
- **Sandbox telemetry schema -- open coordination item:** the team confirmed
  (2026-09-29) this project uses a custom virtual sandbox, not Cuckoo Sandbox.
  The ML team's existing `report_parser.py` (`ML-Axel` branch) is built
  specifically against Cuckoo's JSON report shape (`signatures`, `network`,
  `behavior.summary.num_processes_created`, etc.). Since the sandbox won't
  produce Cuckoo's exact format, either the sandbox needs to emit
  Cuckoo-compatible JSON, or `report_parser.py`'s field mapping needs to be
  updated to match whatever schema the sandbox team settles on. Backend can't finalize the behavioral-ML wiring until this is resolved
  -- needs a three-way conversation between Dynamic Analysis, ML, and Backend.
- **Dashboard endpoints:** drafted in `docs/api-contract.md`, not yet agreed
  with the frontend (Sebastian's `website` branch). Its "Open questions"
  section lists what needs a decision, starting with route names.

## Future additions to consider

A broker-backed job queue (BullMQ + Redis, or similar) if the backend ever
runs as more than one process; authentication and CORS; a route naming pass if `/scans` is the team's
preferred convention over `/samples`.

## Completion

Status: active. Not ready for `Status: final` -- static ML, behavioral ML, and
LLM stages are unimplemented.
