# Graphify and three-brain integration milestone

This milestone addresses the runner/tool gap and adds a fresh guided agent run,
a structural Graphify runtime adapter, optional semantic conversation selection,
frontier traversal and a local authorized viewer. Existing approved demo databases
and frozen urllib3 trials are unchanged.

## Graphify is now a runtime option

Install `uv sync --frozen --extra graphify`. With `BRAIN_CONFIG` pointing at a
clean committed checkout that has already completed `python -m brain sync`, run:

```sh
uv run --extra graphify python -m brain ingest-graphify src/example.py
```

Omitting paths selects supported tracked code files. Version `graphifyy==0.9.92`
is pinned in the optional dependency and lock file. The worker checks that version,
copies selected inputs into an isolated temporary snapshot, passes explicit
`root` and external `cache_root`, and runs deterministic extraction without a
semantic/model pass. See the upstream [extraction API and output schema](https://github.com/Graphify-Labs/graphify/blob/86c57be8204673c2a1b9849a3292a7dd3ab373d8/ARCHITECTURE.md).
The earlier comparison-only result remains historical; this command is a new
runtime adapter using the extractor package itself.

All output is validated before graph writes: tracked input paths, unique IDs,
bounded line ranges, source bytes, endpoint references and confidence categories.
The adapter stores current revision-pinned `Document` evidence with
`source_kind=graphify_structural`, immutable line citations, and fixed
`EXTRACTED_RELATION` edges. Original relation/confidence remain properties;
missing edge locations explicitly use weaker origin-node context. `get_context`
returns citations and these advisory relationships, including their upstream
relation names. Re-import is idempotent; failures during writes leave a readiness
fence until retry. Selected file refresh retires older evidence.

Graphify does not replace the Python AST `CALLS` authority or approve constraints.
`EXTRACTED`, `INFERRED` and `AMBIGUOUS` remain extractor claims, not application
review. No Graphify semantic pass, arbitrary document-concept resolver, FalkorDB
GraphRAG SDK pipeline or PDF integration is claimed. Current bounds are 500 input
files, 10 MB total input, 10,000 nodes and 20,000 relationships; no large-repository
performance claim follows.

## Opt-in semantic conversation extraction

Deterministic `conversation/1` import remains compatible. An explicit model
selection opts into sending only the selected, exactly consented envelope to a
fresh Codex process:

```sh
python -m brain.memory_cli --config /ABSOLUTE/PATH/memory.local.yaml \
  import-conversation /ABSOLUTE/PATH/selected.json \
  --consent-digest EXACT_ENVELOPE_SHA256 --semantic-model gpt-6.1-sol
```

The operator's existing exact-consent confirmation remains required. This mode
uses the existing Codex authentication, may consume account model usage, and
requires Codex CLI support for structured output. It is not local-model inference.
No model call occurs before consent/envelope validation. The child process ignores
user configuration, disables plugins/apps/shell/multi-agent tools and web search,
and runs read-only in an empty temporary directory. It has no memory/catalog
access; the explicit envelope is its only conversation input.

The model selects durable decisions, preferences, constraints and explicit
corrections. Every candidate must cite an exact user-only Unicode span; literal
entities must occur inside that span. Assistant assertions, invented entities,
questions, invalid offsets and conflicting replay metadata are rejected. Casual
turns may yield no candidate. Selected facts stay verbatim proposals, and model,
kind, entities and exact record hash are recorded for audit. Literal entities are
projected as mentions under current visibility, never entity-identity proof.

An `UPDATES` proposal requires a model-classified correction, an explicit correction
cue and exactly one accepted prior private record sharing a backticked subject.
Ambiguous targets abstain. The relationship pins both versions and still needs
separate review; the old record remains retrievable. This is conservative correction
assistance, not arbitrary semantic contradiction resolution. Semantic annotations
are local audit/projection metadata and are not yet portable in `.abhi/2`.

A live synthetic extraction check selected the decision and correction while
excluding casual chat and the assistant assertion. See [recorded check](conversation-semantic-verification.json).
That small acceptance fixture does not establish general extraction accuracy.

## Frontier traversal and local graph viewing

Retrieval now issues at most four native one-hop frontier queries. Each seed
visits an eligible node at most once; shortest supporting paths suffice for the
existing hop-decayed ranking. Native adjacency is checked against the current
permission-filtered projection. A 10,000 seed/node-state budget replaces the old
1,000 enumerated-path cap. Eligible-view and other output bounds remain in force.
The [10/50/100-memory stress check](memory-frontier-evaluation.json) reports actual
query counts and latency; it is not enterprise validation. Original synthetic
retrieval Hit@3 results remain unchanged in the regenerated reports.

```sh
python -m brain.memory_viewer --config /ABSOLUTE/PATH/memory.local.yaml
```

Open the session URL printed by the viewer. It binds only to `127.0.0.1`, fixes the
principal from operator configuration, requires a per-launch bearer token for
API reads and rejects foreign Host/Origin headers. The token is supplied through
the URL fragment and removed from the visible URL; reopen the launch URL after
reload. API responses and assets are not cached. The UI uses text-only rendering
for source prose and a restrictive content policy.

Scopes are derived from the current principal's catalog grants. Each graph read
passes through `memory_graph`, with current authorization, expiry and projection
checks. Clicking a person lists authored memories only in the selected visible
scopes; it never opens another private brain. Proposals are not exposed. Keyboard
selection is supported. This is a local fixed-principal viewer, not a hosted
identity system or protection from local administrators.

## Fresh agent demonstration and reproduction

```sh
uv sync --frozen --extra lite --extra graphify --python 3.12
PYTHONPATH=src .venv/bin/python scripts/demo_three_brain.py \
  --model gpt-6.1-sol --reasoning high
PYTHONPATH=src .venv/bin/python scripts/verify_three_brain.py \
  --run /ABSOLUTE/PATH/TO/PRINTED/LOCAL/RUN \
  --output /ABSOLUTE/PATH/verification.json
```

The script starts a disposable Lite owner and builds a committed synthetic retry
repository. It ingests code, a policy document and Graphify evidence, imports a
selected conversation with exact synthetic consent, attaches a verified policy
citation as explicit fixture curation, reviews only synthetic records, and shares
the selected record into team/company proposals before synthetic review. Another
developer's private canary is deliberately excluded from authorized scopes.

A fresh Codex process receives only the coding task and tool-use guidance.
`--memory-graph` explicitly enables search and inspection while excluding write
operations. It retrieves a private memory, inspects private/team/company links and
verified company policy before changing the retry implementation. A separate
verifier checks trace results, citation bytes, retrieval-before-recorded-edits,
canary exclusion, unchanged policy, agent tests, and 15 independent oracle cases.
The original fixture fails that same oracle. See [verification](three-brain-agent-verification.json).

This is a guided synthetic integration demonstration. It explicitly asks the
agent to inspect those scopes/tools; it is not spontaneous discovery, a baseline
comparison, a real organization deployment or proof of improved coding performance.
The requested model is recorded but not independently attested. Raw traces,
configs, model output and database state stay in ignored local validation storage.
Source hashes record the uncommitted backend used at launch; the fixture revision
is independently committed. Later edits can be compared with those hashes.

## Verification

The full disposable Lite suite passes 267 tests, including actual pinned Graphify
extraction and native graph retrieval. Focused tests cover runner configuration,
semantic provenance/consent/correction proposals, dense-cycle frontier behavior,
viewer bearer/origin/scope boundaries and the existing privacy regressions.
The Docker regression job installs the Graphify extra so these live extractor
checks run in CI. New CI results are not implied by local verification.
