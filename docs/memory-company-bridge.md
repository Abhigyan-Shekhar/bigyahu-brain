# Memory to company graph bridge

An opt-in projection now connects authorized memory references to existing
company Source, Document, File and Symbol nodes. It creates native edges in the
memory graph while retaining original company UIDs and the indexed repository
revision. The original code graph is read-only throughout this operation.

## Native paths

- Memory → `MENTIONS` → Entity → `RESOLVES_TO` → CompanySymbol.
- Memory → `SUPPORTED_BY` → Source → `VERIFIED_SOURCE` → CompanySource.
- CompanyDocument → `SUPPORTS` → CompanySource, and CompanyDocument →
  `MENTIONS` → CompanySymbol, copied only from existing current company paths.
- CompanyFile → `DECLARES` → CompanySymbol, copied only when that native
  declaration actually exists in the company graph.

These paths coexist with personal/team/company memory citation links and
reviewed memory assertions. They let an authorized consumer follow developer or
team memory to company evidence and exact indexed declarations. They do not
create new code relationships, approve decisions or establish binding policy.
Use the existing `check_change` contract to obtain applicable approved constraints.

## Source matching

`VERIFIED_SOURCE` requires an exact URI and SHA-256 match against the **complete
stored company excerpt**, not a shared URL alone or a claimed digest property.
The excerpt must be nonempty, untruncated and at most 12,000 characters. Exactly one matching
source node must exist. Multiple matching historical source UIDs remain ambiguous
rather than being merged without version justification. This checks consistency
with the ingested company evidence; it does not fetch a URL, authenticate its
author, or verify the rest of a remote document.

Matched immutable historical Sources can remain useful evidence. A retired
Document is not projected as a current document path. Projected Source metadata
distinguishes the index `graph_revision` from its original `source_revision`,
which may be older or unknown. A Document's complete stored text must also match
its linked Source bytes before its path is copied. Its symbol mention requires
the native exact-reference confidence and matching evidence source UID.

## Code reference matching

Entities originate from explicit backticked identifiers in authorized memories.
Resolution supports exact repo-relative lexical identities such as `x.py::a`
and uniquely indexed module-qualified names such as `x.a`. Symbols must be
current, belong to the configured repository and revision, have the canonical
indexed UID, and have a corresponding current indexed File.

The resolver excludes ambiguous module paths, bare names such as `a`, and unknown
references. A module-qualified match is a lexical index association; it does not
claim runtime binding, re-export, inheritance, decorator behavior or dynamic
dispatch resolution. In particular, it does not guess that two people with the
same name are the same person or federate their private graphs.

## Access and freshness

Every joined read and synchronization requires both the requested memory scopes
and a current `company` grant. Writes additionally require owner/reviewer access
to the memory brain. Identity must match the configured graph tenant/principal.
Authorization completes before memory or company graph I/O. All queries are
parameterized and repository-filtered; callers cannot specify another graph,
tenant, repository, SQL or Cypher.

Plain memory reads retain their default behavior: they do not query the company
graph or expose company proxies, even when a reviewer previously synchronized
company paths into that memory brain. Team membership alone does not give company
access. Direct database/Browser access remains trusted-operator access, outside
the application authorization boundary.

The company index must have a completed revision with no code/document/GitHub
sync fence active. A joined projection records that revision; a changed revision
requires explicit refresh. The read also recomputes eligible reference matches
against current company evidence and compares the requested native edges with
the projection. Retired documents, mismatched source bytes and hidden or expired
memory references cannot return their old bridge paths. Missing newly expected
edges return `incomplete`; an unavailable index/backend returns `unavailable`.
Unresolved/ambiguous references are reported explicitly and do not produce fake
nodes or edges. They are not evidence that a dependency or source does not exist.

Both stores remain separate authorities. These checks are bounded observations,
not an atomic cross-graph transaction or distributed snapshot guarantee. Refresh
is explicit. Old physical proxies are removed by the next successful brain sync;
they can be ineligible through the API before their physical erasure.

## Enable and inspect

The existing `memory_graph_enabled: true` configuration enables the projection
namespace and eighth MCP tool. No new tool is added for this bridge.

```sh
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml sync-graph --brain private:alice --include-company
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml graph-view --brain private:alice --include-company
```

MCP: `memory_graph(brains=["private:alice", "team:backend", "company"],
include_company=true)` selects authorized scopes and company joins explicitly.
The default `include_company=false` preserves memory-only reads.
All returned text remains untrusted, with envelope `binding=false`.
Joined responses report `company_revision` and `unresolved_company_references`.
Projection metadata, native company UIDs, edge basis and citation JSON retain
provenance. Company proxies are excluded from `.abhi/2` export; portable source
citations and identifiers can be resolved anew in the destination's own company
index, subject to its grants and graph evidence.

Lookup bounds: 1,000 company source candidates, 20,000 current symbols, 5,000
current files and 500 document path rows. A complete joined brain view still
has at most 500 nodes and 1,000 edges. Overflow fails explicitly.

## Verification and limits

The tests use disposable real FalkorDB graphs with actual AST/code and Markdown
ingestion. They check Unicode source hashes, native document/declaration paths,
exact lexical joins, unchanged company nodes, ambiguity/digest failures, unknown
and bare names, duplicate source versions, cross-repository filtering, tenant
identity mismatch, revocation, missing projections, changed revisions, sync
fences, document retirement and MCP/team access boundaries.

This establishes native connected evidence, not a fresh coding-agent execution
or measured advantage over baseline. Semantic fact extraction, Graphify/PDF
ingestion, a permission-aware clickable UI, and the full product demonstration
remain separate milestones.

Local verification on October 17, 2026: **237 tests passed** in the complete
disposable FalkorDB/Lite suite. The engine owner stopped with SAVE. Ruff,
whitespace and publication/history scans passed. The existing third-party
Authlib deprecation warning remains. Existing approved demo graphs and frozen
coding-trial artifacts were not modified.
