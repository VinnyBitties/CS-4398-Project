"use strict";

// Every test file requires this first. It picks the database the tests use:
//
//   npm test                                  -> in-memory SQLite (default)
//   TEST_DATABASE_URL=postgres://... npm run test:pg  -> that PostgreSQL
//
// DATABASE_URL from .env is deliberately ignored, so `npm test` can never
// write to the team's shared Azure database.
process.env.DATABASE_URL = process.env.TEST_DATABASE_URL || "";
process.env.DATABASE_SSL = process.env.TEST_DATABASE_SSL || "false";
process.env.DATABASE_PATH = ":memory:";

/** Empties every table, so a PostgreSQL test database starts each file clean. */
async function resetDb() {
  const db = require("../../src/db");
  if (db.dialect !== "postgres") return; // in-memory SQLite is already fresh
  await db.ready;
  await db.run("TRUNCATE users, sessions, samples, results, jobs RESTART IDENTITY CASCADE");
}

module.exports = { resetDb };
