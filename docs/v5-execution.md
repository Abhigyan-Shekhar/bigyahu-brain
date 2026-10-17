# v5 execution log — 16 October 2026 (IST)

The user's v5 plan is the execution plan. Their subsequent corrections take
precedence: exact changelog → PR bridge first; frozen fresh evaluation after
approval; Browser required; reproducible sources promoted to P0; 30-second
supersession segment; publication review/public visibility Saturday night
(17 October), leaving Sunday for fixes/submission. No architecture rewrite.

## Current completed milestone

Independent human approval and supersession are complete: D-1 is superseded,
D-2 is active, and `check_change.must_preserve` returns D-2. The frozen corpus
SHA-256 is `b16fc995c9d4429a54c20601ae471bbc7a789d61a1256184068aa30c5ef688f6`.
All six fresh trials completed; both baseline and graph succeeded 3/3, with
12/12 oracle cases and passing upstream suites in every session. No accuracy
advantage was observed. See [results](v5-evaluation.md) and
[operator lifecycle evidence](v5-lifecycle-evidence.json).

The separate [reconstructed Browser demo](browser-demo/README.md) now records
visual traversal and human-approved supersession on its own graph. It uses a
seeded editorial Document and different policy targets/text; it is not the frozen
v5 experiment corpus. Visual verification of the original v5 paths, the actual
submission form, final video and Saturday publication review remain release gates.
The checkpoints below retain the earlier order of work; their proposed/pending
states and permission failures are historical.

Earlier v5 Browser check: the user installed FalkorDB Browser and added an explicit
`http://localhost:3000` browse allow entry. The local configuration confirms
`access=allow`, but the computer-use gate still denies observing the existing
Codex browser tab, reporting a saved-permission or managed-policy block. Native
FalkorDB Browser access was also rejected as not approved. No raw CDP, alternate
browser surface or indirect control workaround was used. This remains a runtime/
policy gate; it is not a demonstrated Lite compatibility failure. A fresh app
session is the next diagnostic after the coding trials, not a claim of resolution.

The latest locked clean-room environment also passes all **134 tests** with
real graph/Lite lifecycle checks enabled. After the coding trials, a separate
STDIO probe retrieved the untruncated changelog Source again, and real driver
queries verified the primary and re-export/caller paths on the frozen graph.
[Document evidence](v5-document-evidence.json) records that verification without
claiming Browser access or model use of documentation.

## Initial implementation checkpoint (before human approval)

- Working branch started at `4d8d622`, the integrated recorded agent demo,
  rather than resetting to the plan's older stated starting commit. Preserved
  the passing patch, oracle, old run and old video bytes unchanged.
- Inspected actual tracked pinned urllib3 docs before writing ingestion code.
  Found Sphinx roles, double-backtick literals and `autoclass`, abbreviated
  `poolmanager.PoolManager` and public `urllib3.PoolManager` re-exports.
- Added bounded `ingest-docs`: three default tracked RST files, explicit file,
  total-byte, section, excerpt and resolver limits. Rejects dirty/stale index,
  binary content, nontracked paths and symlinks. IDs are revision/line bound;
  sections retain SHA-256, real lines and immutable Source blob URL.
- One new allowlisted relation, `MENTIONS`, for exact PR numbers and exact,
  unambiguous qualified Symbol references, including explicit public re-exports.
  No abbreviated suffix matching, inherited method guessing or active decisions.
- Prepared graph has 179 bounded Document sections from three files; one exact
  PR link and 38 symbol links. Unresolved names are reported. The #5161 source
  section includes the 303 entry in its untruncated excerpt; the longer PR body
  remains explicitly truncated by the normal service budget.
- Driver traversal verified `CHANGES.rst:127 → PR #5161 → poolmanager.py →
  PoolManager.urlopen`. Bonus verified `docs/reference/urllib3.poolmanager.rst:10
  → urllib3.ProxyManager` (resolved to its indexed definition) with incoming
  `proxy_from_url` call. Queries are in [reproduction](v5-reproduction.md).
- Included only #3780/#5161 public snapshots in `data/sources/urllib3` with
  a filtered-content hash and original collection/provenance metadata. Excluded
  #5181/#5191/#5242 records. One staged script rebuilds code/history/snapshots/docs,
  proposes D-1, handles separate human lifecycle steps, then freezes the corpus.
- Real D-1 proposed against `PoolManager.urlopen`, supported by upstream #5161.
  Captured pre-approval `must_preserve=[]` and review trace locally. No real
  approval simulated or performed by the agent. Freeze correctly refuses a
  proposed-only graph. Narrower D-2 is prepared in the script for human review.
- [Paired criteria](v5-evaluation-protocol.md) fixed before v5 trials: full
  12/12 oracle plus upstream suite for success, all attempts reported, no causal
  or significant lift claim at n=3. Common conditional tool instructions keep
  baseline/graph task text identical. No v5 trials have started.
- Earlier 12/12 report explicitly labelled as a run on the earlier graph.

## Browser morning gate

