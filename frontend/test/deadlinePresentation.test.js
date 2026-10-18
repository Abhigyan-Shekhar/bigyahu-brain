import test from "node:test";
import assert from "node:assert/strict";
import { deadlineGroup } from "../src/deadlinePresentation.js";

test("deadline filters preserve undated and completed work without false overdue flags", () => {
  const now = Date.parse("2026-10-18T12:00:00Z");
  assert.equal(deadlineGroup({ due_at: null }, now), "undated");
  assert.equal(deadlineGroup({ due_at: "broken" }, now), "undated");
  assert.equal(deadlineGroup({ due_at: "2026-10-18T11:00:00Z", status: "open" }, now), "overdue");
  assert.equal(deadlineGroup({ due_at: "2026-10-18T18:00:00+05:30", status: "open" }, now), "upcoming");
  for (const status of ["closed", "merged", "closed_unmerged"]) {
    assert.equal(deadlineGroup({ due_at: "2026-10-01", status }, now), "completed");
  }
});

test("timeline positions follow actual deadlines with stable equal-date ordering", async () => {
  const { deadlineLayout } = await import("../src/deadlinePresentation.js");
  const now = Date.parse("2026-10-18T00:00:00Z");
  const layout = deadlineLayout([
    { uid: "c", due_at: null }, { uid: "b", due_at: "2026-10-20T00:00:00Z" },
    { uid: "a", due_at: "2026-10-18T00:00:00Z" },
  ], now);
  assert.deepEqual(layout.dated.map(({ item }) => item.uid), ["a", "b"]);
  assert.ok(layout.dated[0].fraction < layout.dated[1].fraction);
  assert.equal(layout.undated[0].uid, "c");
  assert.equal(layout.nowFraction, layout.dated[0].fraction);
  assert.equal(deadlineLayout([], now).nowFraction, null);
  assert.equal(deadlineLayout([{ uid: "z", due_at: "2020-01-01" }], now).nowFraction, null);
});
