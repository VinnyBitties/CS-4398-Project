"use strict";

/**
 * Accounts and sessions.
 *
 *   POST /api/auth/register  { username, password }  -> 201 { user }  (and signs in)
 *   POST /api/auth/login     { username, password }  -> 200 { user }
 *   POST /api/auth/logout                            -> 204
 *   GET  /api/auth/me                                -> 200 { user } | 401
 *
 * A successful register or login sets the HttpOnly `sentinel_session`
 * cookie; the browser sends it back on every later request. The frontend
 * must call fetch() with `credentials: "include"` when it is served from a
 * different origin than the API.
 */

const express = require("express");
const config = require("../config");
const users = require("../store/userStore");
const { hashPassword, verifyPassword, verifyAgainstDummy } = require("../auth/passwords");
const { setSessionCookie, clearSessionCookie, sessionToken } = require("../auth/session");

const router = express.Router();

const USERNAME_RE = /^[A-Za-z0-9_.-]{3,32}$/;
const MIN_PASSWORD = 8;
const MAX_PASSWORD = 128;

// ---- failed-login throttle -------------------------------------------------
// In memory, keyed by IP + username: enough for one backend process. It slows
// password guessing without letting someone lock a user out from elsewhere.
const LOCKOUT_MS = 15 * 60 * 1000;
const failures = new Map();

function throttleKey(req, username) {
  return `${req.ip}|${username.toLowerCase()}`;
}

function isLockedOut(key) {
  const entry = failures.get(key);
  if (!entry) return false;
  if (Date.now() - entry.first > LOCKOUT_MS) {
    failures.delete(key);
    return false;
  }
  return entry.count >= config.maxFailedLogins;
}

function recordFailure(key) {
  const entry = failures.get(key);
  if (!entry || Date.now() - entry.first > LOCKOUT_MS) failures.set(key, { count: 1, first: Date.now() });
  else entry.count += 1;
}

// ---- helpers ---------------------------------------------------------------

function readCredentials(req) {
  const body = req.body || {};
  return {
    username: typeof body.username === "string" ? body.username.trim() : "",
    password: typeof body.password === "string" ? body.password : "",
  };
}

async function signIn(res, user) {
  setSessionCookie(res, await users.createSession(user.id, config.sessionTtlHours));
}

// ---- routes ----------------------------------------------------------------

router.post("/auth/register", async (req, res, next) => {
  if (!config.allowRegistration) {
    return res.status(403).json({ error: "registration_closed", message: "New accounts are not being accepted." });
  }
  const { username, password } = readCredentials(req);
  if (!USERNAME_RE.test(username)) {
    return res.status(400).json({
      error: "invalid_username",
      message: "Usernames are 3 to 32 characters: letters, numbers, dot, dash or underscore.",
    });
  }
  if (password.length < MIN_PASSWORD || password.length > MAX_PASSWORD) {
    return res.status(400).json({
      error: "invalid_password",
      message: `Passwords must be ${MIN_PASSWORD} to ${MAX_PASSWORD} characters.`,
    });
  }
  try {
    const user = await users.createUser(username, await hashPassword(password));
    if (!user) {
      return res.status(409).json({ error: "username_taken", message: "That username is already in use." });
    }
    await signIn(res, user);
    return res.status(201).json({ user });
  } catch (err) {
    return next(err);
  }
});

router.post("/auth/login", async (req, res, next) => {
  const { username, password } = readCredentials(req);
  if (!username || !password) {
    return res.status(400).json({ error: "missing_credentials", message: "Enter a username and password." });
  }
  const key = throttleKey(req, username);
  if (isLockedOut(key)) {
    return res.status(429).json({ error: "too_many_attempts", message: "Too many failed logins. Try again in 15 minutes." });
  }
  try {
    const row = await users.getUserByUsername(username);
    const ok = row ? await verifyPassword(password, row.password_hash) : await verifyAgainstDummy(password);
    if (!ok) {
      recordFailure(key);
      // Same message whether the username or the password was wrong.
      return res.status(401).json({ error: "invalid_credentials", message: "Incorrect username or password." });
    }
    failures.delete(key);
    const user = { id: row.id, username: row.username, created_at: row.created_at };
    await signIn(res, user);
    return res.json({ user });
  } catch (err) {
    return next(err);
  }
});

router.post("/auth/logout", async (req, res, next) => {
  try {
    await users.deleteSession(sessionToken(req));
    clearSessionCookie(res);
    return res.status(204).end();
  } catch (err) {
    return next(err);
  }
});

router.get("/auth/me", (req, res) => {
  if (!req.user) return res.status(401).json({ error: "not_authenticated" });
  return res.json({ user: req.user });
});

// Exposed for tests.
router._resetThrottle = () => failures.clear();

module.exports = router;
