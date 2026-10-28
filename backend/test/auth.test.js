"use strict";

// Accounts, sessions, and scans being tied to the signed-in user.

const path = require("node:path");
const fs = require("node:fs");
const os = require("node:os");

const { resetDb } = require("./helpers/testDb");

process.env.ANALYZER_SCRIPT_PATH = path.join(__dirname, "..", "scripts", "mock_analyze.py");
process.env.UPLOAD_DIR = fs.mkdtempSync(path.join(os.tmpdir(), "sentinel-uploads-"));
process.env.MAX_FAILED_LOGINS = "3";
process.env.CORS_ORIGINS = "http://localhost:5500";

const test = require("node:test");
const assert = require("node:assert/strict");
const request = require("supertest");
const { createApp } = require("../src/app");
const db = require("../src/db");
const authRoutes = require("../src/routes/auth");

const app = createApp();

test.before(resetDb);
const fixture = path.join(__dirname, "fixtures", "sample.bin");

let n = 0;
function freshName() {
  n += 1;
  return `tester${n}`;
}

async function registered(username = freshName(), password = "correct-horse-1") {
  const agent = request.agent(app);
  const res = await agent.post("/api/auth/register").send({ username, password });
  assert.equal(res.status, 201, JSON.stringify(res.body));
  return { agent, username, password, user: res.body.user };
}

test("register creates an account, signs in, and never returns the hash", async () => {
  const agent = request.agent(app);
  const username = freshName();
  const res = await agent.post("/api/auth/register").send({ username, password: "correct-horse-1" });

  assert.equal(res.status, 201);
  assert.equal(res.body.user.username, username);
  assert.equal(res.body.user.password_hash, undefined);

  const cookie = res.headers["set-cookie"].join(";");
  assert.match(cookie, /sentinel_session=/);
  assert.match(cookie, /HttpOnly/);
  assert.match(cookie, /SameSite=Lax/);

  const me = await agent.get("/api/auth/me");
  assert.equal(me.status, 200);
  assert.equal(me.body.user.username, username);
});

test("passwords and session tokens are stored hashed", async () => {
  const { username, password } = await registered();
  const row = await db.get("SELECT password_hash FROM users WHERE username = ?", [username]);
  assert.match(row.password_hash, /^scrypt\$/);
  assert.ok(!row.password_hash.includes(password));

  const agent = request.agent(app);
  const res = await agent.post("/api/auth/login").send({ username, password });
  const token = decodeURIComponent(/sentinel_session=([^;]+)/.exec(res.headers["set-cookie"][0])[1]);
  const stored = Number((await db.get("SELECT COUNT(*) AS n FROM sessions WHERE token_hash = ?", [token])).n);
  assert.equal(stored, 0, "raw token must not be in the database");
});

test("register rejects bad input and duplicate usernames (case-insensitive)", async () => {
  const short = await request(app).post("/api/auth/register").send({ username: "ab", password: "correct-horse-1" });
  assert.equal(short.status, 400);
  assert.equal(short.body.error, "invalid_username");

  const weak = await request(app).post("/api/auth/register").send({ username: freshName(), password: "short" });
  assert.equal(weak.status, 400);
  assert.equal(weak.body.error, "invalid_password");

  const { username } = await registered();
  const dup = await request(app)
    .post("/api/auth/register")
    .send({ username: username.toUpperCase(), password: "correct-horse-1" });
  assert.equal(dup.status, 409);
  assert.equal(dup.body.error, "username_taken");
});

test("login succeeds with the right password and fails the same way for wrong user or password", async () => {
  const { username, password } = await registered();

  const ok = await request(app).post("/api/auth/login").send({ username, password });
  assert.equal(ok.status, 200);
  assert.equal(ok.body.user.username, username);

  const wrongPass = await request(app).post("/api/auth/login").send({ username, password: "nope-nope-nope" });
  const wrongUser = await request(app).post("/api/auth/login").send({ username: "nobody-here", password });
  assert.equal(wrongPass.status, 401);
  assert.equal(wrongUser.status, 401);
  assert.deepEqual(wrongPass.body, wrongUser.body);
});

