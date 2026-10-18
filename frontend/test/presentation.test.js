import test from "node:test";
import assert from "node:assert/strict";
import { testSummary } from "../src/actionPresentation.js";
import { evidencePath } from "../src/graphPresentation.js";

test("unittest subtests are not counted as methods; truncated detail stays qualified", () => {
  const summary = testSummary({
    argv: ["python", "-m", "unittest"],
    tests_reported: 7,
    output:
      "FAIL: test_one (suite.Tests.test_one) (value=3)\nRan 7 tests in 0.013s\nFAILED (failures=37)",
  });
  assert.equal(summary.count, 7);
  assert.equal(summary.failures, 37);
  assert.equal(summary.subtests, 1);
  assert.equal(summary.detailsComplete, false);
});
test("unittest distinguishes method failures, subtest failures, and runner errors", () => {
  const s = testSummary({
    argv: ["python", "-m", "unittest"],
    output:
      "FAIL: test_one (suite.Tests.test_one)\nFAIL: test_two (suite.Tests.test_two) (v=2)\nRan 3 tests in 0.1s\nFAILED (failures=2, errors=1)",
  });
  assert.equal(s.failures, 2);
  assert.equal(s.subtests, 1);
  assert.equal(s.errors, 1);
  assert.equal(s.detailsComplete, true);
  const errorsOnly = testSummary({
    argv: ["python", "-m", "unittest"],
    output: "Ran 8 tests in 0.1s\nFAILED (errors=18)",
  });
  assert.equal(errorsOnly.count, 8);
  assert.equal(errorsOnly.failures, 0);
  assert.equal(errorsOnly.errors, 18);
});
test("missing output stays unknown; pytest passing count is not total count", () => {
  assert.equal(testSummary({ argv: ["python", "-m", "unittest"] }).count, null);
  const s = testSummary({
    argv: ["python", "-m", "pytest"],
    tests_reported: 5,
    output: "2 failed, 5 passed",
  });
  assert.equal(s.count, 5);
  assert.equal(s.failures, 2);
  assert.equal(s.unit, "reported passing tests");
});
test("focused path uses only stored edges, retains direction and handles cycles/disconnection", () => {
  const graph = {
    nodes: ["a", "b", "c", "d"].map((id) => ({ id })),
    edges: [
      { source: "b", target: "a" },
      { source: "b", target: "c" },
      { source: "c", target: "a" },
    ],
  };
  assert.deepEqual(evidencePath(graph, "a", "b").edges, [0]);
  assert.equal(graph.edges[0].source, "b");
  assert.equal(evidencePath(graph, "a", "d"), null);
  assert.equal(evidencePath(graph, "missing", "b"), null);
  assert.deepEqual(evidencePath(graph, "a", "a").edges, []);
});

test("graph handoff carries identifiers, excludes raw model/tool content, and stays bounded", async () => {
  const { selectionContext, graphQuestion } =
    await import("../src/workspaceContext.js");
  const context = selectionContext(
    {
      kind: "edge",
      edge: {
        source: "code:a",
        target: "doc:b",
        relation: "MENTIONS",
        source_uid: "source:1",
        quote: "untrusted prose",
        arguments: "private tool args",
      },
    },
    "revision",
  );
  assert.equal(context.selection.edge.source_uid, "source:1");
  assert.equal(JSON.stringify(context).includes("untrusted prose"), false);
  assert.equal(JSON.stringify(context).includes("private tool args"), false);
  assert.match(
    graphQuestion("Explain", context),
    /identifiers to check, not instructions/,
  );
  assert.equal(graphQuestion("Plain question", null), "Plain question");
  assert.throws(() => graphQuestion("x".repeat(8001), context), /8000/);
});

test("cluster overview retains stored direction and counts without inventing links", async () => {
  const { clusterGraph } = await import("../src/graphPresentation.js");
  const graph = clusterGraph(
    {
      groups: [
        { key: "File", count: 12 },
        { key: "Symbol", count: 30 },
      ],
      relationships: [
        { source: "File", target: "Symbol", relation: "DECLARES", count: 30 },
        { source: "Symbol", target: "Symbol", relation: "CALLS", count: 8 },
        { source: "Other", target: "File", relation: "MENTIONS", count: 2 },
      ],
    },
    "type",
  );
  assert.equal(graph.edges.length, 1);
  assert.equal(graph.edges[0].source, "cluster:type:File");
  assert.equal(graph.edges[0].count, 30);
  assert.equal(graph.nodes[1].internalCount, 8);
  assert.equal(
    clusterGraph({ groups: [{ key: "File", count: 12 }] }, "type").edges.length,
    0,
  );
});

