"use strict";

/**
 * All SQL for users and sessions. Session tokens are generated here and only
 * their SHA-256 is written to the database.
 */

const crypto = require("node:crypto");
const db = require("../db");

const NOW = "strftime('%Y-%m-%dT%H:%M:%fZ', 'now')";

const stmts = {
  insertUser: db.prepare("INSERT INTO users (username, password_hash) VALUES (?, ?)"),
  getUserByUsername: db.prepare("SELECT * FROM users WHERE username = ?"),
  touchLogin: db.prepare(`UPDATE users SET last_login_at = ${NOW} WHERE id = ?`),

  insertSession: db.prepare(`
    INSERT INTO sessions (token_hash, user_id, expires_at)
    VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?))
  `),
  getSessionUser: db.prepare(`
    SELECT u.id, u.username, u.created_at, s.expires_at
    FROM sessions s JOIN users u ON u.id = s.user_id
    WHERE s.token_hash = ? AND s.expires_at > ${NOW}
  `),
  deleteSession: db.prepare("DELETE FROM sessions WHERE token_hash = ?"),
  deleteExpiredSessions: db.prepare(`DELETE FROM sessions WHERE expires_at <= ${NOW}`),
};

function hashToken(token) {
  return crypto.createHash("sha256").update(token).digest("hex");
}

function publicUser(row) {
  return row ? { id: row.id, username: row.username, created_at: row.created_at } : null;
}

/** Returns the new user, or null if the username is taken. */
function createUser(username, passwordHash) {
  try {
    const id = Number(stmts.insertUser.run(username, passwordHash).lastInsertRowid);
    return publicUser(db.prepare("SELECT * FROM users WHERE id = ?").get(id));
  } catch (err) {
    if (err && err.code === "SQLITE_CONSTRAINT_UNIQUE") return null;
    throw err;
  }
}

function getUserByUsername(username) {
  return stmts.getUserByUsername.get(username) || null;
}

/** Starts a session and returns the raw token for the cookie. */
function createSession(userId, ttlHours) {
  stmts.deleteExpiredSessions.run();
  const token = crypto.randomBytes(32).toString("base64url");
  stmts.insertSession.run(hashToken(token), userId, `+${ttlHours} hours`);
  stmts.touchLogin.run(userId);
  return token;
}

function getUserForToken(token) {
  if (!token) return null;
  return publicUser(stmts.getSessionUser.get(hashToken(token)));
}

function deleteSession(token) {
  if (token) stmts.deleteSession.run(hashToken(token));
}

module.exports = { createUser, getUserByUsername, createSession, getUserForToken, deleteSession };
