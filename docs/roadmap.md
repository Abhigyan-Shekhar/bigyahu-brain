# Company Brain: implementation and target architecture

This is the current scope record. The event-era v3 plan, implementation guide,
backend progress logs and v5 experiment reports are historical records, not a
claim that the entire target architecture already ships in the prototype.

The preserved foundation is FalkorDB code/Git/history ingestion, five default
MCP tools, human decision approval and the reproducible Codex demonstration.
The optional local memory extension adds a separate SQLite catalog for private,
team and company evidence, transactional imports, access policy and vectors.
It does not replace FalkorDB relationships or promote memory to binding policy.

| Capability | Current implementation | Remaining qualification |
| --- | --- | --- |
| Code/Git, ownership, GitHub snapshots | Existing FalkorDB ingesters | Python only; bounded static relationships |
| Markdown/RST | Native graph sections plus optional catalog ingestion | Heading/duplicate/chunk IDs have documented limits; no semantic policy extraction |
| Document refresh/deletion | Graph refresh fence and logical retirement; catalog transaction and text/vector erasure | Graph historical Sources remain for reviewed citations; erasure is an operator procedure |
| Incremental GitHub | Read-only paginated API acquisition, overlap cursor, reviews/comments/files reconciliation, immutable Source versions | Bounded single writer; periodic full reconciliation required; not a webhook service |
| Personal memory | Private proposals; consented imports; explicit identifier extraction; version-pinned reviewed UPDATES/EXTENDS/RELATES_TO assertions | Opt-in model-selected durable spans/literal entities and explicit correction proposals; unrestricted semantic correction remains unimplemented; no automatic harvesting of logs, email, chat or browser activity |
| Shared team memory | Selected sharing; `.abhi/1` imports; `.abhi/2` record/assertion round trips; operator membership and CAS conflicts | History graph export and cryptographic origin authentication remain unimplemented; local STDIO trust |
| Native memory graph | Opt-in FalkorDB people/team/memory paths, reviewed assertions, citation links and exact company source/document/lexical code bridges | Explicit refresh; catalog retains record/permission authority; source-grounded named concept mentions now supported; no arbitrary semantic identity resolver; local authorized viewer and guided synthetic coding demo now implemented |
| Document concepts | Explicit model-selected literal spans; checked named-mention paths to company sources; labels survive selected sharing | No inferred aliases/identity or model-backed code constraints; current-view bounds remain |
| Graphify | Optional pinned structural runtime adapter with cited advisory relationships | Semantic pass and PDF extraction remain planned; Python AST call authority is preserved |
| Company access | Server tenant identity, tenant-specific FalkorDB names and company grants | Legacy default demo mode is single-user and must not be exposed as a tenant service |
| Retrieval | Graph mode defaults to native Falkor exact/full-text plus authorized four-hop frontier expansion; explicit catalog lexical/vector baseline retained | Native views bounded at 1,000 eligible nodes; vectors remain catalog-based; no general quality/scaling advantage claimed |
| Embeddings | Optional pinned all-MiniLM-L6-v2, CPU/offline, 384 dimensions | English short-text model; domain/multilingual evaluation remains planned |
| MCP | Five default tools; opt-in `memory_search` and `memory_propose`; graph mode adds `memory_graph` | Approval, grants, review, deletion, backup and ingestion remain outside MCP |
| Review | Evidence/text/subjects/reviewer audit, expiry, rejection, revocation rollback and supersession | Memory acceptance is evidence review, never a code constraint; rollback does not auto-reactivate an older rule |
| Security tests | Private/team/tenant isolation, revoked membership, incomplete import recovery, injection stays untrusted | No claim of hostile local-admin isolation or a complete redaction/DLP system |
| Evaluation | Frozen six-session urllib3 report retained; new retrieval and parser component benchmarks | Small synthetic benchmark is not general agent-performance proof; see new evaluation protocol |
| Operations | Schema version gate, transactional catalog, backup, health, restore procedure, retry fences | Distributed sync, online cross-engine migrations, hosted auth and HA remain planned |

## Delivery order and acceptance

1. Preserve the old clean setup and five-tool contract. Use new disposable engines
   and an opt-in config for every extension test. Never rebuild the approved graph.
2. Validate refresh, deletion, crash recovery, CAS conflicts and scope enforcement
   before enabling memory tools. Every result retains citations and untrusted status.
3. Measure retrieval against graph-only and lexical baselines, and code outcomes
   against no-brain and graph-only conditions. Preserve every attempt and failure.
4. Evaluate domain embeddings and approximate indexes only after measuring the
   current bound. Compare Graphify and GraphRAG on exactly identified components;
   do not equate token chunking with semantic entity extraction.
5. Add hosted authentication, federation, webhooks and distributed administration
   as separate reviewed projects. This local extension is not production hosting.

Read [architecture](memory-architecture.md), [operations](memory-operations.md),
[governance](memory-governance.md), [.abhi format](abhi-format.md) and
[evaluation protocol](memory-evaluation.md) for precise contracts.
