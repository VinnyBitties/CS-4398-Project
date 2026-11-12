# Scan reports dashboard

Open `http://localhost:3000/dashboard/reports.html` with the backend running,
or choose **View results** from Home after submitting a scan. The page uses
the existing session cookie and `/api/samples` endpoints. `sample_id` and
history `page` query parameters preserve selection and pagination on refresh.
History is newest first, 20 scans per page; the first scan is selected when no
ID is supplied. Existing guest/account visibility rules still apply.

All pages share `website/retro.css` and `website/retro-loading.js` for the
gold-and-charcoal retro theme and stepped loading reveal. Home and sign-in
layouts live in `website/retro-pages.css`. The reveal is cosmetic: requests
start immediately, Skip animation reveals everything, and reduced-motion
preferences disable it. Reports replays it for a new selection, never for
background polling updates.

Risk and anomaly results are separate. The gauge displays `risk_score * 100`,
the returned risk level, and threshold when supplied. It is not detection
accuracy. Only completed stages supply charts. Missing, failed, or empty
sandbox telemetry does not become zero risk; even an older ML verdict is
suppressed when its sandbox is explicitly failed or empty. Stage failures
remain visible when a job has overall status `completed`.

Both raw sandbox reports (`telemetry` plus `process_count`, etc.) and normalized
reports (top-level events plus `processes_created`, etc.) are supported.
Summary counts take precedence over event-array lengths. Remote-thread zeros
are not charted, since the current adapter can use zero for uncaptured events.
Event tables display returned details, which may be a subset of the totals;
large tables load another 100 rows when requested. No event timeline is shown
because the current parser does not supply event timestamps.

Active scans refresh every two seconds. Polling stops for terminal jobs, pauses
when the tab is hidden, and pauses on request failures with a Retry button.
History refresh is manual. An absent stage is Pending during a running job or
Not run after completion; the API does not identify why it did not run.

## Verification

From the repository root:

```powershell
npm.cmd --prefix backend ci
node --test backend/test/dashboardData.test.js
```

Browser tests use Playwright as a development-only dependency. Install its
Chromium browser once, then run the isolated fixture-backed tests:

```powershell
cd backend
npx.cmd playwright install chromium
npm.cmd run test:dashboard
```

Alternatively, use an installed Chrome executable without downloading Chromium:

```powershell
$env:DASHBOARD_BROWSER_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
npm.cmd --prefix backend run test:dashboard
```

The last command is run from the repository root. Set
`DASHBOARD_SCREENSHOT_DIR` to a temporary directory to capture desktop/mobile
screenshots. UI tests start their own HTTP server and intercept API requests
with clearly marked synthetic fixtures. An additional integration test starts
the real backend with a temporary SQLite database and the mock static analyzer,
uploads an inert fixture from Home, and verifies stored results through the API.
It uses `.venv/Scripts/python.exe` on Windows or `python3` elsewhere; override
this with `DASHBOARD_PYTHON_PATH` if needed. Temporary data is removed afterward.
Tests do not submit files to a sandbox, modify the live database, or verify real
detonation. A successful live sandbox run is still needed to verify that flow.
All dynamic report values are rendered as text, including submitted URLs.