test("repeated failed logins are locked out", async () => {
  authRoutes._resetThrottle();
  const { username, password } = await registered();
  for (let i = 0; i < 3; i += 1) {
    const res = await request(app).post("/api/auth/login").send({ username, password: "wrong-password" });
    assert.equal(res.status, 401);
  }
  const locked = await request(app).post("/api/auth/login").send({ username, password });
  assert.equal(locked.status, 429);
  assert.equal(locked.body.error, "too_many_attempts");
  authRoutes._resetThrottle();
});

test("logout ends the session", async () => {
  const { agent } = await registered();
  assert.equal((await agent.get("/api/auth/me")).status, 200);

  const out = await agent.post("/api/auth/logout");
  assert.equal(out.status, 204);
  assert.match(out.headers["set-cookie"].join(";"), /Max-Age=0/);
  assert.equal((await agent.get("/api/auth/me")).status, 401);
});

test("an expired session is not accepted", async () => {
  const { agent, user } = await registered();
  await db.run("UPDATE sessions SET expires_at = '2000-01-01T00:00:00.000Z' WHERE user_id = ?", [user.id]);
  assert.equal((await agent.get("/api/auth/me")).status, 401);
});

test("GET /api/auth/me is 401 for a guest", async () => {
  const res = await request(app).get("/api/auth/me");
  assert.equal(res.status, 401);
  assert.equal(res.body.error, "not_authenticated");
});

test("scans belong to whoever submitted them", async () => {
  const alice = await registered();
  const bob = await registered();

  const mine = await alice.agent.post("/api/links").send({ url: "https://alice.example/" });
  assert.equal(mine.status, 202);
  const file = await alice.agent.post("/api/samples").attach("file", fixture);
  assert.equal(file.status, 202);
  const guest = await request(app).post("/api/links").send({ url: "https://guest.example/" });

  // History is per user; guests see only guest scans.
  const aliceList = await alice.agent.get("/api/samples");
  assert.deepEqual(
    aliceList.body.samples.map((s) => s.sample_id).sort(),
    [mine.body.sample_id, file.body.sample_id].sort()
  );
  assert.equal(aliceList.body.total, 2);
  assert.equal((await bob.agent.get("/api/samples")).body.total, 0);
  const guestIds = (await request(app).get("/api/samples")).body.samples.map((s) => s.sample_id);
  assert.ok(guestIds.includes(guest.body.sample_id));
  assert.ok(!guestIds.includes(mine.body.sample_id));

  // Someone else's scan is a 404, not a 403.
  assert.equal((await alice.agent.get(`/api/samples/${mine.body.sample_id}`)).status, 200);
  assert.equal((await bob.agent.get(`/api/samples/${mine.body.sample_id}`)).status, 404);
  assert.equal((await request(app).get(`/api/samples/${mine.body.sample_id}`)).status, 404);
  assert.equal((await alice.agent.get(`/api/samples/${guest.body.sample_id}`)).status, 404);
});

test("CORS allows the configured dev origin with credentials, and no other", async () => {
  const pre = await request(app)
    .options("/api/auth/login")
    .set("Origin", "http://localhost:5500")
    .set("Access-Control-Request-Method", "POST");
  assert.equal(pre.status, 204);
  assert.equal(pre.headers["access-control-allow-origin"], "http://localhost:5500");
  assert.equal(pre.headers["access-control-allow-credentials"], "true");

  const other = await request(app).get("/api/health").set("Origin", "https://evil.example");
  assert.equal(other.headers["access-control-allow-origin"], undefined);
});

test("the backend serves the website pages", async () => {
  const res = await request(app).get("/index.html");
  assert.equal(res.status, 200);
  assert.match(res.text, /<html/i);
});
