# Memory foundation verification — 17 October 2026 (IST)

The optional local extension preserves the default five-tool prototype and
existing approved databases. The [roadmap](roadmap.md) is the authoritative
implemented/planned scope; this report records checks actually executed.

## Current backend checks

- **177 passed, zero failures/skips**, with real FalkorDB and Lite lifecycle
  flags enabled against a fresh disposable engine. Tests include SQL and physical
  graph tenant isolation, membership revocation, private proposals, MCP STDIO,
  atomic imports, CAS conflicts, session consent, document retirement/deletion,
  CRLF section identity, stale paths, expired/rejected/rolled-back decisions and
  a refresh fence starting between human review and approval mutation.
- Ruff and whitespace checks pass. Existing FastMCP/Authlib deprecation warnings
  remain; they do not fail the suite.
- A fresh locked Python 3.12 environment installed both Lite and memory extras
  and passed its offline selection (126 passed/35 live skips at `26cd6ab`). Later
  hardening adds tests and is covered by the final 177-test live run.
- Both old Browser and v5 reconstruction workflows passed on new empty engines.
  All eleven Browser database queries passed; all new demo rules remained
  proposed. No real approval phase or saved approved database was used.
- Frozen v5 snapshots, six patches, evaluation manifests, protocol, lifecycle/
  document exports and original demo patch are byte-identical to merged master
  `97a0974`. Their historical results are not reassigned to this new backend.

## Live acquisition and offline model

The [GitHub verification](github-sync-verification.json) used the real repository
and GET-only `gh` authentication on a disposable tenant graph: initial sync
captured three work items; a subsequent incremental sync captured zero and
advanced its cursor. Unit checks cover rate-limit/pagination/changed-file
failures, no cursor advance on failed publish and repository-ID reuse rejection.
Raw API bodies/configs remain ignored; no GitHub issue/PR was changed by the test.

The pinned all-MiniLM-L6-v2 artifacts loaded and encoded 384-dimensional vectors
with both Hugging Face/Transformers offline flags and socket connections blocked.
The model identity and artifact hashes are recorded locally. Runtime requires
local files and never downloads a replacement model implicitly.

## Retrieval outcomes

The [nine-query synthetic report](memory-benchmark.json) preserves each query,
input/model hashes and returned source identities. Warm latency excludes model
load and indexing. Conditions have different lexical semantics, so graph versus
hybrid differences are not solely embedding effects.

| Condition | Hit@3 | MRR@3 | Median milliseconds |
| --- | ---: | ---: | ---: |
| No retrieval | 0/9 | 0 | below 0.001 |
| Existing graph-only | 1/9 | 0.111 | 1.06 |
| Catalog full-text | 6/9 | 0.611 | 0.20 |
| Hybrid | 8/9 | 0.759 | 5.60 |

All returned excerpts match their named fixture sources; all supplied source
digests match those bytes. Citation coverage and returned-source integrity are
100% for returned items. This is source-delivery integrity, not proof of the
truth of generated answers. Small authored labels are not independent relevance
judgments or production performance evidence.

## Coding outcomes

Both tasks are small synthetic Python repairs with identical visible policy,
source, prompt and environment in each arm. Local policy files/hashes are the
authority; illustrative fixture GitHub URLs are not claimed as public sources.
The external oracle was created outside each checkout only after agent exit.
One run/task/condition is anecdotal.

| Corrected protocol at `31b58dc` | Successful tasks | Company memory before edits |
| --- | ---: | --- |
| No brain | 2/2 | Not available |
| Graph-only | 2/2 | Not available |
| Hybrid | 2/2 | Both sessions |

The [call/outcome report](memory-agent-evaluation.json) includes invalid legacy
scope attempts and empty graph keyword results. Every session reread POLICIES.md
after editing. Median measured session-plus-oracle time was 42.10s, 40.47s and
46.64s respectively; cache effects, co-resident validation and n=1/task limit
interpretation. **No coding correctness or speed advantage is established.**

The [six earlier pilot attempts](memory-agent-pilot.json) are also retained.
Their patches passed, but hybrid sessions searched empty private scope. Those
are workflow failures for company-memory use, not successful hybrid retrieval.
Fresh corrected sessions received no previous patches or evaluator feedback.
Final stale-document/backup/refresh-fence/CRLF hardening followed the measured
coding revision and passed the live suite; no newer coding advantage is claimed.

## What remains planned

[Parser component results](parser-comparison.json) cover actual deterministic
Graphify and GraphRAG chunking. Full GraphRAG semantic entity/community extraction
has not been evaluated. Hosted authentication, distributed membership/sync,
automatic deletion-ledger replay on restore, online graph migrations, ANN-scale
retrieval and broader independent coding/relevance benchmarks remain planned.
Neither this extension nor its tests certify hostile local-admin isolation,
complete prompt-injection immunity or a production privacy/compliance system.
