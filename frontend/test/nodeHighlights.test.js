import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

test("node highlights render decision evidence and qualified live scope", async () => {
  const server = await createServer({ root: fileURLToPath(new URL("../", import.meta.url)), configFile: false,
    optimizeDeps: { noDiscovery: true, include: [], entries: [] },
    server: { middlewareMode: true, hmr: false }, appType: "custom" });
  try {
    const { default: Inspector } = await server.ssrLoadModule("/src/GraphInspector.jsx");
    const html = renderToStaticMarkup(React.createElement(Inspector, {
      selection: { kind: "node", node: { id: "file", labels: ["File"], label: "a.py" } },
      detail: { highlights: {
        metadata: {}, last_commit: { uid: "commit", author: "A", timestamp: "2026-10-18T00:00:00Z" },
        live: [{ id: "run", stage: "Editing" }], live_notice: "Human presence unavailable.",
        work: { items: [{ uid: "pr", kind: "PR", title: "Test", url: "javascript:alert(1)",
          decisions: [{ uid: "decision", source_uid: "source", text: "<script>source</script>", status: "proposed" }] }] },
      } }, onNode() {}, onClose() {}, onExplain() {}, onFocus() {}, onExpand() {},
    }));
    assert.match(html, /Last modified by: A/);
    assert.match(html, /planned file scope/);
    assert.match(html, /Inspect decision source/);
    assert.match(html, /proposed/);
    assert.match(html, /&lt;script&gt;/);
    assert.doesNotMatch(html, /href="javascript:/);
    const { default: Deadlines } = await server.ssrLoadModule("/src/DeadlinePanel.jsx");
    const panel = renderToStaticMarkup(React.createElement(Deadlines, { project: "test" }));
    for (const label of ["Upcoming", "Overdue", "No deadline"]) assert.ok(panel.includes(label));
  } finally { await server.close(); }
});
