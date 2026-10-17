# v5 recording script — approximately 4:45

**Recording readiness: original v5 Browser paths still need visual verification.**
The [separate Browser recording](browser-demo/README.md) now shows reconstructed
editorial document/caller paths and its own approval history. Those paths and
policy texts differ from the frozen v5 graph used below. If included, label that
segment as a separate reconstructed demonstration and use its own narration;
do not present it as footage of CHANGES.rst, ProxyManager or the trial decisions.

This is a recording plan, not a completed video or proof of attachment to the
frozen v5 graph. The earlier localhost Browser observation was denied by the runtime permission
gate. Do not retry through an alternate app, browser, protocol or screenshot
mechanism to bypass that denial. Driver/STDIO verification is recorded separately
in [document evidence](v5-document-evidence.json).

Use the real `org_demo` graph only. Approval and supersession already happened
in the human operator's terminal; do not repeat them or rebuild the frozen graph
for filming. Label historical exports and trial playback explicitly. Record a
new final video after the required Browser gate is cleared.

## Timeline and narration

| Time | Show | Say |
| --- | --- | --- |
| 0:00–0:30 | Repository README, task and pinned urllib3 revision. | “Company Brain connects code and public history to source-backed organizational context. This example fixes replay of file-like uploads across body-preserving redirects in urllib3. The source is pinned to `a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`; included PR snapshots are #3780 and #5161.” |
| 0:30–1:00 | Actual Browser primary path below; select the Document/Source properties. | “The deterministic bridge is this exact #5161 reference at CHANGES.rst line 127. The section retains its source URL and lines 103–130. The PR links to a historical file, and that file declares PoolManager.urlopen. A historical file association alone does not establish a symbol-level constraint.” |
| 1:00–1:15 | Actual Browser bonus path below. | “An exact Sphinx reference to urllib3.ProxyManager resolves through its public re-export. We also see the indexed proxy_from_url caller. Unresolved or ambiguous references remain unresolved.” |
| 1:15–1:55 | `v5-lifecycle-evidence.json`, visibly labelled **Historical operator lifecycle export**. Show `before_approval`, then `after_D1_approval`. | “Ingestion supplies untrusted evidence; it does not approve policy. Before approval, must_preserve was empty. A human independently reviewed the source and approved D-1 against this symbol in a separate terminal. These are recorded historical states, not a live approval.” |
| 1:55–2:25 | Actual Browser lifecycle path plus the export's `after_supersession` and `must_preserve`. Overlay **Operator lifecycle on real sources**. | “The operator then approved a narrower D-2. It preserves the 303 switch to GET and removal of the body, framing and rewind state, without prescribing 307/308 replay. D-2 supersedes D-1; the old decision and its evidence remain. The current impact response returns D-2. These are demo operator rules grounded in upstream sources, not policies authorized by urllib3 maintainers.” |
| 2:25–2:45 | `v5-evaluation.md` frozen-input section and full corpus hash. Overlay **Fresh v5 trial replay: graph-2; recorded after human approval and corpus freeze**. | “We approved and superseded first, then froze this corpus. Its SHA-256 matched before and after every trial. This playback is the fresh graph-2 session on that frozen graph.” |
| 2:45–3:20 | Graph-2 entries in reviewed `v5-trials/mcp-evidence.json`: trace lines 23, 29, 31; preserve warnings/status. | “The model chose the tools. At lines 23 and 31, check_change returned active approved D-2 before the first edit at line 32. The ambiguous TestPoolManager lookup at line 29 returned unknown. Other responses were incomplete because of bounds; warnings stay visible.” |
| 3:20–3:45 | Unmodified `v5-trials/graph-2.patch`, first PoolManager hunk and 303 branch. | “The patch records body position for replay, then forwards it only for body-preserving redirects. The existing 303 branch still clears the discarded body and rewind state. The agent also added regression coverage. Observing rule exposure does not prove that it caused this patch.” |
| 3:45–4:05 | Graph-2 row and oracle/upstream results in `v5-evaluation.json`/`v5-evaluation.md`. | “Independent evaluation after the session passed all 12 socket oracle cases and 225 upstream tests. This is the unchanged evaluated patch, not a repair after seeing the oracle.” |
| 4:05–4:30 | Entire six-row results table; keep baseline and graph rows readable together. | “Both conditions succeeded three out of three, with 12 out of 12 oracle cases each. No correctness advantage was observed. Every baseline preserved 303 too; adjacent tests were visible to both conditions. At n equals three, differences are anecdotal. Graph-1 did not receive D-2 and is not described as approval-informed.” |
| 4:30–4:45 | Limitations plus reproduction link. | “These coding sessions retrieved history and approved constraints, but no repository document-section excerpts. The doc path is a separately verified capability. Complete local setup and reviewed evidence are in the repository; bounded and unknown results remain explicit.” |

