# Frozen-v5 baseline versus graph evaluation — 16 October 2026

**No correctness advantage was observed.** Baseline and Company Brain each
succeeded in **3/3 fresh sessions**, all passing **12/12** independent socket
oracle cases and the selected upstream suite. At three sessions per condition,
these results and timing differences are anecdotal. This is a local measured
comparison, not a claim of significance or general coding improvement.

## Exact results

| Order | Session | Oracle | Upstream passed | Seconds | Company Brain calls | Approved D-2 before first edit |
| --- | --- | --- | --- | ---: | ---: | --- |
| 1 | [baseline-1](v5-trials/baseline-1.patch) | 12/12 | 188 | 167.161 | 0 | No graph tools |
| 2 | [graph-1](v5-trials/graph-1.patch) | 12/12 | 210 | 241.960 | 4 | No |
| 3 | [graph-2](v5-trials/graph-2.patch) | 12/12 | 225 | 231.753 | 5 | Yes |
| 4 | [baseline-2](v5-trials/baseline-2.patch) | 12/12 | 156 | 149.254 | 0 | No graph tools |
| 5 | [baseline-3](v5-trials/baseline-3.patch) | 12/12 | 164 | 136.675 | 0 | No graph tools |
| 6 | [graph-3](v5-trials/graph-3.patch) | 12/12 | 178 | 148.936 | 3 | Yes |

No session was omitted, retried or repaired. All six exited successfully; there
were no usage-limited or timed-out sessions in this batch. Independent upstream
checks reported zero failures/errors/skips. Counts differ because the same fixed
selector also includes each agent's new regression tests. The patch audit found
changes only in PoolManager and its two test files; removed lines were import
updates, with no existing test bodies/assertions removed and no new skip markers.

Baseline-2/3 made two built-in MCP resource-discovery calls each, receiving empty
lists. They had no Company Brain tools or organizational results. These empty
discovery calls are preserved separately from Company Brain calls in the data.

Median session time was 149.254 seconds for baseline and 231.753 seconds for
graph. Time includes model work, shell commands and tools, excludes setup and
independent evaluation, and is not a measured per-tool latency or general speed
claim. Cache effects and small sample size limit interpretation.

## Frozen inputs and controls

- urllib3 pin: `a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`.
- Corpus SHA-256: `b16fc995c9d4429a54c20601ae471bbc7a789d61a1256184068aa30c5ef688f6`.
  Contains 2,877 nodes and 3,904 edges, including 179 Document sections,
  independently approved D-2 and superseded D-1. Hash matched before and after
  **every** trial. No sync, approval or source mutation occurred during trials.
- Same requested `gpt-6.1-sol`, high reasoning, 900-second limit, Codex CLI
  `0.162.0-alpha.17.2`, Python 3.12.13 and identical locked dependency inventories.
  Requested model identity is recorded, not independently attested.
- Same task/common instructions and fresh ephemeral sessions. Prompt SHA-256:
  `c9ab628a07cb29aed845fd8bfcd03eaeccfa016361bf30c68663d93f5dd69e6c`.
  Normalized CLI arguments match after removing the graph MCP configuration and
  substituting fresh checkout/output paths. Apps/plugins/web/project documents
  were disabled; graph sessions enabled only the four read-only tools.
- Eligible public snapshots contain #3780/#5161. Screened #5181/#5191/#5242
  source material, prior patches and oracle outputs were not supplied to models.
  Existing adjacent 303 tests remained visible to both arms.
- The fixed oracle remained outside each checkout and ran only after the agent
  exited. Oracle SHA-256:
  `d077b08c3c911fc146f59305ca305d3f216749e0218727b4e3b3adbabe7ff3d0`.
  Upstream counts are from pytest JUnit XML. Emitted-command audit found no
  screened external/evaluator reads; this is not proof of read confinement.

The [criteria were committed before trials](v5-evaluation-protocol.md).
The [machine-readable results](v5-evaluation.json) include each oracle scenario,
patch/trace/evaluator artifact hashes, input hashes and matching checks. Raw
traces and host-specific configurations remain ignored locally.

## What the graph actually contributed

Graph-2 and graph-3 received active approved D-2 through `check_change` **before
their first edit**. Graph-2 received it at trace lines 23 and 31; its first edit
was line 32. Its final response credited organizational history, local commits
and the approved 303-only constraint with preservation requirements. That is a
model self-report plus observed exposure, not proof that the rule caused success.

Graph-1 retrieved real historical evidence but did not receive D-2: a short symbol
lookup returned `unknown`, and a later broad file impact check exceeded caller
bounds. Its passing patch must not be described as approval-informed.

All 12 Company Brain calls completed at the transport level, but their response
statuses were nine `incomplete` and three `unknown`. Excerpt, caller or other
bounds remain material limitations. Warnings, exact arguments, source URLs and
constraint IDs are retained in [MCP evidence](v5-trials/mcp-evidence.json).

None of these coding sessions directly seeded a Document or received a repository
document-section excerpt. Document ingestion and the doc → PR → file → symbol
path were separately verified through the real driver and STDIO probe. Do not
claim that this comparison establishes model use of repository documentation.
The required Browser visual remains a separate gate.

The [post-trial document probe](v5-document-evidence.json) verifies the real
FalkorDB path and untruncated document Source through a separate STDIO process;
it was not supplied to any coding session.

Every baseline also preserved the 303 behavior. **No difference on that constraint
was observed**, consistent with its existing code and nearby tests being visible.

## Fresh demonstration selection

Use graph-2 as the fresh-v5 coding example: human approval/supersession occurred
first, the corpus was frozen, D-2 reached the model before edits, and the unchanged
patch passed 12/12 plus 225 upstream tests. Show the complete 3+3 table alongside
it. The [lifecycle export](v5-lifecycle-evidence.json) records the real operator
transition. This selection demonstrates execution; it does not turn the tie into
an improvement claim. The older 12/12 artifact is explicitly an earlier-graph run.

The exact derived urllib3 patches are distributed with the retained upstream
[MIT notice](../data/sources/urllib3/LICENSE.txt). Source attribution remains urllib3.
