# Workspace UX and interaction flow

The workspace now has four destinations: **Ask Brain**, **Explore Graph**,
**Agent Runs**, and **Memory**. Repository selection, recent conversations and
read-only workspace settings remain in the sidebar. Personal and Team scopes,
including team membership and portable memory controls, sit under Memory.

## Navigation and review

Ask Brain retains source-checked answer cards and compact fix launchers. A fix
launcher creates a linked read-only plan and opens Agent Runs. Investigations and
fixes appear separately in its run list, with actual lifecycle states. A run links
back to its originating conversation. The list shows the latest 20 fixes and
20 investigations; older selected IDs resolve through a repository-scoped direct
lookup, including the verified originating session. Missing or cross-repository
IDs return a real not-found response instead of an endless loading state.
Saved plan, approval, edit and verification
sections remain navigable; focused review retains patch download and explicit
approval. Request changes closes the pending plan and opens a revised objective;
it cannot silently approve or edit. Any replacement needs fresh approval.

Investigation and action activity projects only allowlisted tool names and
recorded completion states. New investigations record start/finish timestamps;
historical missing timing stays unavailable. Traces are bounded to 2 MB; the
latest 12 observed events are retained in the projection. Unknown outcomes are
unverified, never converted into successful events. No model reasoning, tool
arguments or raw tool output is exposed as activity.

## Graph views and provenance

The entire-index overview groups current company entities by entity type or
by top-level folder. It queries aggregate counts across the current repository,
including source entities. The demo has 1,275 indexed entities, ten type groups,
and seven folder groups. Groups are capped at 100 with an explicit warning.
Selecting a cluster loads its bounded members plus up to 50 directly connected
context entities. A visible cross-cluster relationships switch can hide them;
overflow is disclosed and individual neighbor expansion remains available.
Search within cluster retains the root filter; Search entire index explicitly
clears it while preserving the query. Search matches names, symbols, paths,
identifiers, source kinds and URIs. Ingestion completion invalidates the overview
as well as detailed pages; its observer remains mounted during graph exploration.
Returning to the graph also refreshes aggregate counts.

Detailed graph pages load 100 roots plus up to 50 document sources, optionally
50 connected context entities for cluster views, and 300 edges.
Neighbor expansion loads up to 50 neighbors per page; the interactive workspace
caps accumulated detail at 300 nodes/600 edges. Root paging stops at offset
50,000 and neighbor paging at 5,000, with a narrowing-search notice. Grouping and
search preserve discoverability without claiming every entity is on the canvas.

A checked chat citation can open its focused native evidence slice. Selecting
an entity opens a contextual inspector with its current revision and metadata;
source excerpts are reopened using the existing source-byte/provenance checks.
Missing sources or stale evidence are disclosed. The inspector can focus one
neighborhood or expand another hop. Two selected loaded nodes reveal a shortest
recorded connection; arrows keep their stored direction. The path inspector
shows quotes/source references where recorded, or a checked slice's attached
source. Connections and reviewed rationales do not prove causal improvement.

The overview uses summary clusters. Large detailed slices suppress labels and
edges at low zoom; zooming or toolbar selection exposes individual records.
Viewport and path selections survive graph-to-chat round trips during the
current workspace session. View entire graph retains the focused selection and
its inspector. This is in-memory UI state, not persistence across application
restart or arbitrary repository switches.

Explain in chat attaches bounded entity/edge/path/cluster identifiers and the
indexed revision to the composer. It does **not** send automatically, approve
anything or elevate the selection to evidence. Raw tool arguments and source
prose are excluded from this attachment. The normal 8,000-character question
limit applies. A return-to-graph control preserves the view.

## Memory and privacy

Personal source inspection can return to an originating coding report or an
app-verifiable selected conversation turn. Ordinary notes and imported snapshots
remain inspectable inline without invented links. Team management retains its
existing catalog permissions and separate acceptance workflow. Switching tabs
does not accept, share or revoke anything. This remains a single trusted local
operator application; historical report retention after revocation is unchanged.

## Validation

- Isolated graph, memory, application and process suite: **412 passed**, zero
  skipped, three existing dependency deprecation warnings.
- Frontend presentation/context tests: **5 passed**; production build and Ruff
  passed. Agent Runs and the inspector load as separate bundles.
- Follow-up endpoint regression: 21 newer fixes/investigations push selected old
  IDs outside both list windows; direct lookup still returns their session.
  Missing, unauthenticated and cross-repository requests fail. Live graph tests
  verify File clusters retain roots and expose connected entity types/edges.
  A disposable browser workspace with 21 newer runs reopened both an older
  investigation and its original fix report from the conversation. Live search
  for TimestampSigner.unsign returned no File roots, then five entities after
  choosing Search entire index.
- Live browser: selected a Symbol cluster, inspected TimestampSigner.unsign and
  its reopened source at line 72, focused its ten-node/thirteen-edge neighborhood,
  and attached the selection to chat without sending. The viewport matched on
  return. Inspected a two-node native evidence path and its checked source link.
- Confirmed whole-index type/folder counts; overview retained the focused
  selection. Checked the stopped-plan reason and retry objective without sending
  another model request, focused execution report, and return to investigation.
- Opened a proposed Personal lesson's originating run. Confirmed Team management,
  sharing and portable memory controls remain under Memory. No lesson accepted,
  team grant changed, new plan approved or new model editing journey performed.

Known scope: clusters are repository entity-type/top-level-folder summaries,
not a new semantic community detection algorithm. Path finding covers loaded
relationships, not an unbounded server-wide shortest-path search. The existing
index's evidence/coverage gaps remain. Mobile and a fresh paid coding journey
were not acceptance-tested for this follow-up. Screenshots remain local/ignored.
