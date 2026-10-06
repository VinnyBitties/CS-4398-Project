"use strict";

/**
 * Signature catalog (FR02). analyze.py's sha256 field is explicitly "no
 * signature-catalog lookup is performed" (REPORT_CONTRACT.md) -- that lookup
 * is this backend's job, and this module is it.
 *
 * Two sources, both loaded once at startup:
 *
 *   1. signatures/catalog.json -- curated entries with a name, severity and
 *      source. Three entry types: "sha256" (file hash), "domain" (matches the
 *      host and any subdomain of it) and "url" (exact normalized URL).
 *   2. An optional bulk hash list (SIGNATURE_HASHLIST_PATH): one SHA-256 per
 *      line, blank lines and # comments ignored. This is the shape of a
 *      MalwareBazaar-style export, so a real feed can be dropped in without
 *      touching code.
 *
 * A malformed catalog throws at load rather than being skipped: a signature
 * that silently never matches is worse than a server that refuses to start
 * (that is exactly how a 63-character EICAR hash went unnoticed here).
 */

const fs = require("node:fs");
const config = require("../config");

const SHA256_RE = /^[0-9a-f]{64}$/;
const DOMAIN_RE = /^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}$/;
const ENTRY_TYPES = ["sha256", "domain", "url"];

class CatalogError extends Error {
  constructor(message) {
    super(message);
    this.name = "CatalogError";
  }
}

/** Canonical form of a submitted URL: lowercased host, no fragment. */
function normalizeUrl(input) {
  const u = new URL(input);
  u.hash = "";
  return u.href;
}

function buildCatalog(entries, bulkHashes = []) {
  const sha256 = new Map();
  const domains = new Map();
  const urls = new Map();

  entries.forEach((entry, i) => {
    const where = `catalog entry #${i + 1}`;
    if (!entry || typeof entry !== "object") throw new CatalogError(`${where} is not an object`);
    if (!ENTRY_TYPES.includes(entry.type)) {
      throw new CatalogError(`${where} has unknown type "${entry.type}" (expected ${ENTRY_TYPES.join(", ")})`);
    }
    if (typeof entry.value !== "string" || typeof entry.name !== "string" || !entry.name) {
      throw new CatalogError(`${where} needs string "value" and "name" fields`);
    }
    const meta = {
      type: entry.type,
      name: entry.name,
      severity: entry.severity || "unknown",
      source: entry.source || null,
    };
    const value = entry.value.trim().toLowerCase();

    if (entry.type === "sha256") {
      if (!SHA256_RE.test(value)) {
        throw new CatalogError(`${where} is not a SHA-256 (64 hex characters, got ${value.length})`);
      }
      if (!sha256.has(value)) sha256.set(value, meta);
    } else if (entry.type === "domain") {
      if (!DOMAIN_RE.test(value)) throw new CatalogError(`${where} is not a valid domain: "${entry.value}"`);
      if (!domains.has(value)) domains.set(value, meta);
    } else {
      let normalized;
      try {
        normalized = normalizeUrl(entry.value.trim());
      } catch (_) {
        throw new CatalogError(`${where} is not a valid URL: "${entry.value}"`);
      }
      if (!urls.has(normalized)) urls.set(normalized, meta);
    }
  });

  bulkHashes.forEach(({ value, line }) => {
    if (!SHA256_RE.test(value)) {
      throw new CatalogError(`hash list line ${line} is not a SHA-256 (64 hex characters, got ${value.length})`);
    }
    if (!sha256.has(value)) {
      sha256.set(value, { type: "sha256", name: "Known-Malicious-Hash", severity: "unknown", source: "bulk hash list" });
    }
  });

  return {
    size: { sha256: sha256.size, domain: domains.size, url: urls.size },

    /** @returns {object|null} the matching entry's metadata, or null */
    matchHash(hash) {
      return sha256.get(String(hash).toLowerCase()) || null;
    },

    /** @returns {object|null} exact-URL match first, then host / parent domains */
    matchUrl(input) {
      let u;
      try {
        u = new URL(input);
      } catch (_) {
        return null;
      }
      const exact = urls.get(normalizeUrl(input));
      if (exact) return exact;
      const labels = u.hostname.toLowerCase().replace(/\.$/, "").split(".");
      for (let i = 0; i < labels.length - 1; i += 1) {
        const hit = domains.get(labels.slice(i).join("."));
        if (hit) return hit;
      }
      return null;
    },
  };
}

function parseHashList(text) {
  const out = [];
  text.split(/\r?\n/).forEach((raw, i) => {
    const value = raw.trim().toLowerCase();
    if (!value || value.startsWith("#")) return;
    out.push({ value, line: i + 1 });
  });
  return out;
}

function loadCatalog(catalogPath = config.signatureCatalogPath, hashlistPath = config.signatureHashlistPath) {
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
  } catch (err) {
    throw new CatalogError(`Could not read signature catalog at ${catalogPath}: ${err.message}`);
  }
  if (!parsed || !Array.isArray(parsed.entries)) {
    throw new CatalogError(`Signature catalog at ${catalogPath} has no "entries" array`);
  }
  let bulk = [];
  if (hashlistPath) {
    try {
      bulk = parseHashList(fs.readFileSync(hashlistPath, "utf8"));
    } catch (err) {
      throw new CatalogError(`Could not read hash list at ${hashlistPath}: ${err.message}`);
    }
  }
  return buildCatalog(parsed.entries, bulk);
}

let cached = null;
/** The process-wide catalog, loaded on first use. */
function getCatalog() {
  if (!cached) cached = loadCatalog();
  return cached;
}

module.exports = { getCatalog, loadCatalog, buildCatalog, parseHashList, normalizeUrl, CatalogError };
