# Native memory graph: first implementation

This increment adds real FalkorDB memory paths while retaining the catalog as
the authority for records, review and access. It is the first architecture
milestone, not completion of the full three-brain product.

## What works

- `conversation/1` imports automatically extract non-question user lines as
  verbatim candidate assertions, with character-range URNs and SHA-256 citations.
  The operator consents to the exact selected conversation once; extracted
  assertions are private proposals requiring review. Assistant prose is excluded.
- Reviewed private records can be explicitly shared to a team or company brain.
  Only the selected current hash is copied; destination records start as proposals
  and retain original citations. Sharing grants no access to the private brain.
- FalkorDB stores `MemoryNode` nodes with `kind` values Brain, Person, Team,
  Memory, Source, Entity and Version. Native relationships include
  `HAS_MEMBER`, `HAS_BRAIN`, `CONTAINS`, `AUTHORED`, `SUPPORTED_BY`, `MENTIONS`
  and `UPDATES`. Backticked code identifiers become entities shared across
  sessions within a brain. Structural `UPDATES` means an explicit record revision.
  [Reviewed assertion edges](memory-relationships.md) additionally support
  `UPDATES`, `EXTENDS` and `RELATES_TO` between pinned memory versions. They do
  not automatically infer contradiction or supersession between statements.
- `SAME_CITATION` connects source nodes across personal, team and company memory
  brains when URI and claimed content digest match exactly. An authorized view
  can traverse Memory → Source → Source ← Memory across scopes. This is a
  provenance association, not independent verification of the cited content.
- [`.abhi/2` interchange](abhi-format.md) exports selected accepted memories,
  citations and code-identifier nodes/edges. Imports remain proposals; after
  review the native projection reconstructs the same portable topology. It
  excludes identities and membership. Explicitly selected reviewed assertions can
  travel in the optional `relations` extension, with separate destination review.
- The opt-in `memory_graph` MCP tool returns native edges and eligible nodes.
  Existing installations still expose five tools; catalog-only installations
  still expose seven. Graph-enabled installations expose eight.
- Graph mode's `memory_search` now defaults to
  [native exact/full-text search and authorized graph expansion](falkor-memory-retrieval.md).
  It needs no embedding model; the catalog/vector baseline remains explicitly selectable.
- An optional [company evidence bridge](memory-company-bridge.md) projects exact
  source-version and lexical code matches into native paths. Use
  `sync-graph --include-company` and `memory_graph(include_company=true)`; both
  require current company access. Plain memory views do not expose these proxies.

## Enable and operate

Use a tenant configuration with an absolute `memory_db` and
`memory_graph_enabled: true`. The projection lives in
`tenant_<tenant-hash>_memory`, separate from the existing code graph and private
decision graphs. Runtime artifacts and conversation files must remain local and
ignored. This feature does not touch the approved demo database by default.

An example selected conversation file:

```json
{
  "format": "conversation/1",
  "session": "example-session",
  "turns": [
    {"id": "u1", "role": "user", "text": "Preserve unread payloads in `upload`."},
    {"id": "a1", "role": "assistant", "text": "I will inspect the implementation."}
  ]
}
```

Compute the digest of the canonical JSON using `brain.memory.canonical` and
`brain.memory.digest`. The existing operator CLI requires its separate interactive
operator session for consent, sharing, review and graph writes:

```sh
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml import-conversation /ABSOLUTE/PATH/conversation.json --consent-digest SHA256
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml review --brain private:alice --uid RECORD_UID --hash RECORD_HASH --action accept --reason 'Checked against the original turn'
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml share --uid RECORD_UID --hash RECORD_HASH --target team:backend
# Review the destination proposal independently, using its returned UID/hash.
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml sync-graph --brain private:alice
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml sync-graph --brain team:backend
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml graph-view --brain team:backend
```

