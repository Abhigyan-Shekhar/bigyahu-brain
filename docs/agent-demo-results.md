# Completed graph-aware Codex demonstration — 16 October 2026

**Earlier graph:** this run predates v5 repository document nodes and operator
approval. It cannot demonstrate their effect. Label any replay with this provenance;
use a fresh frozen-v5 run for the final approval → coding sequence.

**One complete coding run passed independent evaluation. No baseline improvement
is claimed.** The final patch is [agent-demo.patch](agent-demo.patch); exact
invocation steps are in [agent-workflow.md](agent-workflow.md).

## Integration

Branch: `codex/graph-aware-demo`, created directly from current `origin/master`
`070dc03`. Selected runner, corpus-preflight, evaluation and local-audit files
were inspected and copied from local `feat/codex-agent`; no feature history was
merged or cherry-picked. Old patches and broad comparison machinery were not
imported. Existing backend source, ingestion, five MCP signatures, dependencies
and CI are unchanged.

The imported evaluator previously printed failed scores but exited successfully.
It now returns nonzero when the oracle or upstream tests fail (or oracle cases
fail despite a zero exit), rejects an oracle inside the coding checkout, and
checks its frozen hash. Five regression tests cover read-only runner settings
and success/failure propagation. Raw traces, configs, database state and private
research remain ignored; only reviewed public metadata and source patches are
included here.

## Frozen inputs

- Backend source: merged `070dc03` throughout both new sessions.
- urllib3 source: `a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`.
- Task: [agent-task.txt](agent-task.txt), unchanged from the existing task.
- Final instructions: [agent-instructions.txt](agent-instructions.txt), explicitly
  requiring org retrieval and `check_change` before edits, without implementation
  hints, prior attempts or oracle feedback.
- Final model requested: `gpt-6.1-sol`, high reasoning. Codex CLI:
  `0.162.0-alpha.17.2`; Python 3.12.13; urllib3's frozen test lockfile.
- FalkorDBLite 0.10.0, Redis 8.6.2, graph module 4.18.3. Existing eligible
  namespace: `experiment:urllib3:5181:eligible`, org scope.
- Corpus: 2,517 nodes, 3,755 edges, 122 source nodes. Exact snapshot SHA-256:
  `b191159016b096ef09d964a5d4526477fb8ab7f0b5e2c526bf8fe5426c221578`.
  Before/intermediate/final snapshots match. No re-ingestion or filtering occurred.
- Independent oracle SHA-256:
  `d077b08c3c911fc146f59305ca305d3f216749e0218727b4e3b3adbabe7ff3d0`.
  The public `docs/demo/oracle.py` is byte-identical to the retained original.

The existing filtered corpus includes merged #3780/#5161 and excludes the
screened #5181/#5191/#5242 solution material. Preflight checks these known
references and work items; it cannot certify every possible semantic leak.
Neither new emitted trace contains those excluded references. The final agent's
36 emitted shell commands inspected only the checkout and its local Git history;
no evaluator or sibling-directory reads were observed. The oracle stayed outside
the coding checkout and ran only after the model exited. These are audited
observations, not proof of filesystem read confinement or hidden reasoning.

## Actual graph-aware workflow

The final session completed in 237.37 seconds. All five completed MCP calls
occurred before the first file edit:

1. `check_change` with intended files and short symbols returned
   `unknown`, `symbol_not_found`. This failure was disclosed.
2. `get_context(scope="org")` retrieved #5161 history and eight source excerpts;
   it reported `incomplete` with excerpt/path truncation.
3. File-only `check_change` returned `incomplete`, `caller_limit_exceeded`.
4. `get_context(scope="org", query="set_file_position")` returned `ok`, nine
   #3780 excerpts, and recorded incoming static CALLS evidence for
   `HTTPConnectionPool.urlopen → set_file_position`.
5. Qualified `check_change` on
   `src/urllib3/poolmanager.py::PoolManager.urlopen` returned the target's
   recursive caller path, honestly labeled **heuristic**, plus #5161 historical
   evidence. It reported `incomplete` for excerpt/ownership bounds and warned
   that missing edges do not prove absence of dependencies. `must_preserve`
   and `review` were empty. Other callers were verified in local code.

