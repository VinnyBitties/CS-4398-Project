"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");
const express = require("express");
const { chromium } = require("playwright");
const { complete, raw } = require("./fixtures");
let browser, server, origin;
test.before(async () => {
  const app = express(); app.use(express.static(path.resolve(__dirname, "../../../website")));
  server = app.listen(0, "127.0.0.1");
  await new Promise(resolve => server.once("listening", resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({ headless: true, executablePath: process.env.DASHBOARD_BROWSER_PATH || undefined });
});
test.after(async () => { if (browser) await browser.close(); if (server) await new Promise(resolve => server.close(resolve)); });
async function setup(t, options = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1080 } });
  t.after(() => context.close());
  const page = await context.newPage(), errors = [];
  page.on("pageerror", error => errors.push(error.message));
  t.after(() => assert.deepEqual(errors, []));
  await page.addInitScript(() => { window.SENTINEL_API_BASE = location.origin; });
  const all = options.samples || Array.from({ length: 22 }, (_, i) => complete(i + 1));
  const calls = { details: 0, offsets: [] };
  await page.route("**/api/**", async route => {
    const url = new URL(route.request().url());
    const reply = (data, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
    if (url.pathname === "/api/auth/me") return reply({ user: null });
    if (url.pathname === "/api/samples" && route.request().method() === "POST") return reply(complete(1), 202);
    if (url.pathname === "/api/samples") {
      const offset = Number(url.searchParams.get("offset")); calls.offsets.push(offset);
      if (options.historyFailure && options.historyFailure()) return route.abort();
      return reply({ total: all.length, samples: all.slice(offset, offset + 20) });
    }
    const id = Number(url.pathname.split("/").at(-1)); calls.details++;
    if (options.detail) return options.detail({ id, calls, reply, route });
    const sample = all.find(item => item.sample_id === id);
    return reply(sample || { error: "not_found" }, sample ? 200 : 404);
  });
  return { page, calls };
}
test("scan charts, safe evidence, signature alert, pagination, refresh, URL selection and responsive layout", async t => {
  const { page } = await setup(t);
  await page.goto(origin + "/dashboard/reports.html?sample_id=1");
  await page.waitForSelector("#scan-content:not([hidden])");
  assert.equal(await page.locator("#risk-value").innerText(), "72");
  assert.match(await page.locator("#risk-threshold").innerText(), /26/);
  assert.equal(await page.locator("#synthetic-notice").isVisible(), true);
  assert.equal(await page.locator("#signature-alert").isVisible(), true);
  await page.locator(".counts-details summary").click();
  assert.deepEqual(await page.locator("#activity-counts td").allTextContents(), ["3", "2", "2", "4", "12"]);
  await page.locator('.event-details[data-key="processes"] summary').click();
  assert.match(await page.locator('.event-details[data-key="processes"] tbody').innerText(), /<img/);
  assert.equal(await page.locator("#scan-content img").count(), 0);
  assert.equal(await page.evaluate(() => window.injected), undefined);
  if (process.env.DASHBOARD_SCREENSHOT_DIR) {
    fs.mkdirSync(process.env.DASHBOARD_SCREENSHOT_DIR, { recursive: true });
    await page.screenshot({ path: path.join(process.env.DASHBOARD_SCREENSHOT_DIR, "reports-desktop.png"), fullPage: true });
  }
  await page.getByRole("button", { name: "Next history page" }).click();
  await page.waitForSelector('.history-item[data-sample-id="21"]');
  await page.locator('.history-item[data-sample-id="21"]').click();
  await page.waitForFunction(() => document.getElementById("sample-label").textContent.includes("SCAN 21"));
  assert.match(page.url(), /sample_id=21/);
  assert.match(page.url(), /page=2/);
  await page.reload();
  await page.waitForSelector('.history-item[aria-current="true"][data-sample-id="21"]');
  await page.waitForSelector("#scan-content:not([hidden])");
  assert.match(await page.locator("#sample-label").innerText(), /SCAN 21/);
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  if (process.env.DASHBOARD_SCREENSHOT_DIR) await page.screenshot({ path: path.join(process.env.DASHBOARD_SCREENSHOT_DIR, "reports-mobile.png"), fullPage: true });
});
test("connection failure pauses polling, Retry resumes, and terminal scan stops polling", async t => {
  let state = "running";
  const { page, calls } = await setup(t, { detail: async ({ id, reply, route }) => {
    if (state === "error") return route.abort();
    const sample = complete(id); sample.status = state;
    if (state === "running") sample.results = [{ stage: "sandbox", status: "running" }];
    return reply(sample);
  } });
  await page.goto(origin + "/dashboard/reports.html?sample_id=1");
  await page.waitForSelector("#scan-content:not([hidden])");
  assert.match(await page.locator("#stage-list").innerText(), /Pending/);
  state = "error";
  await page.waitForSelector("#retry-detail:not([hidden])");
  const failedCalls = calls.details;
  await page.waitForTimeout(2200);
  assert.equal(calls.details, failedCalls);
  state = "completed";
  await page.getByRole("button", { name: "Retry scan", exact: true }).click();
  await page.waitForFunction(() => document.getElementById("risk-value").textContent === "72");
  const finalCalls = calls.details;
  await page.waitForTimeout(2200);
  assert.equal(calls.details, finalCalls);
});
test("completed scan with sandbox failure shows failure and unavailable graphs", async t => {
  const sample = complete(); sample.results[1].status = "failed"; sample.results[1].error = { message: "Failed to reach sandbox service" };
  const { page } = await setup(t, { samples: [sample] });
  await page.goto(origin + "/dashboard/reports.html");
  await page.waitForSelector("#scan-content:not([hidden])");
  assert.equal(await page.locator("#risk-value").innerText(), "—");
  assert.match(await page.locator("#stage-list").innerText(), /Failed to reach sandbox service/);
  assert.equal(await page.locator("#job-status").innerText(), "Completed");
  assert.equal(await page.locator("#anomaly-result").innerText(), "Unavailable");
  assert.match(await page.locator("#activity-message").innerText(), /Unavailable/);
});
test("empty history, network retry, and unknown scan ID have explicit states", async t => {
  let fail = true;
  const { page } = await setup(t, { samples: [], historyFailure: () => fail });
  await page.goto(origin + "/dashboard/reports.html?sample_id=9");
  await page.waitForSelector("#retry-history:not([hidden])");
  await page.waitForFunction(() => document.getElementById("detail-message").textContent.includes("belongs to another account"));
  fail = false;
  await page.getByRole("button", { name: "Retry history" }).click();
  await page.waitForFunction(() => document.getElementById("history-message").textContent.includes("No scans yet"));
  assert.equal(await page.locator("#next-page").isDisabled(), true);
  assert.equal(await page.locator("#scan-content").isVisible(), false);
});
test("raw report format and partial heuristic/anomaly output render independently", async t => {
  const sample = raw(); const ml = sample.results[2].report;
  ml.prediction_source = "heuristic"; ml.risk_score = .2; ml.risk_level = "low"; delete ml.threshold;
  const { page } = await setup(t, { samples: [sample] });
  await page.goto(origin + "/dashboard/reports.html");
  await page.waitForSelector("#scan-content:not([hidden])");
  assert.equal(await page.locator("#risk-value").innerText(), "20");
  assert.match(await page.locator("#risk-source").innerText(), /Heuristic/);
  assert.match(await page.locator("#risk-threshold").innerText(), /unavailable/);
  assert.match(await page.locator("#anomaly-score").innerText(), /-0.17/);
});
test("Home exposes View results immediately after submission and hides it on reset", async t => {
  const { page } = await setup(t);
  await page.goto(origin + "/dashboard/home.html");
  await page.locator('input[type="file"]').setInputFiles({ name: "synthetic.exe", mimeType: "application/octet-stream", buffer: Buffer.from("synthetic browser fixture") });
  await page.evaluate(() => sendOff());
  await page.waitForSelector("#view-results:not([hidden])");
  assert.equal(await page.locator("#view-results").getAttribute("href"), "reports.html?sample_id=1");
  await page.locator("#view-results").click();
  await page.waitForSelector("#scan-content:not([hidden])");
  assert.match(await page.locator("#sample-label").innerText(), /SCAN 1/);
  await page.goto(origin + "/dashboard/home.html");
  await page.evaluate(() => resetScan());
  assert.equal(await page.locator("#view-results").isVisible(), false);
});

