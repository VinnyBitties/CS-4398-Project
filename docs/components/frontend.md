# Frontend Dashboard

## Purpose and status

The frontend provides account/guest entry, multi-format file or URL submission, scan progress, paged scan history, behavioral summaries, and detailed PE evidence. Its status is **Partial**: the primary workflows are connected and have committed Node/Playwright coverage, but not every backend stage has a complete detail view and no formal accessibility/usability evaluation exists. The current Playwright command was blocked by Node/npm platform detection before any browser test ran.

## Source layout

| Path | Responsibility |
| --- | --- |
| `website/index.html` | Login, registration, and guest entry |
| `website/api.js` | Shared authenticated Fetch wrapper, submissions, history/detail calls |
| `website/dashboard/home.html` | File/URL input, supported extension list, stage progress, summarized content findings, Reports link |
| `website/dashboard/reports.html` | Paged history and selected-scan panels |
| `website/dashboard/reports.js` | History, selection, polling, retry, safe DOM updates |
| `website/dashboard/reports-data.js` | Browser/Node shared behavioral and stage-state normalization |
| `website/dashboard/static-evidence.js` | Detailed PE evidence rendering |
| `website/retro*.css`, `retro-loading.js` | Shared retro theme and reduced-motion-aware reveal |
| `website/dashboard/README.md` | Report UI operation and browser-test instructions |

The backend serves `website/` by default, keeping pages, API, and HttpOnly session cookie on one origin.

## User workflows

### Account or guest entry

The root page checks `GET /api/auth/me`. Login and registration call the corresponding backend endpoints; successful registration also creates a session. “No Sign In” enters the guest scope. The browser never stores the raw session token.

### File or URL submission

Home accepts click or drag-and-drop files from a documented extension list covering executables, Office, PDF, scripts, source, archives, shortcuts, and web content. Extension filtering is a picker/usability guard only; backend `file_type` detection from bytes is authoritative.

Files use multipart field `file` with `POST /api/samples`. URLs use `{ "url": value }` with `POST /api/links`. The backend validates/normalizes URLs and never fetches them.

### Progress and result navigation

Home polls `GET /api/samples/:id`, maps returned stage state into six conceptual steps, and exposes “View results” immediately after submission. Home also surfaces file-type and content-analysis summaries. Stages that are absent at terminal state are shown as not run/skipped rather than failed.

### Paged scan history and detail

The Reports page calls `GET /api/samples?limit=20&offset=N`, newest first. `sample_id` and `page` query parameters preserve selection and pagination on reload. Account/guest visibility follows the API's ownership rules.

Active scans refresh every two seconds. Polling pauses while the tab is hidden, stops for terminal jobs, and pauses on request errors until Retry. A slower previous request cannot overwrite a newly selected scan.

## Result interpretation

- Signature state is independent from ML risk.
- `risk_score` is displayed as a percentage and labeled with its heuristic/trained source; it is not detection accuracy.
- Anomaly output remains separate from the classifier/heuristic verdict.
- Failed or empty sandbox telemetry suppresses historical ML output rather than becoming zero activity.
- Raw and normalized sandbox field names are accepted; summary counts take precedence over abbreviated event arrays.
- Dynamic values are rendered as text. Browser tests include injection-shaped fixture content and verify no element execution.
- Detailed PE panels cover sections, imports, strings, resources, warnings, reputation, and YARA state when the real 1.2.0 report exists.

## API boundary

| Operation | Route |
| --- | --- |
| Current user | `GET /api/auth/me` |
| Register/login/logout | `POST /api/auth/register`, `/login`, `/logout` |
| Submit file | `POST /api/samples` |
| Submit URL | `POST /api/links` |
| Paged scan history | `GET /api/samples?limit=20&offset=N` |
| Selected scan/polling | `GET /api/samples/:id` |

Exact shapes are in the [backend API contract](../../backend/docs/api-contract.md).

## Testing

| Test source | Coverage |
| --- | --- |
| `backend/test/dashboardData.test.js` | Seven Node tests for raw/normalized telemetry, unavailable data, risk/anomaly separation, signatures, and stage state |
| `backend/test/dashboard/reports.browser.test.js` | Eight Playwright tests for history, selection, polling, retry, responsive layout, safe rendering, Home navigation, and an inert real-backend workflow |

From the repository root:

```bash
node --test backend/test/dashboardData.test.js
cd backend
npm run test:dashboard
```

Playwright needs its Chromium binary or `DASHBOARD_BROWSER_PATH` pointing to a compatible Chrome. Tests use synthetic fixtures and temporary data; they do not invoke a live sandbox.

## Accessibility and usability

Current positive behavior includes native controls, visible labels, text plus color state, explicit loading/failure/unavailable views, responsive tests, reduced-motion support, keyboard-operable history buttons, and retry controls.

Remaining gaps include large inline Home scripts, alert-based validation, incomplete focus/live-region behavior, no audited screen-reader flow, and no formal non-expert user study.

## Security and privacy

- Same-origin serving reduces cookie/CORS complexity; production still needs HTTPS and `COOKIE_SECURE=true`.
- Treat reports as sensitive; guest history is shared by guest scope in the current backend design.
- Dynamic text must continue to use text nodes rather than HTML interpolation.
- Browser extension checks are not a security boundary.
- External-report links and provider output require safe text rendering and data-policy review.

## Known limitations

- The report stage summary omits `file_type` and `content_analysis`.
- Content-analysis and LLM results do not have equivalent complete detail renderers.
- The PE renderer reports limited output for mock/legacy reports.
- No capabilities endpoint tells the UI which optional stages are enabled.
- No frontend build/lint/format system or accessibility suite is defined.

## Next work

1. Add file-type/content-analysis and LLM detail panels.
2. Expose backend capabilities so pending/not-run labels can explain why.
3. Add accessible live announcements, focus management, inline validation, and audit coverage.
4. Add deletion/retention UX after the backend defines policy and endpoints.
5. Validate display against real-but-inert integrated reports from each optional service.

## Related documentation

- [Architecture](../architecture.md)
- [Setup and Operations](../setup-and-operations.md)
- [Prototype Status](../prototype-status.md)
- [Backend component](backend.md)