Speak the hash prefix while showing the full value:
`b16fc995c9d4429a54c20601ae471bbc7a789d61a1256184068aa30c5ef688f6`.
The 231.753-second graph-2 session can be condensed into the 100-second segment;
label accelerated or excerpted playback. Do not stage a new tool conversation
and present it as the measured trial. The public MCP export is a reviewed summary;
if showing it rather than raw recorded playback, label it **Recorded trial evidence**.

## Read-only Browser queries

These queries contain no writes. Select **org_demo** before recording. The first
two paths were verified through the actual driver; visual results remain pending.

Primary exact changelog → PR → file → symbol, with documentary Source:

```cypher
MATCH p=(d:Document {repo_id:'experiment:urllib3:5181:eligible', path:'CHANGES.rst'})
  -[:MENTIONS]->(pr:PR {number:5161})-[:CHANGES]->(f:File)
  -[:DECLARES]->(s:Symbol {qualname:'PoolManager.urlopen'})
MATCH evidence=(d)-[:SUPPORTS]->(src:Source)
RETURN p, evidence LIMIT 5
```

Bonus exact public re-export and incoming caller:

```cypher
MATCH p=(d:Document {repo_id:'experiment:urllib3:5181:eligible',
  path:'docs/reference/urllib3.poolmanager.rst'})
  -[:MENTIONS]->(s:Symbol {qualname:'ProxyManager'})
  <-[:CALLS]-(caller:Symbol)
MATCH evidence=(d)-[:SUPPORTS]->(src:Source)
RETURN p, evidence LIMIT 5
```

Current lifecycle graph, scoped to the two real decisions (query prepared from
the implemented schema and lifecycle export; Browser execution is pending):

```cypher
MATCH history=(new:Decision {
  repo_id:'experiment:urllib3:5181:eligible',
  uid:'D-b00dc7379a3a4ca0a08dbce704942574'})
  -[:SUPERSEDES]->(old:Decision {
  repo_id:'experiment:urllib3:5181:eligible',
  uid:'D-5354eeec80024d77a83a2526ec952063'})
MATCH subject=(new)-[:CONSTRAINS]->(s:Symbol)
MATCH evidence=(new)-[:SUPPORTED_BY]->(src:Source)
RETURN history, subject, evidence LIMIT 5
```

Status table without operator identity:

```cypher
MATCH (d:Decision {repo_id:'experiment:urllib3:5181:eligible'})
WHERE d.uid IN ['D-5354eeec80024d77a83a2526ec952063',
  'D-b00dc7379a3a4ca0a08dbce704942574']
RETURN d.uid AS decision, d.status AS status, d.approval AS approval,
  d.text AS text, d.approved_revision AS revision
ORDER BY decision
```

Expected current state: D-1 `superseded`, D-2 `active`, both `human_approved`
at the pinned revision. A current-state graph cannot display the earlier
proposed/active timeline; use the labelled historical export for those states.
Graph properties can contain `approved_by`; do not open/record that property
or expose other local identity data.

## Browser verification and recording checklist

All items below are **pending**, not implied by a green connection indicator.

- [ ] Runtime grants observation/control through the normal approved Browser surface.
- [ ] Browser attaches to the intended Lite TCP endpoint and `org_demo` is selected.
- [ ] Primary query visibly returns the real Document → PR #5161 → File → Symbol path.
- [ ] Document Source properties show the pinned URI, section lines 103–130 and exact mention line 127.
- [ ] Bonus query visibly resolves ProxyManager and its real incoming caller.
- [ ] Lifecycle query visibly shows D-2 → SUPERSEDES → D-1 and retained source/symbol edges.
- [ ] Status query shows D-1 superseded and D-2 active with human approval and correct revision.
- [ ] The org graph URL is reopened and checked before describing it as a reproducible direct link; the existing `?tab=` UUID is not proof of graph selection.
- [ ] Recording framing excludes graph lists, private namespaces, credentials, operator identity, notifications and unrelated tabs.
- [ ] Video contains actual Browser footage, clear historical/replay labels, the complete 3+3 comparison, warnings and limitations.
- [ ] Final recording is reviewed and its host URL/length validated against the actual live submission form.

An actual Browser-to-Lite attachment failure requires the documented Docker
fallback and verification before claiming compatibility. A permission denial
does not demonstrate attachment failure. Do not mutate this frozen graph to test
a fallback. Do not use `docs/demo/demo.mp4` as the final successful video: it is
the earlier failed 9/12 attempt. Any older 12/12 run must be labelled **Earlier
graph, before v5 documents and approval** and cannot illustrate D-2 exposure.