test("a delayed previous scan cannot overwrite the selected scan's panels", async t => {
  let release;
  const delayed = new Promise(resolve => { release = resolve; });
  t.after(() => release());
  const first = complete(1), second = complete(2);
  second.original_filename = "Second synthetic fixture.exe";
  second.results[0].report.matched = false;
  second.results[1].report.summary.processes_created = 9;
  second.results[2].report.risk_score = .83;
  second.results[2].report.anomaly_prediction = "known";
  const { page } = await setup(t, { samples: [first, second], detail: async ({ id, reply }) => {
    if (id === 1) await delayed;
    return reply(id === 1 ? first : second);
  } });
  await page.goto(origin + "/dashboard/reports.html?sample_id=1");
  await page.locator('.history-item[data-sample-id="2"]').click();
  await page.waitForFunction(() => document.getElementById("risk-value").textContent === "83");
  release();
  await page.waitForTimeout(100);
  assert.equal(await page.locator("#sample-name").innerText(), second.original_filename);
  assert.equal(await page.locator("#risk-value").innerText(), "83");
  assert.equal(await page.locator("#activity-counts td").first().textContent(), "9");
  assert.equal(await page.locator("#signature-alert").isVisible(), false);
  assert.equal(await page.locator("#anomaly-result").innerText(), "Within learned baseline");
  assert.match(page.url(), /sample_id=2/);
});

