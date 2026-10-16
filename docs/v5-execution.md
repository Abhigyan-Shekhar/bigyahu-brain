# v5 execution log — 16 October 2026 (IST)

The user's v5 plan is the execution plan. Their subsequent corrections take
precedence: exact changelog → PR bridge first; frozen fresh evaluation after
approval; Browser required; reproducible sources promoted to P0; 30-second
supersession segment; publication review/public visibility Saturday night
(17 October), leaving Sunday for fixes/submission. No architecture rewrite.

## Completed implementation and observed evidence

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
