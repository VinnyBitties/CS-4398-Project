"use strict";

const express = require("express");
const healthRoutes = require("./routes/health");
const sampleRoutes = require("./routes/samples");

function createApp() {
  const app = express();
  app.use(express.json({ limit: "100kb" }));

  app.use("/api", healthRoutes);
  app.use("/api", sampleRoutes);

  app.use((req, res) => {
    res.status(404).json({ error: "not_found" });
  });

  // Every error leaves as JSON with a stable `error` code, never an HTML
  // stack trace: the dashboard can branch on the code.
  // eslint-disable-next-line no-unused-vars
  app.use((err, req, res, next) => {
    if (err && err.name === "MulterError") {
      return res.status(413).json({ error: "upload_rejected", message: err.message });
    }
    if (err && err.type === "entity.parse.failed") {
      return res.status(400).json({ error: "invalid_json", message: "Request body is not valid JSON." });
    }
    console.error(err);
    return res.status(500).json({ error: "internal_error", message: "Unexpected server error." });
  });

  return app;
}

module.exports = { createApp };
