import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { fileURLToPath } from "node:url";
test("finding alerts sort severity, retain citations, escape source text and hide unfinished findings", async () => {
  const server = await createServer({
    root: fileURLToPath(new URL("../", import.meta.url)),
    configFile: false,
    optimizeDeps: { noDiscovery: true, include: [], entries: [] },
    server: { middlewareMode: true, ws: false, hmr: false },
    appType: "custom",
  });
  try {
    const { default: FindingAlerts } = await server.ssrLoadModule(
      "/src/FindingAlerts.jsx",
    );
    const claim = (severity) => ({
      text: "Impact explained",
      support: [{ evidence_id: "proof", title: "unsafe.py:10" }],
      finding: {
        severity,
        title: `${severity} <script>`,
        category: "security",
        location: { path: "unsafe.py", line: 10 },
        recommendation: "Use safe APIs",
      },
    });
    const render = (turn) =>
      renderToStaticMarkup(
        React.createElement(FindingAlerts, {
          turn,
          onEvidence: () => {},
          onPlan: () => {},
        }),
      );
    assert.equal(render({ status: "running", claims: [claim("high")] }), "");
    const html = render({
      status: "complete",
      claims: [claim("low"), claim("critical")],
    });
    assert.ok(html.indexOf("severity-critical") < html.indexOf("severity-low"));
    assert.match(html, /role="alert"/);
    assert.match(html, /unsafe.py:10/);
    assert.equal((html.match(/Review fix workflow/g) || []).length, 1);
    assert.match(html, /Filter findings by severity/);
    assert.match(html, /aria-pressed="true"/);
    assert.ok(!html.includes("<script>"));
    assert.equal(
      render({
        status: "complete",
        claims: [{ text: "Ordinary explanation" }],
      }),
      "",
    );
  } finally {
    await server.close();
  }
});
