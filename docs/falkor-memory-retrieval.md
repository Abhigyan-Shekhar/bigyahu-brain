# FalkorDB memory retrieval

Graph-enabled servers now use FalkorDB for exact/full-text memory search and
native graph expansion. This path requires no embedding model. SQLite remains
the record, permission, review and audit authority; it does not perform lexical
or vector ranking for the Falkor backend.

## Routing and compatibility

`memory_search` accepts `backend="auto"`, `"falkor"` or `"catalog"`.

- `auto` selects Falkor when `memory_graph_enabled: true` is configured; otherwise
  it preserves catalog retrieval.
- `falkor` requires an enabled, current projection and a native full-text index.
  A missing or stale projection/index returns `incomplete`; backend failure
  returns `unavailable`. There is no silent fallback to a different scope or engine.
- `catalog` explicitly preserves the existing exact/FTS5/optional-vector hybrid
  path for comparison. `include_graph=true` retains its legacy company-source fusion.

No new MCP tool is added. The legacy default server still has five tools,
catalog mode has seven, and graph mode has eight. Existing installations without
graph mode retain their retrieval behavior. Graph mode's `auto` route now changes
from catalog search to the embedding-free native route; callers needing the
existing semantic-vector behavior can explicitly select `catalog`.

Native `include_graph=true` requests the verified company bridge and requires
current company access. It uses refreshed source/document/lexical code projections
rather than the catalog backend's legacy `get_context` fusion. Native responses
identify their backend and return a bounded nodes/edges evidence graph.

## Retrieval flow

1. Begin a catalog transaction and authorize **all** requested brains, plus company
   access when requested. Validate current record/link visibility, expiry and
   projection freshness. An incomplete requested scope prevents a partial ranking.
2. Find exact candidates through graph UID, record UID, citation URI, explicit
   entity name, company UID or indexed path.
3. Query the native `MemoryNode` full-text index over `text` and `name`. Input
   becomes at most twenty literal word tokens joined with OR. Raw query syntax,
   SQL and Cypher are never accepted from the caller.
4. Restrict candidates to currently eligible node UIDs **before** query-local
   ranking and candidate limits. Rank lexical candidates by the number of query
   terms occurring in their text/name, then UID for deterministic ties. FalkorDB
   corpus-wide relevance scores are deliberately ignored: hidden or expired
   records must not change authorized document-frequency statistics or ranking.
5. Expand native Cypher paths up to four hops, allowing only eligible nodes and
   visible assertion UIDs. Relationship types are explicitly allowlisted. Shared
   authorship/brain containers are excluded from expansion so unrelated notes
   are not retrieved simply because they have the same author.
6. Fuse exact and full-text seed ranks with reciprocal-rank contributions. Exact
   seeds have weight three; each graph hop halves a contribution. A memory gets
   at most its best contribution per channel, preventing many incidental paths
   from inflating its score.
7. Return ranked memory records with exact citations, one supporting native path,
   edge directions, assertion UIDs, retrieval channels and a bounded evidence
   neighborhood. Endpoint eligibility is rechecked before returning to catch expiry
   while queries run. Joined company searches also recheck the completed revision.

`updated_by` identifies eligible reviewed incoming `UPDATES` assertions. The
original record remains independently retrievable; retrieval does not silently
erase it or interpret an assertion as a binding code constraint. Evidence remains
untrusted and `binding=false`.

