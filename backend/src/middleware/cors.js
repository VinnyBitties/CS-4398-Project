"use strict";

/**
 * CORS for the dashboard when its pages are served from a different origin
 * than the API (for example VS Code Live Server on port 5500). Only origins
 * listed in CORS_ORIGINS get access, and credentials (the session cookie) are
 * allowed for them. Not needed at all when the backend serves website/.
 */

const config = require("../config");

function cors(req, res, next) {
  const origin = req.headers.origin;
  if (origin && config.corsOrigins.includes(origin)) {
    res.set("Access-Control-Allow-Origin", origin);
    res.set("Access-Control-Allow-Credentials", "true");
    res.set("Vary", "Origin");
    if (req.method === "OPTIONS") {
      res.set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
      res.set("Access-Control-Allow-Headers", "Content-Type");
      res.set("Access-Control-Max-Age", "600");
      return res.status(204).end();
    }
  }
  return next();
}

module.exports = { cors };
