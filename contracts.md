# Company Brain contract — 0.1

Default five MCP tools: get_context, trace_decision, find_owner, check_change, remember.
No administrative tool or arbitrary Cypher endpoint exists.

Opt-in extension: `memory_db` plus `tenant_id` enables memory_search(query, brains?,
include_graph?, include_proposals?, limit?) and memory_propose(text, sources,
brain?, expires?). Principal/tenant come only from server config. Shared brains
require operator-owned membership. Source/memory acceptance is never a binding
code decision. Default graphs are preserved; an explicit tenant prefixes graph
names into new namespaces. See docs/memory-architecture.md for the new contract,
docs/memory-governance.md for trust/retention, and docs/roadmap.md for actual status.

Operation `status` is ok/error/unavailable/unknown/incomplete. Decision lifecycle
uses the separate `decision_status` field: proposed, active, superseded.
All responses include graph_revision, evidence, warnings, verification, and
untrusted_source_excerpts. Source and decision prose are quoted in the latter;
only structured evidence metadata appears in must_preserve/review.

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
