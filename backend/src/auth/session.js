"use strict";

/**
 * Session cookie handling and the middleware that puts the signed-in user on
 * `req.user` (or null for a guest).
 *
 * The cookie is HttpOnly (page scripts can't read it, so an XSS bug can't
 * steal it) and SameSite=Lax (another site can't make the browser send it
 * with a cross-site POST).
 */

const config = require("../config");
const users = require("../store/userStore");

const COOKIE_NAME = "sentinel_session";

function readCookie(req, name) {
  const header = req.headers.cookie;
  if (!header) return null;
  for (const part of header.split(";")) {
    const eq = part.indexOf("=");
    if (eq === -1) continue;
    if (part.slice(0, eq).trim() === name) {
      try {
        return decodeURIComponent(part.slice(eq + 1).trim());
      } catch (_) {
        return null;
      }
    }
  }
  return null;
}

function cookieOptions(maxAgeSeconds) {
  const opts = [`Path=/`, `HttpOnly`, `SameSite=Lax`, `Max-Age=${maxAgeSeconds}`];
  if (config.cookieSecure) opts.push("Secure");
  return opts.join("; ");
}

function setSessionCookie(res, token) {
  res.append("Set-Cookie", `${COOKIE_NAME}=${encodeURIComponent(token)}; ${cookieOptions(config.sessionTtlHours * 3600)}`);
}

function clearSessionCookie(res) {
  res.append("Set-Cookie", `${COOKIE_NAME}=; ${cookieOptions(0)}`);
}

function sessionToken(req) {
  return readCookie(req, COOKIE_NAME);
}

/** Runs on every /api request. Never rejects: guests get req.user = null. */
async function loadUser(req, res, next) {
  try {
    req.user = await users.getUserForToken(sessionToken(req));
    return next();
  } catch (err) {
    return next(err);
  }
}

/** For routes that need a signed-in user. */
function requireUser(req, res, next) {
  if (!req.user) {
    return res.status(401).json({ error: "not_authenticated", message: "Log in to use this route." });
  }
  return next();
}

module.exports = { COOKIE_NAME, loadUser, requireUser, setSessionCookie, clearSessionCookie, sessionToken };
