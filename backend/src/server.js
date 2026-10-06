"use strict";

const { createApp } = require("./app");
const config = require("./config");
const { queue } = require("./queue/jobQueue");
const { getCatalog } = require("./signatures/catalog");

// Load the catalog before accepting traffic: a malformed catalog should stop
// the server with a clear message, not fail the first scan.
const catalog = getCatalog();
console.log(
  `Signature catalog loaded: ${catalog.size.sha256} hashes, ${catalog.size.domain} domains, ${catalog.size.url} URLs`
);

const app = createApp();

app.listen(config.port, () => {
  const { requeued } = queue.start();
  if (requeued > 0) console.log(`Re-queued ${requeued} scan(s) interrupted by the last shutdown`);
  console.log(`Sentinel backend listening on port ${config.port}`);
});
