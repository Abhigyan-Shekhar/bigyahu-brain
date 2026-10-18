# Demo usability follow-up — 18 October 2026

The stopped recorded attempt was action `5e6817101abf4fbbb3f41bc43f1b2be2`.
The planner returned `tests/test_timed_validation.py (new)` as a filename; the
existing file-scope validator rejected its suffix. It was not an observed model
outage. The later attempt used literal filenames and diagnostic exception
assertions, as preserved in the live demo receipt. No execution was approved for
the stopped attempt.

## Changes

- Explain invalid literal paths and explicitly prohibit annotations in planner
  paths. The failed card retains the reason and offers **Review objective and
  retry**, with the original objective prefilled and fresh approval required.
  Model timeouts have a distinct message; generic exceptions retain a bounded
  safe message rather than exposing arbitrary diagnostics.
- Show unittest methods/cases, assertion failure totals, runner errors and
  available subtest failure details separately. The recorded log retains 13
  subtest failure headers, while its final summary reports 37 assertion failures
  across seven methods/cases. Missing headers are not reconstructed or counted
  as method failures. Pytest counts remain explicitly reported passing tests.
  This presentation does not change the conservative verification gate.
- Show completed results first, with the evidence-to-action summary visible by
  default, including Company, Personal and Team contributions when present.
  Memory remains advisory. Keep patch download in the card header; collapse
  transcripts and the diff. Add native modal focused review with Escape, focus
  trapping and focus restoration; opening a citation returns to the inspector.
  Reduce the persistent composer to one initial line in an active conversation.
- Move graph selectors out of the canvas into a wrapping toolbar. Select two
  nodes to show their shortest recorded connection and hide unrelated nodes.
  Traversal can cross an edge in either direction, but arrows retain the stored
  direction. Disconnected loaded slices report no path. This is navigation, not
  proof of causality or completeness across the whole graph.
- Project allowlisted tool names and completion statuses from existing traces,
  and timestamp planning/execution phases. Report real stages for original
  tests, patched tests and fresh-base patch replay. Never return tool arguments,
  outputs, model prose or hidden reasoning. Old jobs without timestamps say
  elapsed time is unavailable. Polling reads at most 2 MB and labels bounded
  traces; it shows the last 12 observed completion events.

## Verification

- Isolated live graph/memory/application suite: **409 passed**, zero skipped,
  three existing dependency deprecation warnings.
- Final focused action/progress/relevance suite: **48 passed**.
- Frontend summary/path tests: **4 passed**, also added to application-client CI.
- Frontend production build and Ruff passed. `git diff --check` passed.
- Real browser inspection of the retained completed action confirmed the seven
  methods/cases, 37 assertion failures, at least 13 retained subtest failures,
  advisory memory summary, header patch download, focused dialog and Escape
  focus restoration. No new editing action or approval was performed.
- Browser path selection reduced the 100-node loaded graph to the actual two-node
  `base64_decode → CALLS → want_bytes` path. Toolbar remained outside the canvas.
- Earlier independent downloaded-patch verification remains **4/16 → 16/16**
  reproduction cases and **297 → 304** passing upstream tests. It is separate
  from the automatic gate and is preserved in the existing live receipt.
- GitHub push and PR runs for `601269a` passed Windows, macOS, Ubuntu, Docker,
  frontend and publication jobs; security checks passed. New follow-up source
  requires its own CI run on the PR.

Screenshots and raw traces remain local and ignored. Browser checks used the
existing synthetic demo workspace; mobile sizes and a fresh paid model/editor
journey were not exercised for this UI follow-up. The checks above are not a new
comparative benchmark or evidence of graph performance advantage.


## Private graph visibility follow-up

The Personal Brain graph mounted inside a collapsed details element. React Flow
initially fitted a zero-size viewport and could retain its minimum zoom, leaving
loaded nodes outside the visible canvas. The shared viewer now observes real
canvas dimensions and refits when it becomes visible. Normal page wheel scrolling
no longer zooms graphs out; explicit zoom controls and pinch zoom remain available.
Static memory graphs use a three-column layout and a taller canvas instead of
spreading each node kind into a separate distant column.

Browser verification used the existing private graph: 12 nodes visible on first
expansion and after collapse/reopen, stable zoom during page scrolling, and the
recorded MENTIONS relationship inspectable. Build and four frontend checks passed.
This repairs rendering; existing unresolved-company-reference warnings remain
visible and are not a claim that all memory source links resolve.
