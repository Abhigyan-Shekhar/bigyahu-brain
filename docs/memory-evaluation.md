# Memory evaluation protocol and component comparison

## Retrieval

`benchmarks/memory-retrieval.json` fixes eight synthetic documents and nine
queries, with one relevant source per query. Run
`scripts/validate_memory_foundation.py --model-dir <local-model> --benchmark-output <report>`
against its automatically allocated disposable engines. It compares no retrieval,
the existing graph-only `get_context`, catalog full-text and hybrid retrieval.
Report hit@3, MRR@3, citation coverage and warm-query p50/p95 latency; indexing
and model startup are excluded. No query, failed outcome or corpus item is removed
after execution. Small authored labels are not independent relevance judgments.

The [measured retrieval report](memory-benchmark.json) records actual model/input
hashes and every query result. Graph search and catalog lexical semantics differ;
compare catalog lexical/hybrid separately before attributing a change to vectors.
Citation coverage means references were returned, not proof of every downstream
natural-language claim. Unit/live tests additionally verify immutable hashes,
scope filtering, stale updates, revocation, expiry, deletion and injection boundaries.

## Coding agents

The [pilot](memory-agent-pilot.json) retains six completed sessions at backend
`26cd6ab`. Every patch passed its external oracle, but both hybrid sessions
omitted `brains=["company"]` and returned zero memory items. They demonstrate
tool invocation and coding success, not use of hybrid memory. No pilot run was
overwritten or omitted. The corrected protocol fixes scope guidance in both the
tool description and common instructions, before starting a new six-session set.
It supplies no prior patches, oracle feedback or known solutions to fresh agents.

`benchmarks/agent-tasks.json` fixes two synthetic Python tasks, initial sources,
visible tests, policies and an independent evaluator. Run one fresh session per
task/condition: no brain, graph-only, hybrid. Each condition sees the same source
and policy files, identical prompt/instructions, model/reasoning, limits and test
interpreter. Hybrid adds only read-only `memory_search`; no experiment enables
memory writes, approval, administration or outside information.

`scripts/benchmark_agents.py` creates fresh repositories and a disposable engine.
It supplies common instructions, captures real Codex JSON events/patches and runs
an external oracle after agent exit. Raw logs remain ignored; the reviewed report
records every trial, independent outcome, selected MCP calls, elapsed time and
patch hash. A transport success is distinct from retrieval relevance, model use
or coding success. One run/task/condition is anecdotal; do not claim significance
or production benefit. A synthetic policy task is not a replacement for the
historical frozen [urllib3 comparison](v5-evaluation.md), which is left untouched.

## Parser comparison

The [component report](parser-comparison.json) pins
[Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) and
[Microsoft GraphRAG](https://github.com/microsoft/graphrag) revisions, input hashes
and measured timings. Inputs include imported Python calls/inheritance, Markdown
with fenced code, Sphinx RST, and the public #5161/#3780 PR bodies already included
with retained urllib3 attribution/license. It runs deterministic Graphify
extraction and GraphRAG's actual TokenChunker; neither invokes an LLM or uploads
the corpus. The shared codepoint tokenizer isolates chunk mechanics.

The current measured fixture yields six Company Brain symbols, two resolved
calls and one unresolved inherited call. Graphify yields 21 nodes/25 relationships,
including `inherits` and three `calls`; its returned source-file list includes
Markdown but not the RST fixture. GraphRAG tokenizes every input as text chunks,
not a code AST or independently source-grounded PR graph. Counts use different
schemas and cannot be treated as comparative precision/recall or correctness.

[GraphRAG's semantic indexing](https://microsoft.github.io/graphrag/index/overview/)
extracts entities and relationships with model-based workflows. That full pipeline
has **not** been measured here. A future semantic comparison must pin model,
prompt, extraction budget, inputs and gold links; report inferred versus exact
links, false links, source offsets, cost and latency. Do not replace it with
token chunk counts or claim an accuracy winner from this component test.