Team membership still uses the existing operator `grant` command. A team reader
can inspect accepted shared memory but cannot synchronize the team projection.
In MCP, request `memory_graph(brains=["private:alice", "team:backend", "company"])`
only when all scopes are authorized. Omitting brains defaults to private memory.
Graph views do not write or synchronize anything.

## Freshness and privacy contract

Projection writes require owner/reviewer authority. Each brain is fenced before
replacement and published with a manifest of current records and membership.
Interrupted writes remain unavailable until a successful retry. Every read
checks all requested scopes before graph access, obtains current eligible rows
from a SQLite transaction, checks the manifest and validates native edges against
the authorized projection. A stale brain returns `incomplete` and no nodes for
that brain. Backend failure returns `unavailable` rather than a fabricated graph.

Revoke, reject, rollback, refresh and delete operations invalidate manifests.
Time-based expiry is filtered on every read even without a manifest change.
Hidden drafts cannot contribute nodes, edges or code-identifier paths to a reader.
There is no distributed transaction between SQLite and FalkorDB. Graph refresh
is explicit, not a background replication service. Successful sync purges old
nodes for the selected brain. Until sync, deleted prose may remain physically
in FalkorDB but is unavailable through this API. Direct database and Browser
access are trusted-operator capabilities and bypass application permissions.
Do not expose the raw database or Browser to team members as an authorized UI.
Existing trusted-local-operator storage/encryption limitations remain.

The namespace is tenant-wide rather than repository-specific, allowing portable
memories within one configured tenant/catalog. Use one authoritative catalog per
tenant; unrelated catalogs must use distinct tenant identifiers. Person node IDs
are scope-local proxies. Matching names do not automatically federate private
brains or identify GitHub accounts.

Bounds: 100 turns, 1 MB per selected conversation, 200 extracted assertions;
1,000 catalog records and 500 members per projected brain; ten requested brains,
500 nodes and 1,000 edges per brain view, 1,000 cross-brain citation edges.
Overflow fails explicitly. All prose remains untrusted and non-binding.

## Verification and next milestones

`tests/test_memory_graph.py` exercises exact consent, deterministic replay,
atomic conflict handling, span citations, selected sharing, authorization before
graph I/O, native live graph paths, cross-session mentions, hidden drafts,
membership revocation, stale refreshes, deletion, expiry, failure recovery and MCP.
Run `python scripts/validate_memory_foundation.py` for the complete suite on a
disposable FalkorDBLite engine; it shuts down its own engine with SAVE. The Docker
CI job now runs the live integration/memory suite too. CI has not been run merely
by adding the workflow step.

Local verification on October 17, 2026: **196 passed**, including live graph,
MCP and Lite lifecycle tests. The disposable owner stopped with SAVE. Ruff and
diff whitespace checks passed. The suite emits the existing third-party Authlib
deprecation warning. No fresh coding-agent comparison was performed.

Still outstanding:

1. Broadly evaluated semantic extraction/correction handling. The new opt-in
   model-selected literal spans/entities and explicit correction proposals are
   implemented, but one synthetic acceptance check does not establish general
   extraction quality or Supermemory equivalence.
2. Extend the tested `.abhi/2` record/assertion round trip to historical graphs
   and explicit origin authentication.
3. Graphify semantic extraction and FalkorDB GraphRAG/PDF extraction. The optional
   structural Graphify runtime adapter is implemented; see the [integration guide](graphify-three-brain-integration.md).
4. Broaden the implemented exact source/document/lexical code bridge with
   evaluated semantic resolution and agent planning. Approved constraints still
   come exclusively from the existing `check_change` contract.
5. Broader validation beyond the local permission-aware viewer and guided synthetic
   coding-agent demonstration now implemented, including production workflows proving
   use of these paths. MCP integration tests do not establish improved coding.
6. Hosted identity and storage hardening if deployment moves beyond a trusted
   local operator. Moving vectors to FalkorDB remains optional and unimplemented.
