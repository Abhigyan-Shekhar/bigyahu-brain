import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

test("activity hero renders recorded operations without fabricating future stages", async () => {
  const server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)),
    configFile: false,
    optimizeDeps: { noDiscovery: true, include: [], entries: [] },
    server: { middlewareMode: true },
    appType: "custom",
  });
  try {
    const { default: ActivityStream } = await server.ssrLoadModule(
      "/src/ActivityStream.jsx",
    );
    const render = (turn) =>
      renderToStaticMarkup(React.createElement(ActivityStream, { turn }));
    const waiting = render({
      status: "running",
      stage: "Preparing evidence",
      progress: { completed_tools: [], completed_count: 0, current_tool: null },
    });
    assert.match(waiting, /Waiting for the next recorded tool event/);
    assert.doesNotMatch(
      waiting,
      /Searching repository history|Tracing graph relationships|\d+%/,
    );
    const working = render({
      status: "running",
      stage: "Gathering source evidence",
      progress: {
        completed_tools: [{ tool: "read_code", status: "completed" }],
        completed_count: 1,
        current_tool: "search_history",
        elapsed_seconds: 9,
      },
    });
    assert.match(working, /Searching repository history/);
    assert.match(working, /Inspecting source code/);
    assert.doesNotMatch(
      working,
      /Tracing graph relationships|Producing a plan|\d+%/,
    );
    const recorded = render({
      status: "complete",
      stage: "Investigation complete",
      progress: {
        completed_tools: [{ tool: "read_code", status: "unverified" }],
        completed_count: 1,
        current_tool: null,
      },
    });
    assert.match(recorded, /RECORDED INVESTIGATION/);
    assert.doesNotMatch(recorded, /AGENT IS WORKING/);
  } finally {
    await server.close();
  }
});
