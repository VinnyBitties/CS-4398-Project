"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { buildCatalog, loadCatalog, parseHashList, CatalogError } = require("../src/signatures/catalog");

const HASH = "a".repeat(64);

test("the committed catalog loads and every entry is well-formed", () => {
  const catalog = loadCatalog();
  assert.ok(catalog.size.sha256 >= 1);
  assert.ok(catalog.matchHash("275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f"));
});

test("matchHash is case-insensitive and returns the entry's metadata", () => {
  const catalog = buildCatalog([{ type: "sha256", value: HASH, name: "Test", severity: "high" }]);
  assert.deepEqual(catalog.matchHash(HASH.toUpperCase()), { type: "sha256", name: "Test", severity: "high", source: null });
  assert.equal(catalog.matchHash("b".repeat(64)), null);
});

test("a truncated hash is rejected at load instead of silently never matching", () => {
  assert.throws(
    () => buildCatalog([{ type: "sha256", value: HASH.slice(0, 63), name: "Truncated" }]),
    (err) => err instanceof CatalogError && /entry #1/.test(err.message) && /got 63/.test(err.message)
  );
});

test("unknown types and missing fields are rejected", () => {
  assert.throws(() => buildCatalog([{ type: "md5", value: "x", name: "n" }]), CatalogError);
  assert.throws(() => buildCatalog([{ type: "sha256", value: HASH }]), CatalogError);
  assert.throws(() => buildCatalog([{ type: "domain", value: "not a domain", name: "n" }]), CatalogError);
});

test("a domain entry matches the host and its subdomains, but not lookalikes", () => {
  const catalog = buildCatalog([{ type: "domain", value: "bad.example", name: "Bad" }]);
  assert.ok(catalog.matchUrl("https://bad.example/x"));
  assert.ok(catalog.matchUrl("http://cdn.BAD.example:8080/x?y=1"));
  assert.equal(catalog.matchUrl("https://notbad.example/"), null);
  assert.equal(catalog.matchUrl("https://bad.example.com/"), null);
  assert.equal(catalog.matchUrl("https://example/"), null);
  assert.equal(catalog.matchUrl("nonsense"), null);
});

test("a url entry matches only that exact URL, ignoring the fragment", () => {
  const catalog = buildCatalog([{ type: "url", value: "https://site.example/payload.exe", name: "Payload" }]);
  assert.ok(catalog.matchUrl("https://site.example/payload.exe#top"));
  assert.equal(catalog.matchUrl("https://site.example/other.exe"), null);
});

test("a bulk hash list is parsed, skipping comments and blank lines", () => {
  const bulk = parseHashList(`# feed header\n\n${HASH}\r\n  ${"B".repeat(64)}  \n`);
  assert.deepEqual(bulk.map((b) => b.line), [3, 4]);
  const catalog = buildCatalog([], bulk);
  assert.equal(catalog.size.sha256, 2);
  assert.equal(catalog.matchHash("b".repeat(64)).source, "bulk hash list");
  assert.throws(() => buildCatalog([], parseHashList("deadbeef")), /line 1/);
});