No Docker executable or desktop runtime is installed. Started official FalkorDB
Browser from source at `8d5b64e6428b1a727bb682a0bd836dd6f7f0d5e4`
(Browser 2.7.0 / Next.js 16.3.8) in a temporary external checkout. It is configured
for the isolated Lite TCP server on loopback port 6393; Browser listens on
`http://localhost:3000`. Lite reports Redis 8.6.2 / graph module 4.18.3.

**Visual attachment and direct org graph URL remain unverified.** The computer-use
origin gate denied localhost; explicit user approval to open it was then received,
but retry was rejected by a saved permission/managed policy. No alternative
surface or indirect browser-control workaround was used. This is a UI permission
block, not evidence that Browser cannot attach to Lite. Clear that saved setting
and verify the two queries visually. If actual attachment fails, use the Docker
FalkorDB+Browser setup and repeat reconstruction/verification there.

## Submission and release gates

Read the [live official rules](https://www.wemakedevs.org/hackathons/falkordb/rules)
on 16 October. Required: public source repository; README setup and graph model;
dependent Cypher/algorithms; working demo video; deployment or complete local
setup; entered tracks; AI-assistance disclosure. Local setup is permitted in
place of deployment. This is a rules check, **not** a completed form inspection.

The live registration/submission panel could not be inspected: its browser origin
permission was also denied. Required actual form fields, video host/length limits,
deployment field rules and account/team state remain a Friday-night user gate.
No registration, submission, upload or public visibility change has occurred.

Validation: **130 passed**, no skips, with real FalkorDB and Lite lifecycle flags;
Ruff across src/tests/scripts and diff whitespace checks pass. A separate real
STDIO probe retrieved the untruncated #5161 document excerpt, exact source line
and all five tool names. Its response correctly reports incomplete because the
linked PR body exceeds the normal excerpt budget. The 498 text-bearing graph
nodes contain none of the screened excluded-work references. The publication
guard passed 98 indexed files and complete reachable history at this preflight;
this is not a final privacy audit or authorization to publish an unreviewed video.

Clean-room reconstruction also passed from a separate committed checkout, a new
`uv sync --frozen --extra lite --python 3.12` environment, a separate pinned
urllib3 checkout and an empty isolated database. The prepared non-operator graph
matches exactly: **2,875 nodes and 3,899 edges**, including properties. Unique
operator proposal IDs and created-at audit events are intentionally excluded
from that comparison; no approval was simulated in either graph. The original
passing patch, checks, MCP evidence, oracle and old video remain byte-identical
to the starting commit. The fresh locked environment also passed the complete
130-test suite with real graph and Lite lifecycle checks enabled.

Saturday 17 October: run publication/history scan on the final release commit;
manually review source, snapshots, binary/video frames, credentials and personal
data; flip public only after that review, then verify logged-out access. Do not
defer first public-access check to Sunday. Current preflight findings belong in
this log once verified; they cannot certify a future release commit.

## Final video sequence (about 4:45)

1. 0:00–0:30: real repo/task; show exact pin and public source provenance.
2. 0:30–1:15: actual Browser primary and bonus paths; show Source URL/line.
3. 1:15–1:55: D-1 proposed → independent human approval → `must_preserve`.
4. 1:55–2:25: **Operator lifecycle on real sources**. Show narrower D-2 approved,
   D-1 `superseded`, D-2 `SUPERSEDES` D-1, retained source/history and current
   D-2 in `must_preserve`. This is operator clarification, not a new upstream policy.
5. 2:25–4:05: show freeze hash and a fresh run on that graph; model-selected MCP,
   actual edits/tests. If replaying the older passing run, label “earlier graph,
   before v5 documents/approval” and do not imply the new constraint caused it.
6. 4:05–4:45: independent outcomes, all attempted comparison results, no-difference
   result if observed, privacy/poisoning negative test and honest limitations.

Do not use `docs/demo/demo.mp4` as final successful footage: it records the older
failed 9/12 attempt. A new final video is still required.

## Trial preparation checkpoint (before human approval)

Prepared six fresh clean checkouts in the fixed order (baseline-1, graph-1,
graph-2, baseline-2, baseline-3, graph-3). All are at the same urllib3 pin,
Python 3.12.13, with identical 60-distribution locked environments. Exact launch
argument arrays, dependency inventories and the common task/instruction copies
are stored locally under ignored `data/experiments/v5-paired`. No model session
has started and no corpus is frozen while D-1 remains proposed.

The selected upstream suite passed **130 tests, 705 deselected** on the untouched
pin during environment preflight. This is setup validation, not a coding-trial
result, and no oracle or preflight output is placed in an agent checkout.

Closed an evaluator gap before freezing: success now requires exactly 12 oracle
results, all passing, and a nonempty upstream passing suite. Pytest JUnit XML
records actual upstream passed/failed/error/skipped counts. Regression cases
reject 1/12, extra oracle results, no tests and all-skipped suites even if the
process reports exit 0. Earlier trial artifacts remain untouched.

A [submission draft](submission-draft.md) is ready for the live form once browser
access is available; required form fields and final video/deployment URL rules
remain unverified.

After the evaluator change, the complete real graph/Lite suite passes **134 tests**
with no skips. Ruff passes across src/tests/scripts. The six prepared model
sessions remain unstarted pending the independent human lifecycle steps.
