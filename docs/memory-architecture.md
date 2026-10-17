# Opt-in local memory architecture

## Compatibility and authorities

With no `memory_db`, `python -m brain.mcp_server` still registers exactly
`get_context`, `check_change`, `trace_decision`, `find_owner` and `remember`.
The historical demo defaults to `org_demo` and `private_<principal>` unchanged.

With `tenant_id` configured, graph names gain a SHA-256-derived tenant prefix.
This opens a separate namespace; it never migrates or mutates the old graph.
With `memory_db` configured, the server also registers `memory_search` and
`memory_propose`. Configured tenant and principal select identity; there are no
principal, tenant, arbitrary graph, arbitrary SQL or Cypher tool arguments.
Org operations additionally require a current company grant. Private operations
use the configured principal. Team membership is an operator-owned catalog row,
not something inferred from repository prose, CODEOWNERS or an imported file.
Legacy context/trace/impact reads also require company membership because they
consult the configured code graph's revision; private catalog search does not.
Tenant MCP startup refuses a missing catalog or a graph/catalog identity mismatch.
Tenant-only configuration remains available to operator ingestion commands.

FalkorDB remains authoritative for code, historical relationships and applicable
approved decisions. SQLite is a sidecar authority for memory ownership, proposals,
membership, source text, audit, refresh transactions and derived vector data.
There is no claim of an atomic distributed transaction between the two stores.

## Ingestion

Native graph document versions preserve revision/line-bound UIDs and immutable
Source references. `stable_id` adds logical heading/occurrence/chunk identity
independent of preceding line movement. Fenced Markdown examples do not become
headings. RST/Sphinx references and exact PR numbers retain existing resolution.
Refresh marks a Project unavailable before writes; success retires obsolete
sections and releases the fence. A failed refresh stays unavailable until rerun.
`retire-docs` removes active mention edges but preserves historical Sources.

Catalog document ingestion preflights selected `.md`/`.rst` paths and all size
bounds, then atomically replaces their sections. Removed sections lose searchable
text/vectors. The stable key is path + heading occurrence + chunk ordinal: a
heading rename, insertion of an identical earlier heading or changed chunk
boundary can change an ID. IDs do not claim semantic equivalence after arbitrary
edits. Citations contain exact line ranges and SHA-256 of the cited excerpt.

`sync-github` uses the operator's existing `gh` authentication for GET requests
only. It verifies repository identity, uses pagination with hard bounds, overlaps
the prior cursor by five minutes, polls issues and updated PRs, and captures full
comment/review/changed-file lists for touched parents. It downloads everything
before publishing. A failed graph write keeps `github_syncing=true`; retry
reconciles the same parents before advancing the cursor. New Sources have content
hash suffixes, so refreshed prose cannot overwrite previously reviewed evidence.
Periodic `--reconcile` is required for child edits/deletions not reflected in parent
timestamps. API caps and incomplete changed-file counts fail closed. Private repo
capture requires a tenant namespace; raw captures must stay ignored and private.

Session imports accept only `session/1` curated memory strings with a consent
digest covering the exact export. No raw trace reader or background collector
is installed. Imported entries remain private proposals. Team `.abhi` files can
propose content, but cannot assert membership, accepted state or approval.

## Retrieval

The selected model is
[sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2),
Apache-2.0, 384 dimensions. The explicit provisioning script pins a Hub commit,
materializes safetensors/tokenizer/config artifacts and records their hashes.
Runtime checks every artifact, sets `local_files_only=True` and
`trust_remote_code=False`, and runs on CPU. It makes no model-download request.
The [SentenceTransformer API](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html)
documents these local-loading controls. Text longer than a model window is split
into overlapping 224-token chunks and mean-normalized; this is an engineering
choice, not a measured semantic optimum.

The vector index is an exact cosine flat index stored as normalized vectors in
SQLite. No extension daemon, paid service or external vector database is required.
[SQLite's deliverable engine is public domain](https://www.sqlite.org/copyright.html);
the flat-ranking code is implemented in this repository, without a separate ANN SDK.
Authorization, tenant, state and expiry filtering happen before scoring. Each
request builds an eligible-only [FTS5](https://sqlite.org/fts5.html) view so hidden
or expired text cannot affect candidate cutoffs or BM25 statistics. RRF combines
exact, full-text and vector rankings; optional graph evidence joins by cited URI.
The graph's existing full-text term semantics differ from catalog OR queries,
so a graph-vs-hybrid difference is not attributed solely to embeddings.

The query bound is 10,000 eligible records per brain, ten requested brains and
twenty returned results. Overflow fails explicitly. A model/hash change requires
operator reindexing; vector-only queries refuse missing/mismatched vectors and
hybrid queries warn. Results carry source digest/URI, state, scope, truncation
and `binding=false`. Only existing `check_change` can return binding constraints.

## Codex contract

Before edits: inspect local code; identify targets; call `check_change`; retrieve
relevant company and permitted personal/team context; open cited files or source
excerpts; distinguish source facts, proposed notes and approved constraints.
Record IDs, hashes, source lines and any incomplete/unknown responses in the plan.
After edits: reread affected evidence, verify source hashes/line ranges, rerun
relevant tests and `check_change`, and explain which evidence influenced the edit.
A stale citation requires a new plan; it is not confirmation that a rule vanished.

The existing experiment runner adds read-only `memory_search` only with
`--memory-search`. Both `remember` and `memory_propose` remain disabled in that
condition. Agents cannot call ingestion, membership, review, approval, deletion,
backup, migration or restore tools. These are separate human operator commands.

## Limits

Code preflight caps indexing at 5,000 Python files, 1 MB/file and 20 MB total,
before graph mutation. Document and query bounds remain explicit. Existing
callers traverse at most two reverse CALLS hops. Runtime dispatch, inheritance,
ambiguous modules, wildcard/conditional imports and rebound symbols remain
unresolved; self/cls edges remain heuristic. No absent edge proves absence of
dependencies. Graphify's broader structural coverage is a comparison target,
not justification to silently convert speculative edges into approved facts.