See [reviewed MCP metadata](agent-demo-evidence.json) for actual arguments,
source URLs, warnings and caller paths. No new decision was written or approved.
The backend exposes five tools; the model session enabled only the four read-only
ones and disabled `remember`.

The agent explicitly credited [#5161](https://github.com/urllib3/urllib3/pull/5161)
with reinforcing 303 body/framing cleanup and
[#3780](https://github.com/urllib3/urllib3/pull/3780) with rewind-error behavior.
It then independently inspected the corresponding local commits, which already
contain both behaviors. Its core diagnosis—PoolManager loses the original body
position across recursive redirects—came from current code inspection. History
influenced preservation requirements and test coverage; this does not show that
the graph was necessary to discover the fix. Historical discussion was kept
non-binding, and incomplete caller evidence prompted local verification of
ProxyManager and public helpers.

The agent stated a concrete source/test/verification plan before editing. It
first added 54 regressions: **11 failed, 43 passed** before changing production
code. It then changed `PoolManager.urlopen` to capture a position for redirects
without passing a failed-tell marker into the initial request. Only a
body-preserving redirect receives that captured position; the existing 303
state reset remains. It also added same-/cross-host socket regressions.

## Actual outcomes

| Check | Passed | Failed/errors | Skipped | Other |
| --- | ---: | ---: | ---: | --- |
| Company Brain full suite, isolated live Lite + MCP | 125 | 0 | 0 | 2 existing deprecation warnings |
| Agent's new regressions before production fix | 43 | 11 | 0 | Demonstrated bug |
| Agent's final new regressions | 54 | 0 | 0 | Overlaps unit suite |
| Agent's relevant unit suites | 835 | 0 | 7 | PoolManager, util, connectionpool |
| Agent's dummy-server selection in sandbox | 0 | 85 setup errors | 1 | Socket permission failure |
| Independent unchanged socket oracle after exit | 12 | 0 | 0 | Includes 6 bare-pool controls |
| Independent selected upstream tests after exit | 200 | 0 | 0 | 705 deselected |
| Exact sandbox-blocked server selection rerun after exit | 86 | 0 | 0 | Loopback permitted |

Selections overlap; do not add their counts. The 835/7 and failed sandbox counts
are preserved from the agent's emitted commands. Post-exit checks used the task
checkout's own Python, verified the actual imported source path, and evaluated
the unchanged patch. [Reviewed socket outcomes](agent-demo-checks.json) include
both attempts, actual wire observations, exit codes and import verification.
Ruff for `src tests scripts`, diff checks and staged publication/history scanning
passed. The full Company Brain suite includes all five tools over real STDIO.

Final patch SHA-256:
`eb1cde4c7d542094246f4407b9322d36e37c70345c0bb4fbdfb33d0f2494afa0`.
It changes three upstream files: 130 insertions, two deletions. It was authored
by the fresh agent and was not manually repaired before independent evaluation.
Apply it only to the pinned urllib3 revision; this is a demo patch, not an
upstream merge or release.

## Failures and limits retained

The first new attempt requested `gpt-6-luna`, medium reasoning and completed in
44.43 seconds. It retrieved org history once but never called `check_change`.
Its patch passed **132 selected upstream tests** (705 deselected) yet only
**9/12 oracle cases**, including 6/6 bare-pool controls. It prematurely raised
`UnrewindableBodyError` before any initial upload for failed-tell streams,
regressing ordinary and 303 requests. This attempt fails both workflow and
correctness criteria; its raw records and patch remain local.

The second attempt used a fresh clean checkout, explicit impact-tool guidance
and a different model/reasoning setting. It received no first-attempt patch,
trace, diagnosis, or evaluator feedback. These are two development attempts,
not a controlled comparison. Earlier recorded failed and successful runs remain
accurately described in the main README and original demo material.

The passed demonstration meets the intended workflow on the verified Lite engine.
It does not establish causal graph benefit, full dependency coverage, every
urllib3 behavior, another engine version, or a zero-input public graph rebuild.
Reproduction requires the existing eligible database; private runtime state is
not published. No backend redesign, new ingestion, CI work, new framework,
dashboard, baseline campaign, push or master merge was performed.
