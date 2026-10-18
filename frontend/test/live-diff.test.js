import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

test("live diff shows actual additions/deletions and distinguishes agent explanation from approved rationale", async () => {
  const server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)),
    configFile: false,
    optimizeDeps: { noDiscovery: true, include: [], entries: [] },
    server: { middlewareMode: true, hmr: false },
    appType: "custom",
  });
  try {
    const { default: LiveDiff, diffRows } =
      await server.ssrLoadModule("/src/LiveDiff.jsx");
    const patch =
      "--- a/service.py\n+++ b/service.py\n@@ -1,2 +1,2 @@\n old\n-shell=True\n+shell=False\n";
    const rows = diffRows(patch);
    assert.deepEqual(
      rows.find((row) => row.kind === "removed"),
      { text: "-shell=True", kind: "removed", oldLine: 2 },
    );
    assert.deepEqual(
      rows.find((row) => row.kind === "added"),
      { text: "+shell=False", kind: "added", newLine: 2 },
    );
    const action = {
      status: "running",
      activity_phase: "editing",
      plan: {
        files: ["service.py", "test_service.py"],
        summary: "Preserve signatures",
        steps: [],
      },
      live_changes: {
        files: [
          {
            path: "service.py",
            diff: patch,
            explanation: "Avoid <script> execution",
            additions: 1,
            deletions: 1,
          },
        ],
      },
    };
    const render = () =>
      renderToStaticMarkup(React.createElement(LiveDiff, { action }));
    const html = render();
    assert.match(html, /Agent explanation/);
    assert.match(html, /Approved plan rationale/);
    assert.match(html, /diff-added/);
    assert.match(html, /diff-removed/);
    assert.match(html, /Pending/);
    assert.match(html, /provisional/);
    assert.ok(!html.includes("<script>"));
    action.live_changes.files = [];
    const waiting = render();
    assert.match(waiting, /Waiting for the first successful write/);
    assert.doesNotMatch(waiting, /diff-added|diff-removed/);
  } finally {
    await server.close();
  }
});
