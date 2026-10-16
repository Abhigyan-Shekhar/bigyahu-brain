# Backend merge verification

Verified 2026-10-16 on codex/company-brain-integration. The reviewed integration
commit is the sole original commit above cleaned origin/master; the accompanying
focused fix adds no feature-branch ancestry. Codex agent commits are excluded.
The final commit SHA and its post-commit validation/CI links are recorded in the PR.

## Confirmed retrieval defect and fix

get_context bounded its direct file links and _change_history links separately,
then sliced their concatenation to 20 without checking the final union. A live
graph regression with mixed exact seeds reproduced 21 distinct links returning
20 with status ok and no truncation marker. An overlap case also demonstrated
duplicate links displacing distinct results. These synthetic seeds exercise the
combination boundary, not a claim that normal ingested identifiers collide.

The fix keeps one complete provenance record per work/file pair, orders the
union by work UID and file UID, and marks file_associations in truncated before
the final slice when distinct results exceed 20. The public envelope then reports
incomplete. All five existing MCP tool signatures are unchanged.

Three live regressions cover 21 distinct links, exactly 20 links, and overlapping
routes with 20 distinct links. They check stable repeated ordering and source UID,
confidence, basis, snapshot time, association revision and non-binding semantics.
Before the fix: 2 failed, 1 passed, 7 deselected. After the fix: 3 passed,
0 failed, 0 skipped, 7 deselected.

The combined-set audit also inspected keyword seeds, historical/direct sources,
decision/history evidence, decision excerpts, affected files and ownership.
_change_history already detects its own query overflow; its accumulated sources
pass through bound_excerpts at both public callers. Other combined public sets
already signal their final bounds or fail closed. No additional silent truncation
was demonstrated, so no unrelated retrieval redesign was made.

## Executed verification

The full suite runs with BRAIN_INTEGRATION=1, BRAIN_LITE_TESTS=1 and an absolute
BRAIN_TEST_CONFIG selecting a fresh isolated loopback FalkorDBLite owner. Every
verification run creates a new database/configuration; fixtures and the database
owner are cleaned up without touching existing graph or experiment data. The
local environment uses Python 3.12.13, FalkorDBLite 0.10.0, Redis 8.6.2 and graph
module 4.18.3. Other engine versions remain unverified.

| Check | Passed | Failed | Skipped |
| --- | ---: | ---: | ---: |
| Complete pytest suite, live graph and Lite enabled | 120 | 0 | 0 |
| Separately invoked MCP STDIO selection | 4 | 0 | 0 |
| Separately invoked security/relationship selection | 6 | 0 | 0 |

The two selections overlap the full suite; do not add them to claim 130 unique
tests. Each invocation emits two existing Authlib deprecation warnings.

The separate STDIO selection consists of:

- test_process.py: module launch from another cwd and unavailable database.
- test_integration.py: all five tools sharing a real synced database.
- test_integration.py: context delivers source history without Decisions.
- test_graph_intelligence.py: change history over real separate-process STDIO.

The explicit boundary selection covers real org/private isolation and two-hop
callers; approved caller constraints and supersession; atomic rejection of
unrelated-scope approval; injected evidence remaining quoted/non-binding;
snapshot Issue/PR references and untrusted sources; and history poisoning,
foreign-repository/private routing and response budgets.

Ruff passes for src, tests and scripts. Git working/staged/commit diff checks
pass. The publication guard checks both indexed files and every reachable commit
tree; raw research/runtime paths and credential-shaped or machine-specific
content must remain absent. The final branch contains only cleaned master
ancestry, the reviewed integration and this focused fix. Existing non-noreply
metadata already on cleaned master is unchanged; new integration commits use the
approved GitHub noreply author and committer identity.

Commands (use only an isolated disposable database):

```sh
BRAIN_TEST_CONFIG=/absolute/path/to/isolated-test.yaml \
  BRAIN_INTEGRATION=1 BRAIN_LITE_TESTS=1 PYTHONPATH="$PWD/src" \
  .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check src tests scripts
git diff --check
git diff --cached --check
.venv/bin/python scripts/check_publication.py --history
git merge-base --is-ancestor origin/master HEAD
```

Raw execution logs and database state stay outside the tracked tree. The final
verification is repeated after committing, against that exact immutable commit,
and reported in the PR. No subsequent source or documentation edits should be
made without recording a new commit and rerunning the relevant final checks.

## CI and remaining limits

The configured GitHub workflow is Publication boundary: it scans indexed content
and complete reachable history. It does not install dependencies or execute the
Python suite, so a green CI job is not evidence of pytest success. The PR records
the final head's actual CI result separately from local test results.

Static graph coverage remains conservative; missing dependencies stay unknown.
Historical file links, issue mentions and reviewer activity are advisory, not
symbol-level or human-approved constraints. Bounds may return incomplete; no
pagination or arbitrary Cypher tool is introduced. Sync remains single-writer;
there is no hostile-shell/admin isolation guarantee. No baseline coding benefit
has been demonstrated. A human-reviewed real approved constraint and broader
deployment/engine validation remain release concerns, not features added here.

The backend is prepared for review and merge after the final checks pass. The PR
must not be merged without the user's approval. Codex agent integration is the
next, separate step.
