"use strict";

const { createApp } = require("./app");
const config = require("./config");
const db = require("./db");
const { queue } = require("./queue/jobQueue");
const { getCatalog } = require("./signatures/catalog");

// Load the catalog before accepting traffic: a malformed catalog should stop
// the server with a clear message, not fail the first scan.
const catalog = getCatalog();
console.log(
  `Signature catalog loaded: ${catalog.size.sha256} hashes, ${catalog.size.domain} domains, ${catalog.size.url} URLs`
);

async function main() {
  // Connect and create the tables before taking requests, so a wrong
  // DATABASE_URL or a blocked firewall shows up here, not on the first scan.
  console.log(`Database: ${db.describe()}`);
  await db.ready;
  await db.get("SELECT 1 AS ok");

  const { requeued } = await queue.start();
  if (requeued > 0) console.log(`Re-queued ${requeued} scan(s) interrupted by the last shutdown`);

  const app = createApp();
  app.listen(config.port, () => {
    console.log(`Sentinel backend listening on port ${config.port}`);
  });
}

main().catch((err) => {
  console.error(`Could not start: ${err.message}`);
  if (db.dialect === "postgres") {
    console.error(
      "Check DATABASE_URL in .env, and that your IP address is allowed in the Azure server's " +
        "Networking (firewall) settings. See docs/azure-database.md."
    );
  }
  process.exit(1);
});
