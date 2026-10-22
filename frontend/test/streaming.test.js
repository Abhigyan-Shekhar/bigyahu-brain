import test from "node:test";
import assert from "node:assert/strict";
import { consumeSnapshots, watchResource } from "../src/api.js";
const responseFor = (text, size = 1) => {
  const bytes = new TextEncoder().encode(text);
  let offset = 0;
  return new Response(
    new ReadableStream({
      pull(controller) {
        if (offset === bytes.length) return controller.close();
        controller.enqueue(bytes.slice(offset, (offset += size)));
      },
    }),
    { headers: { "Content-Type": "text/event-stream" } },
  );
};
test("SSE handles split UTF-8, CRLF frames, comments and multiple snapshots", async () => {
  const values = [];
  await consumeSnapshots(
    responseFor(
      ': heartbeat\r\n\r\nevent: snapshot\r\ndata: {"stage":"检查"}\r\n\r\nevent: snapshot\ndata: {"status":"complete"}\n\n',
    ),
    (v) => values.push(v),
  );
  assert.deepEqual(values, [{ stage: "检查" }, { status: "complete" }]);
});
test("incomplete snapshots are rejected instead of published", async () => {
  await assert.rejects(
    consumeSnapshots(responseFor('event: snapshot\ndata: {"status":'), () =>
      assert.fail(),
    ),
    /incomplete/,
  );
});
test("watch authenticates in headers, falls back after interruption, and stops at completion", async () => {
  const oldFetch = globalThis.fetch,
    oldStorage = globalThis.sessionStorage;
  const calls = [];
  globalThis.sessionStorage = { getItem: () => "private-token" };
  globalThis.fetch = async (url, options) => {
    calls.push([url, options]);
    if (url.endsWith("events")) throw Error("connection lost");
    return new Response(JSON.stringify({ status: "complete", claims: [] }));
  };
  let stop;
  try {
    const value = await new Promise((resolve, reject) => {
      stop = watchResource("/turns/abc/events", "/turns/abc", resolve, reject);
    });
    assert.equal(value.status, "complete");
    assert.equal(calls.length, 2);
    assert.equal(calls[0][1].headers.Authorization, "Bearer private-token");
    assert.ok(!calls[0][0].includes("private-token"));
  } finally {
    stop?.();
    globalThis.fetch = oldFetch;
    globalThis.sessionStorage = oldStorage;
  }
});

test("oversized complete and fragmented events are rejected before publication", async () => {
  const event = `event: snapshot\ndata: ${JSON.stringify({ text: "x".repeat(4_000_000) })}\n\n`;
  for (const size of [event.length, 1_000_000]) {
    await assert.rejects(
      consumeSnapshots(responseFor(event, size), () => assert.fail("Oversized snapshot published")),
      /exceeds size limit/,
    );
  }
});

test("size limit applies to each event rather than the combined network chunk", async () => {
  const value = { text: "x".repeat(2_000_000) };
  const event = `event: snapshot\ndata: ${JSON.stringify(value)}\n\n`;
  const values = [];
  await consumeSnapshots(responseFor(event.repeat(3), event.length * 3), (v) => values.push(v));
  assert.deepEqual(values, [value, value, value]);
});
