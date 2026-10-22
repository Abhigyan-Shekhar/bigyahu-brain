import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";

test("documentation preview renders cited text and code without evaluating source HTML", async () => {
  const server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)), configFile: false,
    optimizeDeps: { noDiscovery: true, include: [], entries: [] },
    server: { middlewareMode: true, ws: false, hmr: false }, appType: "custom",
  });
  try {
    const { default: Preview } = await server.ssrLoadModule("/src/MarkdownPreview.jsx");
    const id = "a".repeat(24);
    const markdown = `# Queue recovery\n\n## Observed behavior\n\nA job is in memory. [^source-${id}]\n\n<script>alert('source')</script>\n\n\x60\x60\x60json\n{"tests_passed":false}\n\x60\x60\x60\n`;
    const html = renderToStaticMarkup(React.createElement(Preview, { markdown, onEvidence() {} }));
    assert.match(html, /<h2>Queue recovery<\/h2>/);
    assert.match(html, /Source aaaaaa/);
    assert.match(html, /&lt;script&gt;/);
    assert.doesNotMatch(html, /<script/);
    assert.match(html, /<pre>/);
    assert.match(html, /tests_passed/);
  } finally { await server.close(); }
});