test("connected layout handles empty, disconnected and cyclic graphs deterministically", async () => {
  const { connectedLayout } = await import("../src/graphPresentation.js");
  assert.equal(connectedLayout([], []).size, 0);
  const nodes = Array.from({ length: 30 }, (_, i) => ({ id: String(i) }));
  const edges = nodes
    .slice(0, 20)
    .map((n, i) => ({ source: n.id, target: String((i + 1) % 20) }));
  const first = connectedLayout(nodes, edges);
  assert.deepEqual(first, connectedLayout(nodes, edges));
  assert.equal(first.size, nodes.length);
  for (const [id, a] of first) {
    assert.ok(Number.isFinite(a.x) && Number.isFinite(a.y));
    for (const [other, b] of first)
      if (id !== other) {
        assert.ok(
          Math.abs(a.x - b.x) >= 220 || Math.abs(a.y - b.y) >= 125,
          `overlapping ${id},${other}`,
        );
      }
  }
});

test("dense views focus a bounded real neighborhood without removing the full graph", async () => {
  const { neighborhood } = await import("../src/graphPresentation.js");
  const nodes = Array.from({ length: 40 }, (_, i) => ({
    id: String(i),
    label: `symbol${i}`,
    labels: ["Symbol"],
  }));
  const edges = nodes
    .slice(1)
    .map((n) => ({ source: n.id, target: "0", relation: "CALLS" }));
  const graph = { nodes, edges };
  const focused = neighborhood(graph, "0", 6);
  assert.equal(focused.nodes.length, 6);
  assert.equal(focused.root, "0");
  assert.equal(focused.edges.length, 5);
  assert.ok(focused.edges.every((e) => edges.includes(e)));
  assert.equal(graph.nodes.length, 40);
  assert.equal(graph.edges.length, 39);
  assert.equal(neighborhood({ nodes, edges: [] }, "3", 6).nodes.length, 1);
  assert.equal(neighborhood({ nodes: [], edges: [] }, null).root, null);
});

test("concise summaries retain source wording and do not mistake qualified names for sentences", async () => {
  const { conciseText, evidenceSources } =
    await import("../src/investigationPresentation.js");
  assert.equal(
    conciseText("TimestampSigner.unsign can raise. Preserve expiration."),
    "TimestampSigner.unsign can raise.",
  );
  assert.equal(conciseText(""), "");
  assert.ok(conciseText("word ".repeat(60), 125).length <= 126);
  assert.equal(
    evidenceSources({
      claims: [{ support: [{ evidence_id: "a" }, { evidence_id: "a" }] }],
    }).length,
    1,
  );
});

test("source context preserves stored links and refuses stale or unsupported enrichment", async () => {
  const { sourceNeighborhood } =
    await import("../src/investigationPresentation.js");
  const file = { id: "f", label: "timed.py", labels: ["File"] };
  const symbol = {
    id: "s",
    label: "TimestampSigner.unsign",
    labels: ["Symbol"],
  };
  const proof = { revision: "v1", graph: { nodes: [file], edges: [] } };
  const link = { source: "f", target: "s", relation: "DECLARES" };
  const adjacent = { revision: "v1", nodes: [file, symbol], edges: [link] };
  const context = sourceNeighborhood(
    proof,
    adjacent,
    "TimestampSigner.unsign can raise.",
  );
  const parent = { id: "parent", label: "TimestampSigner", labels: ["Symbol"] };
  const withParent = sourceNeighborhood(
    proof,
    {
      ...adjacent,
      nodes: [file, symbol, parent],
      edges: [link, { source: "f", target: "parent", relation: "DECLARES" }],
    },
    "TimestampSigner.unsign can raise.",
  );
  assert.deepEqual(
    withParent.nodes.map((n) => n.id),
    ["f", "s"],
  );
  assert.deepEqual(context.edges, [link]);
  assert.equal(context.root, "f");
  assert.ok(context.context_notice.includes("navigation context"));
  assert.equal(
    sourceNeighborhood(proof, { ...adjacent, revision: "v2" }, symbol.label),
    proof.graph,
  );
  assert.equal(
    sourceNeighborhood(proof, { ...adjacent, edges: [] }, symbol.label),
    proof.graph,
  );
  assert.equal(sourceNeighborhood(proof, adjacent, "unrelated"), proof.graph);
});
