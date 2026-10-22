# Company Brain contract — 0.1

Default MCP tools: repository_status, get_context, trace_decision, find_owner,
check_change, remember, search_code, read_code, repository_files, search_history,
resolve_evidence. The original five operations keep their signatures.
No administrative tool or arbitrary Cypher endpoint exists.

Standalone repository retrieval uses the same byte/provenance/history checks as
the application, with a process-local cache of at most 128 citation descriptors.
Reopening a citation rechecks its source and topology; IDs expire on restart or
eviction. A direct source UID resolves only within the configured org repository.
Tenant mode authorizes company access before every call, including reopening an
issued ID. No client selects a tenant, filesystem evidence directory, or arbitrary
Git object. See [native Codex setup and bounds](docs/codex.md).

Optional `BRAIN_REGISTRY` selects a validated operator-owned allowlist rather than
one `BRAIN_CONFIG`. In this mode `list_repositories` exposes registered roots/IDs;
every other tool requires the absolute `repo_root` on every call. Context and
citation caches are separate per root, with no mutable shared selection. All
configs must share the same trusted principal, tenant and memory settings.
Unregistered roots fail before retrieval. Registry/config changes require a server
restart; live index refresh is checked on subsequent calls. Operator CLI registry
sync preserves the existing clean committed-checkout requirement. Single-config
mode retains its signatures and tool inventory.

Opt-in extension: `memory_db` plus `tenant_id` enables memory_search(query, brains?,
include_graph?, include_proposals?, limit?, backend?) and memory_propose(text, sources,
brain?, expires?). Principal/tenant come only from server config. Shared brains
require operator-owned membership. Source/memory acceptance is never a binding
code decision. Default graphs are preserved; an explicit tenant prefixes graph
names into new namespaces. See docs/memory-architecture.md for the new contract,
docs/memory-governance.md for trust/retention, and docs/roadmap.md for actual status.

With `memory_graph_enabled: true`, the catalog extension additionally registers
read-only memory_graph(brains?, include_proposals?, include_company?). It reads a separate
tenant-derived memory projection, requires current catalog authorization, returns
`incomplete` for stale/missing projections and never establishes binding rules.
This opt-in graph response uses nodes/edges/warnings/binding/trust_status rather
than the legacy code-evidence envelope. See docs/three-brain-graphs.md for its
explicit sync, privacy, provenance and size-bound contract.
`include_company=true` additionally requires a current company grant and a
completed company index. It returns verified source/lexical code bridge paths
from a refreshed projection; it never approves a code constraint. Plain memory
views cannot expose company proxies. See docs/memory-company-bridge.md.

`memory_search` backend `auto` now selects FalkorDB in graph mode and the existing
catalog route otherwise. `falkor` is embedding-free exact/full-text plus authorized
native path expansion; it does not silently fall back on stale/unavailable data.
`catalog` explicitly preserves the optional-vector baseline. Native response
`graph` is a bounded nodes/edges evidence view. Company joins in native search use
`include_graph=true` and require current company access. See
docs/falkor-memory-retrieval.md for ranking, index refresh and bounds.

Operation `status` is ok/error/unavailable/unknown/incomplete. Decision lifecycle
uses the separate `decision_status` field: proposed, active, superseded.
The original graph-operation responses include graph_revision, evidence, warnings, verification, and
untrusted_source_excerpts. Source and decision prose are quoted in the latter;
only structured evidence metadata appears in must_preserve/review.
Shared repository reads carry source text in checked_evidence; history retains
its existing items/coverage/ranking envelope and advisory association metadata.

Graphs are fixed to org_demo and private_<configured principal>. Scope arguments
accept only org/private. Configuration, not MCP arguments, selects the repository.
These are legacy demo defaults; tenant mode uses isolated derived names. Memory
brains accept company/team:<authorized team>/private:<configured principal> and
are separate from the legacy scope argument. No client can choose a tenant.
Project UID is canonical repo_id. File/symbol UIDs include repo, SHA, path and
qualified symbol; historical revision nodes remain available. Commit UIDs include
repo and commit SHA. Git author identities are separate from GitHub identities.
No unsupported identity joins or inferred team membership are created.

A CALLS edge points from caller to callee. check_change traverses incoming paths
of one or two edges and batches decisions over targets and callers. Limits never
silently yield an apparently complete constraint check. Incomplete syncs fail closed.
Any dirty working tree or changed HEAD downgrades precision to file; constraints
are advisory until the checkout and approved revision match again. Diff-only
requests currently use conservative file coverage.

Only an independent interactive operator session may run approval. The CLI checks
reviewed evidence/text/subjects and replacement scope in one database mutation.
Local shell/database administrators can bypass this application boundary; no
production isolation claim is made. Agents must never run the approval command.

Repository documentation uses the existing Document and Source labels. Bounded
tracked RST/Markdown sections carry revision, digest, path, line range and an
immutable blob URL through SUPPORTS. The additive MENTIONS relation connects a
Document to a PR by exact number or a current Symbol by exact qualified reference.
It records source_uid, source_line, reference, confidence and binding=false.
It is distinct from PR-to-Issue REFERENCES and never creates a Decision or
CONSTRAINS edge. Public explicit re-exports resolve statically; abbreviated,
ambiguous, inherited and dynamic references remain unresolved.

Native document versions retain their old UID/citation shape and now carry a
stable logical section ID and current marker. Refresh fences block readers after
failure until retry; retirement hides old sections while retaining historical
Source citations. Catalog refresh/deletion is transactional and separately erases
searchable text/vectors. New GitHub syncing uses content-addressed Source versions
and commits its cursor only after complete acquisition/publication.

## Graphify and three-brain integration

The operator CLI adds `ingest-graphify [tracked-code-paths...]` with the pinned
optional Graphify extra. It writes revision-pinned advisory documents and
`EXTRACTED_RELATION` evidence, never authoritative `CALLS` or decisions. Native
retrieval uses up to four checked one-hop frontiers with a bounded seed/node state
budget, returning traversal diagnostics without widening caller scope.

`import-conversation --semantic-model MODEL` explicitly opts into external model
selection of consented literal durable spans and entities. Model output remains
non-binding proposals; explicit correction links require separate review. The
local viewer fixes identity in configuration and routes authenticated graph reads
through `MemoryTools.memory_graph`. It adds no hosted identity or MCP tools.
The experimental runner's `--memory-graph` enables both read-only memory tools.
See [integration contracts and reproduction](docs/graphify-three-brain-integration.md).

## Source-grounded named concept extension

`annotate-concepts --document UID [--document UID ...] --model MODEL` explicitly
sends selected current company document sections to the named model. Output is
validated as literal spans before any mutation. Native `ConceptMention` evidence
is advisory and guarded by a separate readiness flag. The memory bridge adds
`MATCHES_MENTION`/`MENTIONS_CONCEPT` paths only after company access and current
source/annotation/span/revision checks; these are label associations, not identity
resolution. They add no MCP tools or approval authority. See [contracts, bounds
and evaluation](docs/company-concepts.md).
