# Chat and connected repository knowledge

The primary application workflow is now: connect a public repository → Graphify
structural extraction → chat beside the native knowledge graph → upload company
documents → automatic Graphify semantic extraction → inspect quoted evidence and
its graph node identities. The graph lives in the repository's existing FalkorDB
tenant. Job and chat state remain in the local application catalog; immutable
upload bytes and extraction snapshots remain on disk for citation verification.

## Using the workspace

Follow the environment and launch commands in [the application guide](company-brain-app.md).
The `graphify` and `ingestion` extras are required for the complete flow. New
repository connections run Graphify before becoming ready. Optional GitHub
history acquisition retains its partial coverage report; the connect dialog can
require successful acquisition if the demonstration depends on that history.

Chat is the default screen. The knowledge rail shows repository node counts and
a readable sample of the current graph page. **Explore graph** opens the larger
searchable, paged graph. **Next nodes** walks the remaining indexed nodes;
double-clicking a node expands its recorded neighbors. Neighbor paging is
separate from repository paging. This is a bounded view of the indexed graph,
not a claim that the entire repository fits on one screen.

**Add document** accepts Markdown, RST, text-based PDF, or DOCX. Uploads immediately
save source-backed sections and queue Graphify relationship extraction. All
uploaded sections are processed in batches of up to eight, with durable progress
and partial-failure receipts. The document library exposes failed jobs and allows
selected sections to be retried. Semantic processing uses the configured Codex
model and account usage. During extraction, new investigations and source changes
are blocked so an answer cannot mix changing graph snapshots.

Literal file paths and qualified symbol names in uploaded documents add advisory
`MENTIONS` edges to current code nodes. Merely mentioning a file does not create a
constraint on every function in it. Graphify code nodes connect to their files via
`HAS_EXTRACTED_NODE`; semantic entities connect back to original document sources
via `DERIVED_FROM`. Existing validated source and model relevance checks remain
in place. Source prose never becomes an instruction to the investigation agent.

Each newly published answer claim includes checked source buttons and expandable
**Evidence** rows containing exact quotations, graph node labels, and full node
IDs. Clicking a node opens its current graph neighborhood. Clicking a source
opens the checked bytes and source graph. Older saved answers retain their
original source buttons; they do not gain invented historical node lists.

Questions about changes and previous approaches use the existing investigation,
history, and approved isolated coding-action workflow. A supported change plan
can be prepared from an answer, reviewed, and approved to generate a patch and
test report. Team administration remains in secondary workspace tools.

## Coverage and limits

Repository Graphify extraction supports the adapter's Python, JavaScript/JSX,
TypeScript/TSX, Go, Rust, Java, and C/C++ suffixes, up to 500 tracked UTF-8 code files
and 10 MB total. The clone and Python indexing limits still apply. Unsupported
languages and external dependency definitions are outside this coverage. Unlocated
extractor references and relationships without located endpoints are counted and
reported, rather than published with fabricated provenance. Empty source files
remain File nodes from the code index, without fabricated source excerpts.

Graph pages contain 100 non-source roots with up to 50 supporting sources and
300 edges. Counts describe current indexed nodes, not parse completeness. The
browser caps accumulated neighbor expansion at 300 nodes/600 edges. Document/code
reference linking considers up to 10,000 current file/symbol targets and returns
an explicit coverage flag when truncated. Semantic relationships remain advisory;
exact-source checking does not prove that a model's interpretation is correct.

## Verification

A fresh public `pallets/itsdangerous` connection at revision
`672971d66a2ef9f85151e53283113f33d642dabd` completed Graphify extraction over 15 code
files: 195 located nodes and 520 relationships, with 21 unlocated references and
137 relationships without located endpoints explicitly excluded. This run did
not acquire GitHub issue/PR history.

A clearly labeled demonstration design document automatically produced five
semantic entities and four relationships using Graphify and the configured Codex
model. A real read-only Codex investigation retrieved the upload and code, then
published three source-checked, relevance-reviewed claims with twelve supporting
node references. It distinguished the notes' description of a previous approach
from the current code's optional expiration behavior. This demonstrates evidence
retrieval and provenance, rather than establishing the truth of authored notes.
Browser verification covered the answer, expandable quote/node identities, the
graph preview, and paging to the next graph slice.

The isolated FalkorDBLite suite, including real Graphify, application API and
STDIO process checks, passes 382 tests. Ruff, the frontend production build,
Prettier checks and `git diff --check` pass. The new regressions cover automatic
upload jobs, complete batching, partial failure, mandatory extractor failure,
ambiguous code references, punctuation in file mentions, graph paging, citation
node identities, duplicate basenames, empty files, external references and source
path preservation through a symlinked temporary root.
