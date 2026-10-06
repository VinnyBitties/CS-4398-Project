# Sentinel backend API contract (draft for the dashboard)

Status: **draft v0.2, not yet agreed with frontend.** Everything below is
implemented and tested on `backend-Dhrubo`; what is still open is listed under
"Open questions" at the end. Until those are settled, treat field names as
stable and route names as provisional.

Base URL in development: `http://localhost:3000/api`

## How a scan works

1. The dashboard submits a file (`POST /samples`) or a link (`POST /links`).
2. The backend stores it, queues a scan job and answers **immediately** with
   `202 Accepted` and a `sample_id`. Nothing has been analyzed yet.
3. The dashboard polls `GET /samples/{sample_id}` until `status` is
   `completed` or `failed`. A 1 to 2 second interval is plenty.
4. Each pipeline stage adds one entry to `results[]` as it starts, and fills
   it in when it finishes, so the dashboard can show progress stage by stage.

For scripts and demos, add `?wait=true` to either submit route: the request is
held until the scan finishes and returns `201 Created` with the final result.
If the scan outlasts 30 seconds it falls back to `202` and polling.

## The sample object

Every route that returns a submission returns this one shape.

| Field | Type | Notes |
|---|---|---|
| `sample_id` | integer | Use this in `GET /samples/{sample_id}`. |
| `submission_type` | `"file"` \| `"link"` | |
| `status` | `"queued"` \| `"running"` \| `"completed"` \| `"failed"` | The scan job as a whole. `completed` means the pipeline ran to the end, **not** that every stage succeeded: check `results[].status`. `failed` means the pipeline itself crashed. |
| `sha256` | string, 64 hex | Of the file's bytes; for a link, of the normalized URL. |
| `original_filename` | string \| null | The name the user uploaded. Null for links. Show this, not the analyzer report's `filename`, which is a random storage name. |
| `submitted_url` | string \| null | Normalized (lowercase host, no `#fragment`). Null for files. |
| `file_size` | integer \| null | Bytes. Null for links. |
| `created_at` | string | ISO 8601 UTC, e.g. `2026-10-06T23:02:13.554Z`. |
| `signature_match` | boolean \| null | **Null until the signature stage finishes.** `true` = known-bad hash, domain or URL. |
| `job` | object \| null | `job_id`, `status`, `attempts`, `error`, `queued_at`, `started_at`, `finished_at`. |
| `results` | array | One entry per stage that has started, in pipeline order. |

Each `results[]` entry:

| Field | Type | Notes |
|---|---|---|
| `stage` | string | See "Stages" below. |
| `status` | `"running"` \| `"complete"` \| `"failed"` | |
| `signature_match` | boolean \| null | Only set on the `signature` stage. |
| `report` | object \| null | The stage's full output. Shape depends on the stage. |
| `error` | object \| null | When `failed`: `{ code, message, details }`. |
| `created_at` | string | When the stage started. |

### Stages

| `stage` | Runs for | Status | `report` shape |
|---|---|---|---|
| `signature` | files, links | **Live** | `{ matched, checked: "sha256"\|"url", match: { type, name, severity, source } \| null }` |
| `static_analysis` | files | **Live against a mock analyzer** | The static analyzer's report, `schema_version` `1.0.0` (`REPORT_CONTRACT.md`). PE fields are canned values until the real `analyze.py` is plugged in. |
| `static_ml` | files | Planned | To be defined with ML. |
| `sandbox` | files, links | Planned | Blocked on the sandbox telemetry schema. |
| `behavioral_ml` | files, links | Planned | Depends on `sandbox`. |
| `llm` | files, links | Planned | To be defined with LLM/Threat Intelligence. |

New stages appear as extra `results[]` entries. Nothing else about the sample
object changes, so a dashboard that renders `results[]` generically picks them
up without a contract change.

## Routes

### `GET /health`

`200` `{ "status": "ok", "service": "sentinel-backend" }`

### `POST /samples`

Submit a file. `multipart/form-data`, one part named **`file`**. Limit: 25 MiB.

```bash
curl -F "file=@suspicious.exe" http://localhost:3000/api/samples
```

`202 Accepted`, `Location: /api/samples/7`:

