import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

test("resume is offered only for a recoverable editing timeout and never accepts a partial patch", async () => {
  const server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)), configFile: false,
    optimizeDeps: { noDiscovery: true, include: [], entries: [] },
    server: { middlewareMode: true, ws: false, hmr: false }, appType: "custom",
  });
  try {
    const { default: Recovery } = await server.ssrLoadModule("/src/ExecutionRecovery.jsx");
    const action = { status: "failed", phase: "execution", failure_kind: "editor_timeout", recovery: { available: true } };
    const render = (overrides = {}, submitting = false) => renderToStaticMarkup(
      React.createElement(Recovery, { action: {...action, ...overrides}, submitting, onResume() {} })
    );
    assert.match(render(), /Resume editing/);
    assert.match(render(), /does not accept the partial patch as complete/);
    assert.match(render({}, true), /disabled/);
    for (const overrides of [{status: "complete"}, {status: "running"}, {phase: "planning"},
                             {failure_kind: "execution_timeout"}, {recovery: {available: false}}]) {
      assert.equal(render(overrides), "");
    }
  } finally { await server.close(); }
});
