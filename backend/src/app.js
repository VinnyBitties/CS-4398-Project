"use strict";

const fs = require("node:fs");
const express = require("express");
const config = require("./config");
const healthRoutes = require("./routes/health");
const authRoutes = require("./routes/auth");
const sampleRoutes = require("./routes/samples");
const { loadUser } = require("./auth/session");
const { cors } = require("./middleware/cors");

function createApp() {
  const app = express();
  app.disable("x-powered-by");
  app.use(express.json({ limit: "100kb" }));

  // Every /api request knows who is calling: req.user, or null for a guest.
  app.use("/api", cors, loadUser);

  app.use("/api", healthRoutes);
  app.use("/api", authRoutes);
  app.use("/api", sampleRoutes);

  // Serve the dashboard pages from the same origin as the API, so the
  // session cookie is sent without any CORS setup: http://localhost:3000/
  if (config.websiteDir && fs.existsSync(config.websiteDir)) {
    app.use(express.static(config.websiteDir));
  }

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
