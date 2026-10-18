# Evidence-first demo presentation

The app keeps its existing repository, investigation, approval, isolated execution,
and memory-review workflows. Presentation emphasizes the diagnosis, connected
sources, and observed outcome before technical reports.

## Graph architecture

**FalkorDB stores the knowledge graph. React Flow renders it.** The browser never
creates a relationship merely to make the visualization look connected.

The entire-graph endpoint now aggregates directed stored relationships by entity
type or top-level folder. Both endpoints of every relationship must belong to the
current repository and be current. The response is bounded to 100 node groups and
200 relationship groups, with separate truncation notices. Internal relationship
counts stay inside their cluster; cross-cluster relationships become arrows.
Selecting an aggregate opens its count and stored type; selecting a cluster opens
a bounded slice with its existing cross-cluster context. Individual source and
relationship inspection continue through the existing evidence workflow.

Dagre supplies directed positions with explicit node dimensions and rank spacing; React Flow renders the resulting graph using
a small minimap and the existing pan, zoom, neighbor expansion and path controls. Dense detail views begin with six connected entities, disclose the displayed/loaded counts, and offer the full loaded graph. Cluster markers vary by entity type; edges recede until hovered or selected.
At low zoom, detailed labels recede while connections stay visible. Purple marks
memory/evidence; sage remains the workspace identity.

## Demo path

1. Open Ask Brain and a saved investigation. A concise first finding leads;
   detailed diagnosis, supporting findings, limitations and review metadata remain inspectable.
2. Open a cited source from the adaptive context panel, then its evidence graph.
   The sidebar shows directed connection rows. It may add current directly linked symbols whose labels occur in the stored investigation; these are explicitly labeled navigation context. Opening the explorer preserves those entities. The checked citation itself stays separate from this additional context.
3. Explore the entire graph. Explain FalkorDB storage and React Flow rendering,
   select a relationship to inspect its aggregate, then open a cluster.
4. Open Agent Runs. The execution timeline and baseline/patched results lead.
   Counts come from retained runner results, with unknown counts left unknown.
   Unittest assertion failures and runner errors are separate. When comparable
   counts are unavailable, show passed commands rather than inventing a test total.
5. Explain the separate states: execution finished, tests passed, matched baseline
   regression demonstrated, independent bug review, and unchanged source checkout.
   Run cards use the same backend verification calculation as the detailed report.
6. Open Memory. Filter accepted knowledge or awaiting review, inspect its source,
   and return to the originating run. Transfers and graph connection controls are
   available under a separate disclosure. Do not accept memories merely for a demo.

On narrow screens the run browser starts collapsed so the outcome remains visible.
No model calls, approvals, code executions, or memory reviews are triggered by
navigation. The redesign does not add an independent bug-verification mechanism.

## Focused hero polish

Ask Brain now leads with an extractive first sentence from the stored finding,
followed by cited-excerpt count, graph reveal, and the fix handoff. Detailed findings
and source paths remain closed until requested. Memory lists also use extractive
short titles; selecting a record exposes its full text and review controls.

The activity hero renders actual lifecycle stages, current allowlisted tool names,
and the last recorded completion events from existing backend polling. It does not
schedule fictional future stages, estimate percentages, or synthesize progress.
Queued runs without a current tool show an explicit waiting state. Completed
investigations label their timeline as recorded activity. Isolated execution uses
the same activity component while its backend status is running or queued.
