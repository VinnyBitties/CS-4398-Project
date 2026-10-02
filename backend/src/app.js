"use strict";

const express = require("express");
const healthRoutes = require("./routes/health");
const sampleRoutes = require("./routes/samples");

function createApp() {
  const app = express();
  app.use(express.json());

  app.use("/api", healthRoutes);
  app.use("/api", sampleRoutes);

  // Multer errors (e.g. file too large) land here instead of the generic
  // 500 handler, so the client gets a clear reason.
  app.use((err, req, res, next) => {
    if (err && err.name === "MulterError") {
      return res.status(413).json({ error: "upload_rejected", message: err.message });
    }
    return next(err);
  });

  app.use((req, res) => {
    res.status(404).json({ error: "not_found" });
  });

  return app;
}

module.exports = { createApp };
