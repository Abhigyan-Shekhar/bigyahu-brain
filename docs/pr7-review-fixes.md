# PR #7 review fixes

The five concrete review findings are addressed without changing the catalog
authority, retrieval architecture or approval boundary.

| Finding | Result |
| --- | --- |
| Symbol names hidden by a populated path | The graph filter checks path, qualified name, title, name and UID independently. |
| Generic semantic relationship labels | Native graph edges retain stored type plus extracted relation, quote, confidence and source UID. The explorer renders the relation and offers clickable details and a relationship picker. |
| Missing document source paths | Selected Documents bring bounded SUPPORTS Source neighbors into the main graph. Root, neighbor and edge caps report truncation. |
| Passing tests imply a demonstrated fix | Reports distinguish `tests_passed` from `regression_demonstrated`; only matched original assertion failures resolved by the patch support new coding lessons. Passing baselines remain explicitly unverified. |
| Order-sensitive citation graph comparison | Native graphs sort nodes and edges; verification compares canonical structures, tolerating reordered equivalent legacy snapshots while rejecting changed metadata. |

## Verification — October 17, 2026

- Full isolated live FalkorDBLite/Graphify/memory/application suite: **361 passed**,
  zero failed or skipped; three upstream deprecation warnings.
- Targeted review and Personal Brain coverage: **20 passed**. Negative regression
  cases include passing baselines, timeouts, runner exits, error summaries, command
  mismatch and changed case counts. Positive unittest and pytest cases are covered.
- Ruff lint and changed Python formatting checks pass; production React build
  passes with the existing upstream React Flow module directive warning.
- Browser verification used the existing indexed synthetic fixture with actual
  semantic ingestion results: **30 nodes / 27 relationships**, including Source
  nodes and SUPPORTS paths. `delay_ms` finds the symbol despite its `retry.py` path.
  Selecting **Retry Service → IMPLEMENTS → Backoff Policy** shows stored type
  EXTRACTED_RELATION, INFERRED confidence, the literal policy quote and Source UID.
  The existing approved five-test coding report shows baseline failures resolved.
  Its saved code citation opens with checked original bytes and a native CONTAINS
  path; the live regression also covers citation-click ordering and changed digests.

Historical real-agent reports keep their original implementation hashes. This
review pass verifies current backend contracts and the current browser interface;
it does not claim a new complete model-driven coding trial.

The regression flag is command-level evidence, not independent proof of bug
relevance or general correctness. Semantic extracted entities still do not
automatically resolve to arbitrary code symbols/history. Bounded graph views
remain prototype-scale and extracted relationships remain advisory.
