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
- [ ] [backend-02] Create queued/running/completed/failed job states and a worker
      interface. Currently only synchronous request-handling exists (signature
      stage only, which is fast); this becomes required once the sandbox stage
      (much slower) is wired in.
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
- [x] [backend-07] Validate upload type and return useful errors for unsupported
      files. `POST /api/samples` returns structured error codes
      (`INPUT_NOT_FOUND`, `NONZERO_EXIT`, `TIMEOUT`, etc.) rather than a bare 500.

## Dependencies and acceptance details

- **Static analysis (Kyle, `dev-branch`):** `runAnalyzer.js` implements the
  documented Node.js `child_process.spawn` integration and is tested against
  `scripts/mock_analyze.py` (a contract-compatible stand-in). Swap in the real
  `malware_detection/analyze.py` once that branch merges.
- **Signature lookup (FR02):** starter in-memory hash list in
  `src/signatures/knownHashes.js` -- replace with a real catalog/YARA source
  per the Week 3 plan.
- **Sandbox telemetry schema -- open coordination item:** the team confirmed
  (2026-09-29) this project uses a custom virtual sandbox, not Cuckoo Sandbox.
  The ML team's existing `report_parser.py` (`ML-Axel` branch) is built
  specifically against Cuckoo's JSON report shape (`signatures`, `network`,
  `behavior.summary.num_processes_created`, etc.). Since the sandbox won't
  produce Cuckoo's exact format, either the sandbox needs to emit
  Cuckoo-compatible JSON, or `report_parser.py`'s field mapping needs to be
  updated to match whatever schema the sandbox team (Vincent, Jarrel) settles
  on. Backend can't finalize the behavioral-ML wiring until this is resolved
  -- needs a three-way conversation between Dynamic Analysis, ML, and Backend.
- **Dashboard endpoints:** depend on the frontend/API contract (Sebastian's
  `website` branch). Not yet coordinated on exact response shape beyond what's
  in `GET /api/samples/:id`.

## Future additions to consider

Pagination for scan history; a real job queue (BullMQ + Redis, or similar)
once stage latency requires it; a route naming pass if `/scans` is the team's
preferred convention over `/samples`.

## Completion

Status: active. Not ready for `Status: final` -- static ML, behavioral ML, and
LLM stages are unimplemented, and the job queue doesn't exist yet.
