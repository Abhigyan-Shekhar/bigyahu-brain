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