test("Home upload persists a scan and opens Reports through the real backend API", async t => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "sentinel-dashboard-"));
  const root = path.resolve(__dirname, "../../..");
  // Load backend modules only after isolating their database, uploads and services.
  Object.assign(process.env, {
    DATABASE_URL: "", DATABASE_PATH: path.join(temporary, "scans.db"),
    UPLOAD_DIR: path.join(temporary, "uploads"), SANDBOX_URL: "", LLM_DIR: "",
    SIGNATURE_HASHLIST_PATH: "", WEBSITE_DIR: path.join(root, "website"),
    ANALYZER_SCRIPT_PATH: path.join(root, "backend/scripts/mock_analyze.py"),
    PYTHON_PATH: process.env.DASHBOARD_PYTHON_PATH || (process.platform === "win32" ? path.join(root, ".venv/Scripts/python.exe") : "python3"),
  });
  const db = require("../../src/db");
  const { queue } = require("../../src/queue/jobQueue");
  const { createApp } = require("../../src/app");
  await db.ready;
  await queue.start();
  const apiServer = createApp().listen(0, "127.0.0.1");
  await new Promise(resolve => apiServer.once("listening", resolve));
  const context = await browser.newContext();
  t.after(async () => {
    await context.close();
    queue.stop();
    await new Promise(resolve => apiServer.close(resolve));
    while (queue.stats().active) await new Promise(resolve => setTimeout(resolve, 50));
    await db.close();
    const relative = path.relative(path.resolve(os.tmpdir()), path.resolve(temporary));
    assert.ok(relative && !relative.startsWith("..") && !path.isAbsolute(relative));
    fs.rmSync(temporary, { recursive: true, force: true });
  });
  const page = await context.newPage();
  await page.addInitScript(() => { window.SENTINEL_API_BASE = location.origin; });
  const apiOrigin = `http://127.0.0.1:${apiServer.address().port}`;
  await page.goto(apiOrigin + "/dashboard/home.html");
  await page.locator('input[type="file"]').setInputFiles({ name: "synthetic-stored-fixture.exe", mimeType: "application/octet-stream", buffer: Buffer.from("Synthetic dashboard fixture; mock analyzer only.") });
  await page.evaluate(() => sendOff());
  await page.waitForSelector("#view-results:not([hidden])");
  await page.locator("#view-results").click();
  await page.waitForFunction(() => document.getElementById("job-status").textContent === "Completed");
  assert.equal(await page.locator("#sample-name").innerText(), "synthetic-stored-fixture.exe");
  const response = await context.request.get(apiOrigin + "/api/samples?limit=20&offset=0");
  const history = await response.json();
  assert.equal(history.total, 1);
  const detailResponse = await context.request.get(apiOrigin + "/api/samples/" + history.samples[0].sample_id);
  const detail = await detailResponse.json();
  assert.equal(detail.results.find(result => result.stage === "static_analysis").status, "complete");
  assert.equal(await page.locator("#risk-level").innerText(), "Unavailable");
  await page.reload();
  await page.waitForSelector("#scan-content:not([hidden])");
  assert.equal(await page.locator("#sample-name").innerText(), "synthetic-stored-fixture.exe");
});
