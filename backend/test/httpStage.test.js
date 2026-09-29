"use strict";

// Pure node:test + node:http -- no npm packages needed, so this runs even
// before `npm install` (unlike samples.test.js, which needs supertest).

const test = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const { callStage, StageHttpError } = require("../src/stages/httpStage");

function withMockServer(handler, fn) {
  const server = http.createServer(handler);
  return new Promise((resolve, reject) => {
    server.listen(0, async () => {
      const port = server.address().port;
      try {
        await fn(port);
        resolve();
      } catch (err) {
        reject(err);
      } finally {
        server.close();
      }
    });
  });
}

test("callStage resolves with the parsed JSON on a 200 response", async () => {
  await withMockServer(
    (req, res) => {
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ echoed: JSON.parse(body) }));
      });
    },
    async (port) => {
      const result = await callStage(`http://127.0.0.1:${port}/predict`, { a: 1 });
      assert.deepEqual(result, { echoed: { a: 1 } });
    }
  );
});

test("callStage rejects with BAD_STATUS on a non-2xx response", async () => {
  await withMockServer(
    (req, res) => res.writeHead(500) && res.end("nope"),
    async (port) => {
      await assert.rejects(() => callStage(`http://127.0.0.1:${port}/predict`, {}), (err) => {
        assert.ok(err instanceof StageHttpError);
        assert.equal(err.code, "BAD_STATUS");
        return true;
      });
    }
  );
});

test("callStage rejects with BAD_JSON on a non-JSON response body", async () => {
  await withMockServer(
    (req, res) => res.writeHead(200) && res.end("not json"),
    async (port) => {
      await assert.rejects(() => callStage(`http://127.0.0.1:${port}/predict`, {}), (err) => {
        assert.equal(err.code, "BAD_JSON");
        return true;
      });
    }
  );
});

test("callStage rejects with CONNECTION_FAILED when nothing is listening", async () => {
  await assert.rejects(() => callStage("http://127.0.0.1:1/unreachable", {}), (err) => {
    assert.equal(err.code, "CONNECTION_FAILED");
    return true;
  });
});
