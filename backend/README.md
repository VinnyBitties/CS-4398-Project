# backend

Sentinel's core REST API: accepts sample uploads, runs them through the analysis
pipeline stages, stores scan history, and serves results to the dashboard. Scope
per `Sentinel_Backend_Development_Documentation_Form.docx`: REST API, database,
job queue/orchestration across signature → static ML → sandbox → behavioral ML →
LLM stages, and operational configuration.

## Why Node.js

`malware_detection`'s `DEMO_AND_HANDOFF.md` already specifies a "Future Node.js
integration (design only)" for calling into the Python static analyzer via
`child_process.spawn`. This backend implements that design in
`src/analyzer/runAnalyzer.js` rather than picking a different stack — confirm
with the team if that design should change before diverging from it.

## Setup

```bash
cd backend
npm install
cp .env.example .env
npm run dev     # starts on http://localhost:3000 by default
```

## Current status (what's implemented vs. stubbed)

- `GET /api/health` — implemented.
- `POST /api/samples` (multipart, field `file`) — implemented against a
  **mock** analyzer (`scripts/mock_analyze.py`), which mimics
  `analyze.py`'s I/O contract (`REPORT_CONTRACT.md`, schema `1.0.0`) closely
  enough to develop and test the API without depending on the
  `malware-detection` branch. Runs the file through the analyzer, computes
  `sha256`, checks it against an in-memory signature list
  (`src/signatures/knownHashes.js` — replace with a real YARA/hash catalog
  per the Week 3 plan), and stores both in SQLite.
- `GET /api/samples/:id` — implemented; returns a sample plus all its stage
  results.
- `POST /api/links` — **stubbed**, returns 501. Depends on Dynamic Analysis
  extending the sandbox to render URLs (Week 8) before this can do anything
  real.
- Static ML, sandbox, behavioral ML, and LLM stages — **not started**. The
  `results` table already has a `stage` column designed to hold each of
  these as they come online, so wiring in a new stage means adding another
  `results` row per sample, not a schema change.
- Job queue — **not started**. Right now everything runs synchronously
  inside the request handler, which is fine only while analysis is fast
  (signature stage). Once the sandbox stage is wired in (which takes much
  longer per Week 7/8), this needs to become async — a real queue (e.g.
  BullMQ + Redis) or at minimum a background worker, so uploads don't hang
  an HTTP request for minutes.

## Switching from the mock analyzer to the real one

Once `malware-detection` is merged (or while developing against it locally),
set in `.env`:

```
ANALYZER_SCRIPT_PATH=/absolute/path/to/malware_detection/analyze.py
PYTHON_PATH=/absolute/path/to/malware_detection/.venv/Scripts/python.exe
```

`runAnalyzer.js` doesn't care which script it's pointed at as long as the
script honors the same contract (JSON to stdout + exit 0 on success; JSON
error to stderr + exit 1 on failure; `schema_version` field).

## Tests

```bash
npm test
```

Runs against the mock analyzer and an in-memory SQLite database — no real
PE files or network access needed.

## Next steps (see the Week-by-Week Plan / Kickoff Checklist)

1. Fill in the Backend Development Documentation Form as you go: API
   Endpoint Record, Database Record, Decision Log (e.g. "why SQLite for
   dev"), Testing and Verification.
2. Swap the mock analyzer for the real one once `malware-detection` merges,
   and confirm the Node.js integration design still holds for real PE
   reports (larger `strings.sample` arrays, real `imports`, etc.).
3. Replace the in-memory known-hash Set with a real signature source.
4. Decide on the job-queue approach before the sandbox stage lands — that's
   the point synchronous request handling breaks.
