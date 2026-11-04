# Frontend Dashboard

## Purpose and status

The frontend provides account entry, guest access, file or URL submission, and a stage-by-stage progress display. Its current status is **Partial**: the submission path is connected to the backend, but report history and detailed result presentation are unfinished.

## Source layout

| Path | Responsibility |
| --- | --- |
| `website/index.html` | Login, account creation, and guest entry |
| `website/api.js` | Shared Fetch wrapper, authentication calls, submissions, polling retrieval, account rendering |
| `website/dashboard/home.html` | File/URL input, progress animation, polling, scan reset |
| `website/dashboard/reports.html` | Report list and pagination scaffold; no API integration |
| `website/style.css` | Login/account page styles |
| `website/dashboard/*.css` | Dashboard, home, and report styles |

The backend serves this directory by default, which keeps pages and session cookies on one origin.

## Screens and user workflows

### Login and registration

The root page attempts `GET /api/auth/me`; an existing session redirects to the dashboard. Login sends a username/password to `POST /api/auth/login`. Registration validates matching passwords in the browser, calls `POST /api/auth/register`, and redirects on success. “No Sign In” enters the dashboard as a guest.

The browser never stores a session token directly. The backend owns an HttpOnly cookie. When the site is served separately, `api.js` sends `credentials: include` and the origin must be allowed by backend CORS configuration.

### File submission

The home page accepts click or drag-and-drop selection and checks for a lowercase-normalized `.exe` suffix. Submission creates `FormData` with field name `file` and calls `POST /api/samples`. File content and PE validity are not examined in the browser.

### URL submission

Typing in the URL field selects a string submission and clears the selected file display. The frontend sends `{ "url": value }` to `POST /api/links`. The backend performs URL normalization and validation.

### Progress display

After a successful `202` response, the page polls `GET /api/samples/:id`. It maps stored stage names to six conceptual UI steps:

1. Signature
2. Static analysis
3. Static ML score
4. Sandbox
5. Behavioral ML score
6. Report

Running, completed, failed, and skipped/not-run labels are shown. Because `static_ml` does not exist and optional stages may be disabled, several conceptual steps normally end as skipped. A network failure uses a longer retry; a non-network HTTP error ends the view. “Scan another” clears the polling timer and form/progress state.

## API boundary

| Operation | Frontend helper | Backend route |
| --- | --- | --- |
| Current user | `auth.currentUser()` | `GET /api/auth/me` |
| Login | `auth.login()` | `POST /api/auth/login` |
| Register | `auth.register()` | `POST /api/auth/register` |
| Logout | `auth.logout()` | `POST /api/auth/logout` |
| File submission | `scans.submitFile()` | `POST /api/samples` |
| URL submission | `scans.submitLink()` | `POST /api/links` |
| Poll one scan | `scans.get()` | `GET /api/samples/:id` |
| List history | Not implemented | `GET /api/samples` |

Exact request and response fields are in the [backend API contract](../../backend/docs/api-contract.md).

## Configuration and startup

Run the backend and open `http://localhost:3000/`; no separate frontend build is required. If another server hosts the static files, set `window.SENTINEL_API_BASE` or use the built-in fallback to `http://localhost:3000`, then add that page origin to `CORS_ORIGINS`.

## Loading, empty, and error behavior

- Login and registration buttons are disabled while their request runs.
- Submission changes to a progress panel with “Submitting...” then “Scanning...”.
- Stage records determine visible state; stages never present are shown as skipped at completion.
- Network loss while polling retries; other retrieval errors stop with a message.
- Backend JSON `message` is preferred, with a frontend fallback.
- The reports page currently renders an empty array; its empty view is not explained to the user.

## Accessibility and usability observations

Present positive elements include language metadata, viewport metadata, visible labels, native form controls, and text status in addition to animation/color. Remaining issues include alert-based validation, inline event handlers, large inline scripts, no announced live region for progress, limited keyboard/focus management for the account popup, unexplained empty reports, and no formal accessibility or user test.

## Test evidence

No frontend unit, browser integration, or accessibility suite is present. Backend API/auth tests cover the server routes used by the pages, but `npm test` did not start in the 2026-11-03 WSL 1/npm environment. No browser automation was performed during this documentation update.

## Security and privacy notes

- Treat displayed backend messages as untrusted text; current code assigns them through `textContent` in submission/login paths.
- The report list scaffold builds HTML strings and must escape server-supplied values when integrated.
- Client `.exe` validation is a usability check, not a security boundary.
- Same-origin backend serving reduces CORS complexity; production still requires HTTPS and secure cookies.
- Avoid exposing sensitive telemetry or reports to other guest users when history is integrated.

## Known limitations

- No report-history API call or detailed report view.
- No stage score, telemetry, evidence, or generated explanation renderer.
- No route handling beyond static paths.
- No frontend build, lint, formatting, test, or accessibility tooling.
- Optional stage availability is inferred from returned results, not a capabilities endpoint.

## Next work

1. Connect `GET /api/samples?limit=&offset=` with user/guest scope and safe DOM rendering.
2. Add a detailed scan view for stage results and clear evidence/status explanations.
3. Make incomplete and unavailable stages explicit before submission.
4. Add accessible status announcements, focus management, inline validation, and keyboard testing.
5. Add browser-level tests for account, submission, polling, failure, and history flows.

## Related documentation

- [Architecture](../architecture.md)
- [Setup and Operations](../setup-and-operations.md)
- [Prototype Status](../prototype-status.md)
- [Backend component](backend.md)