Falkor's full-text index API is documented in the
[official full-text reference](https://docs.falkordb.com/cypher/indexing/fulltext-index).
This implementation uses native matching and graph traversal with its own
scope-safe ranking policy; it does not claim to use native BM25 or an LLM semantic
resolver.

## Enable and query

Use the existing tenant configuration with `memory_db` and
`memory_graph_enabled: true`. Omit `embedding_model_dir` for an entirely
embedding-free deployment. A configured encoder still supports existing memory
ingestion and the explicit catalog baseline; the native query path never calls it.

Run the existing operator sync once to create/repair the index. Old projections
without an index require this refresh; queries never create indexes or mutate data.

```sh
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml sync-graph --brain private:alice
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml search --query 'upload replay' --backend falkor
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.yaml search --query 'upload replay' --backend catalog
```

For company paths, sync with `--include-company`, then search with `--include-graph`.
Repeat `--brain` to select multiple authorized brains. Omitting brains defaults to
the configured principal's private brain. MCP uses the corresponding existing
`memory_search` parameters. Shared citation paths can connect selected personal,
team and company memory scopes; unrequested scopes cannot contribute candidates.

## Bounds and trust

Native retrieval permits ten selected brains but at most 1,000 eligible nodes and
2,000 edges across the requested view. Each seed channel returns at most fifty
candidates; at most fifty fused seeds are expanded. Candidate cutoff is reported.
More than 1,000 expansion paths returns `incomplete` and requires a narrower query.
At most twenty memory items are returned, with 2,000 characters of item text each.
Evidence context has at most 200 nodes and 400 edges. Supporting retrieval edges
are retained when trimming context. Node snippets are at most 1,000 characters,
with a total context-text budget of 16,000 characters and explicit truncation flags.

Visibility/freshness is determined from the catalog and validated native graph.
No query executes imported text, approves a decision or exposes administrative
operations. The catalog transaction serializes cooperating catalog writers and
projection synchronizers; it is not a distributed transaction across all company
ingestion processes. Direct local database access remains trusted-operator access.
There is no hostile-local-admin or timing-side-channel isolation claim.

## Evaluation

The [vector comparison](falkor-memory-vector-comparison.json) reports three modes
on the same disposable engine and synthetic corpus:

| Corpus group | Catalog exact/full-text | Native exact/full-text/graph | Catalog hybrid with local vectors |
| --- | --- | --- | --- |
| Existing nine natural-language queries: Hit@3 | 6/9 | 6/9 | 8/9 |
| Three authored graph acceptance queries: Hit@3 | 0/3 | 3/3 | 1/3 |

The natural-language group is evaluated before the extra graph fixtures are
added. The graph acceptance questions intentionally depend on reviewed
`UPDATES`/`EXTENDS` paths or a shared explicit identifier. They demonstrate path
retrieval, not independent evidence of general relevance quality.

These results support keeping embeddings optional. Native graph retrieval
provides useful relationship context, while the local vector baseline finds more
paraphrased questions in this tiny corpus. No combined native graph+vector mode
or native vector index is implemented here. The existing local-vector baseline
still stores/scores vectors in SQLite. Moving vectors into FalkorDB requires a
separate eligibility-safe design and evaluation; unrestricted ANN top-k followed
by permission filtering is not an acceptable substitute.

The reports include measured single-query latency (including native graph
validation), corpus/implementation hashes, model identity and per-query outcomes.
Native graph validation was slower than catalog lexical search on this small
fixture. Index/model loading is excluded. No production-scale performance,
agent-coding advantage or new semantic extraction quality is claimed.

Reproduce on a disposable engine:

```sh
PYTHONPATH=src python scripts/benchmark_falkor_memory.py --output /ABSOLUTE/PATH/retrieval.json
PYTHONPATH=src python scripts/benchmark_falkor_memory.py --model-dir /ABSOLUTE/PATH/minilm-v1 --output /ABSOLUTE/PATH/vector-comparison.json
```

`tests/test_falkor_memory_search.py` covers authorization before graph access,
exact/native full-text matching, reviewed and shared graph paths, hidden-draft
ranking invariance, expiry, revocation, stale content, index repair, literal-query
safety, text limits, MCP/company paths and absence of embedding/catalog search
calls in the native backend.

Local verification on October 17, 2026: **249 tests passed** in the complete
disposable FalkorDB/Lite suite. Engine owners stopped with SAVE. Both benchmark
reports were reproduced against the final implementation, and all recorded
implementation hashes match. Earlier benchmark attempts remain in ignored local
validation artifacts. Ruff, whitespace and publication/history scans passed.
The existing third-party Authlib deprecation warning remains. No approved demo
graph or frozen coding-trial artifact was modified, and no new coding-agent
comparison was executed.
