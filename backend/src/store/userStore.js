"use strict";

/**
 * All SQL for users and sessions. Session tokens are generated here and only
 * their SHA-256 is written to the database.
 */

const crypto = require("node:crypto");
const db = require("../db");

function hashToken(token) {
  return crypto.createHash("sha256").update(token).digest("hex");
}

function publicUser(row) {
  return row ? { id: row.id, username: row.username, created_at: row.created_at } : null;
}

/** Returns the new user, or null if the username is taken (case-insensitive). */
async function createUser(username, passwordHash) {
  try {
    const id = await db.insert("INSERT INTO users (username, password_hash) VALUES (?, ?)", [username, passwordHash]);
    return publicUser(await db.get("SELECT * FROM users WHERE id = ?", [id]));
  } catch (err) {
    if (db.isUniqueViolation(err)) return null;
    throw err;
  }
}

function getUserByUsername(username) {
  return db.get("SELECT * FROM users WHERE lower(username) = lower(?)", [username]);
}

/** Starts a session and returns the raw token for the cookie. */
async function createSession(userId, ttlHours) {
  const now = db.now();
  await db.run("DELETE FROM sessions WHERE expires_at <= ?", [now]);
  const token = crypto.randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + ttlHours * 3600 * 1000).toISOString();
  await db.run("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)", [
    hashToken(token),
    userId,
    expiresAt,
  ]);
  await db.run("UPDATE users SET last_login_at = ? WHERE id = ?", [now, userId]);
  return token;
}

async function getUserForToken(token) {
  if (!token) return null;
  const row = await db.get(
    `SELECT u.id, u.username, u.created_at
     FROM sessions s JOIN users u ON u.id = s.user_id
     WHERE s.token_hash = ? AND s.expires_at > ?`,
    [hashToken(token), db.now()]
  );
  return publicUser(row);
}

async function deleteSession(token) {
  if (token) await db.run("DELETE FROM sessions WHERE token_hash = ?", [hashToken(token)]);
}

module.exports = { createUser, getUserByUsername, createSession, getUserForToken, deleteSession };