```json
{
  "sample_id": 7,
  "submission_type": "file",
  "status": "queued",
  "sha256": "2cdb420b7d09618b3cfd735a82bfbdfea451d822e7c47fcf0d39faf059c46b4d",
  "original_filename": "suspicious.exe",
  "submitted_url": null,
  "file_size": 539,
  "created_at": "2026-10-06T23:02:13.201Z",
  "signature_match": null,
  "job": { "job_id": 7, "status": "queued", "attempts": 0, "error": null,
           "queued_at": "2026-10-06T23:02:13.201Z", "started_at": null, "finished_at": null },
  "results": []
}
```

### `POST /links`

Submit a URL. `application/json`. Only absolute `http://` and `https://` URLs,
up to 2048 characters.

```bash
curl -H "Content-Type: application/json" \
     -d '{"url": "https://example.com/download"}' \
     http://localhost:3000/api/links
```

Responds exactly like `POST /samples`, with `submission_type: "link"`.

The backend **does not visit the URL**. Today a link only gets the signature
stage (is the URL or its domain in the catalog?). Opening the page happens in
the sandbox stage once that exists.

### `GET /samples/{sample_id}`

`200` with the sample object. A finished file scan:

```json
{
  "sample_id": 7,
  "submission_type": "file",
  "status": "completed",
  "sha256": "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f",
  "original_filename": "eicar.com",
  "submitted_url": null,
  "file_size": 68,
  "created_at": "2026-10-06T23:02:13.201Z",
  "signature_match": true,
  "job": { "job_id": 7, "status": "completed", "attempts": 1, "error": null,
           "queued_at": "2026-10-06T23:02:13.201Z",
           "started_at": "2026-10-06T23:02:13.204Z",
           "finished_at": "2026-10-06T23:02:13.259Z" },
  "results": [
    { "stage": "signature", "status": "complete", "signature_match": true,
      "report": { "matched": true, "checked": "sha256",
                  "match": { "type": "sha256", "name": "EICAR-Test-File",
                             "severity": "test",
                             "source": "EICAR standard antivirus test file (68 bytes)" } },
      "error": null, "created_at": "2026-10-06T23:02:13.205Z" },
    { "stage": "static_analysis", "status": "complete", "signature_match": null,
      "report": { "schema_version": "1.0.0", "...": "see REPORT_CONTRACT.md" },
      "error": null, "created_at": "2026-10-06T23:02:13.207Z" }
  ]
}
```

### `GET /samples?limit=20&offset=0`

Scan history, newest first. `limit` is 1 to 100 (default 20).

```json
{ "total": 42, "limit": 20, "offset": 0, "samples": [ { "...sample object..." } ] }
```

## Errors

Every error is JSON: `{ "error": "<code>", "message": "<human readable>" }`.
Branch on `error`, display `message`.

| HTTP | `error` | When |
|---|---|---|
| 400 | `missing_file` | `POST /samples` with no `file` part. |
| 400 | `missing_url` | `POST /links` with no `url` string. |
| 400 | `invalid_url` | Not an absolute http(s) URL. |
| 400 | `url_too_long` | Over 2048 characters. |
| 400 | `invalid_json` | Body is not valid JSON. |
| 404 | `not_found` | Unknown route or `sample_id`. |
| 413 | `upload_rejected` | File over 25 MiB. |
| 500 | `internal_error` | Unexpected; details are in the server log only. |

A stage failing is **not** an HTTP error: the scan still returns 200/201, and
the failure is in that stage's `results[].error`. Stage error codes so far,
all from `static_analysis`: `NONZERO_EXIT` (most often: not a valid PE file),
`TIMEOUT`, `BAD_JSON`, `UNSUPPORTED_SCHEMA`, `LAUNCH_FAILED`,
`INPUT_NOT_FOUND`.

## Open questions

1. **Route names.** `docs/component-plan.example.md` on `main` sketches
   `POST /scans`; this implementation uses `/api/samples` and `/api/links`.
   Renaming is a one-line change on the backend. Which does the dashboard
   want?
2. **Overall verdict.** There is no single "malicious / suspicious / clean"
   field or score yet, only `signature_match` plus per-stage reports. Who
   computes the verdict the dashboard shows, and from which stages?
3. **Authentication.** None. Every route is open to anyone who can reach the
   port. Fine on localhost; needs a decision before any shared deployment.
4. **CORS.** Not enabled. If the dashboard is served from a different origin
   than the API in development, the backend needs to allow that origin.
5. **Progress updates.** Polling only. Is that enough, or does the dashboard
   want server-sent events?
6. **Signature match and later stages.** A signature match does not stop the
   pipeline; later stages still run. Should a known-bad hash short-circuit?
