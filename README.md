# Company Brain

**An engineering agent that connects code, documents, decisions and reviewed team knowledge in FalkorDB—and shows the sources behind a proposed change.**

Company knowledge is scattered across repositories, issues, PR discussions and documents. Company Brain brings those connections into a local React/FastAPI workspace: ask about a bug, inspect the evidence and graph paths, review a fix plan, then approve an isolated patch with before/after test results.

**Graph Hacks 2026 · Track 03: Company Brain**

| Submission item | Where to find it |
| --- | --- |
| Public source code | [Abhigyan-Shekhar/bigyahu-brain](https://github.com/Abhigyan-Shekhar/bigyahu-brain) |
| Working-project walkthrough | [Captioned MP4](docs/submission-demo/walkthrough.mp4) · [captions](docs/submission-demo/captions.srt) · [receipts and patch replay](docs/submission-demo/README.md) |
| Run the product | [Complete local setup](#run-locally) below; no hosted deployment is required for this local application |
| Graph data model | [Nodes, edges and provenance](#graph-data-model) |
| Cypher and retrieval | [Queries the product depends on](#cypher-and-graph-retrieval) |
| Original work and AI assistance | [Disclosure](#original-work-data-and-ai-assistance) · [NEW_WORK.md](NEW_WORK.md) |

The included video is a **100-second edited, captioned walkthrough of captured application states**, with waits omitted; it is not continuous screen recording. It shows investigation, evidence, approval, patch and test results. A separately hosted final recording can be added later.

## Why this fits Company Brain

| Track focus | Implemented in Company Brain |
| --- | --- |
| Connected company knowledge | Public repository code, Git history, bounded GitHub issue/PR discussions, repository docs and uploaded Markdown/RST/PDF/DOCX feed a company graph. |
| Who owns what | CODEOWNERS rules, Git authorship and recorded PR reviews provide explicit ownership or clearly labeled maintainer evidence. |
| Trace decisions to their sources | Decisions link to source excerpts and constrained symbols; supersession preserves the earlier decision and its evidence. |
| Keep knowledge current | Revision and source-byte checks identify stale evidence; manual sync/reconciliation refreshes snapshots. Personal/team records support review and revocation. |
| Answers with clear sources | Clickable citations reopen original text and native FalkorDB paths. The server checks quoted bytes, permissions and provenance. |

Personal Brain and Team Brain extend the company workflow with selected, reviewed knowledge. Portable `.abhi/2` files transfer selected records and relationships for independent review. This submission enters **Company Brain**; these supporting features do not imply entry into another track.

## What the working product does

1. **Connect a public repository.** Onboarding clones a bounded checkout, indexes Python structure and Git history, imports a partial public GitHub history sample, and runs Graphify structural extraction.
2. **Add company documents.** Upload supported documents and inspect extraction status, original text and advisory semantic relationships.
3. **Investigate in chat.** A read-only Codex agent chooses code, impact, ownership, history and authorized memory tools. Published claims carry checked quotations and source IDs.
4. **Inspect the graph.** Follow actual callers, source relationships and reviewed memory links behind the answer.
5. **Review a fix plan.** Inspect claims, affected files and exact supported Python test commands before approving execution.
6. **Compare and export.** Editing happens in an isolated clone. Inspect original versus patched test output and download the Git patch. Any new lesson remains a proposal until reviewed.

[Application guide](docs/company-brain-app.md) · [Approved coding actions](docs/company-brain-actions.md) · [Personal Brain](docs/personal-brain-app.md) · [Team Brain](docs/team-brain-app.md) · [Portable memory](docs/abhi-app.md)

## Run locally

To use graph evidence directly in an existing Codex chat, see
[Native Codex skill and MCP setup](docs/codex.md). It supports an already indexed
checkout or CLI initialization without the web application.

The supported product is a **single trusted operator's local application**, bound to loopback. You need Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), Python 3.12, Node.js **20.19+ or 22.12+**, npm, an installed/authenticated Codex CLI with access to the selected model, and an authenticated GitHub CLI (`gh auth login`). Model calls consume your configured account's usage. No embedding model is required for native graph retrieval.

Use macOS or Linux for the Lite path. On macOS, install its runtime prerequisite with `brew install libomp`. Native Windows Lite is unavailable; use Docker Desktop Linux containers or WSL. Approved editing/tests additionally require a supported Codex OS sandbox; Windows patch-portability checks do not establish native Windows execution support.

### 1. Install the application

```sh
git clone https://github.com/Abhigyan-Shekhar/bigyahu-brain.git
cd bigyahu-brain
uv sync --frozen --extra app --extra lite --extra graphify --extra ingestion --python 3.12
npm ci --prefix frontend
npm run --prefix frontend build
```

### 2. Start FalkorDB

In terminal 1, from the repository root:

```sh
uv run --frozen --extra app --extra lite python scripts/run_lite.py \
  --db data/runtime/company-brain-app/brain.rdb --port 6398
```

Leave this process running. Wait for its `status: ready` output. Use exactly one Lite owner per database; keep the entire runtime directory for persistence. Ctrl-C saves and stops the engine.

**Docker alternative:** install the same application extras without `--extra lite`, then run `docker compose up -d` instead of the Lite command. The pinned container exposes FalkorDB on `127.0.0.1:6379`; use `port: 6379` in the next step. Do not run both engines on the same port. The Docker image is FalkorDB 4.14.7; the recorded Lite integration used graph module 4.18.3.

### 3. Configure and launch

In terminal 2, from the repository root, create an ignored local configuration with the current absolute checkout path:

```sh
uv run python - <<'PY'
from pathlib import Path
import yaml
Path('config/app.local.yaml').write_text(yaml.safe_dump({
    'repo_root': str(Path.cwd().resolve()),
    'repo_id': 'app-connection-template',
    'principal': 'app_operator',
    'host': '127.0.0.1',
    'port': 6398,
}))
PY

uv run --frozen --extra app python -m brain.app.server \
  --config "$PWD/config/app.local.yaml" \
  --data "$PWD/data/runtime/company-brain-app/sources" \
  --model gpt-6.1-sol --port 8787
```

Choose a model available to your authenticated Codex account if needed. Open the **Open locally** session URL printed by the server, including its token fragment. Each restart creates a new token, so reopen the newly printed URL. The server checks and rebuilds outdated frontend assets on startup.

### 4. Try the complete workflow

Connect a small public Python repository such as `https://github.com/pallets/itsdangerous`. Wait for indexing and inspect coverage/extraction status. Upload your own synthetic engineering document if you want document-backed investigation, then ask a question about the indexed code. Open a citation and inspect its graph path before requesting a fix plan.

For the recorded signed-token example, use the [demo artifacts and reproduction instructions](docs/submission-demo/README.md). The recording used revision `672971d66a2ef9f85151e53283113f33d642dabd`, synthetic company documents and human-reviewed demo memories; onboarding today's default branch is not an exact reproduction of that fixture. Personal/team memory contributions require their separate proposal, sharing and review steps.

If onboarding or chat fails, check CLI authentication, model access, database readiness and visible job errors. Failed or partial ingestion is not a complete knowledge base. See the [full run guide](docs/company-brain-app.md) for update commands and limits, [Lite lifecycle guide](docs/lite-integration.md), and [optional Cloud setup](docs/cloud-setup.md) (not live-verified).

## Graph data model

FalkorDB is the **primary connected knowledge database**. It stores the company graph and optional native personal/team memory projections. SQLite stores memory records, permissions, review/lifecycle state and audit history; it does not replace company graph traversal. Original source bytes and local artifacts live on disk.

| Nodes | Role |
| --- | --- |
| `Project`, `File`, `Symbol` | Repository identity, revision-pinned files and Python code identities |
| `Person`, `Team`, `Commit` | Recorded contributors, explicit ownership and change evidence; no invented company hierarchy |
| `Issue`, `PR`, `Comment` | Attributed public work-item and discussion snapshots |
| `Document`, `Source`, `ConceptMention` | Documents, literal excerpts/provenance and advisory named-concept mentions |
| `Decision`, `ReviewRecord` | Proposed/approved decisions and separate review evidence |
| Native memory graph nodes | Brain, person, team, memory, source, entity and version nodes in a separate tenant namespace |

Core paths, shown as schema patterns rather than claims that every project contains every edge:

```text
(Project)-[:CONTAINS]->(File)-[:DECLARES]->(Symbol)
(Symbol caller)-[:CALLS]->(Symbol target)
(Person)-[:AUTHORED]->(Commit)-[:MODIFIES]->(File)
(owner)-[:CODEOWNER_OF]->(File)
(Person)-[:REVIEWED]->(PR)-[:CHANGES]->(File)
(PR)-[:REFERENCES]->(Issue)
(PR or Issue)-[:DISCUSSED_IN]->(Comment)-[:SUPPORTS]->(Source)
(Document)-[:SUPPORTS]->(Source)
(Decision)-[:SUPPORTED_BY]->(Source)
(Decision)-[:CONSTRAINS]->(Symbol)
(new Decision)-[:SUPERSEDES]->(old Decision)
```

Nodes carry scoped identifiers such as `uid` and `repo_id`; current code includes revision/current-state metadata. Edges retain relevant resolution/confidence and source provenance. Static call resolution is conservative; dynamic dispatch and missing edges remain unknown. Git author identities are not automatically merged with GitHub users.

Native memory can link a reviewed record through **`MENTIONS → RESOLVES_TO`** to a verified company symbol. Reviewed `UPDATES`, `EXTENDS` and `RELATES_TO` assertions preserve version-specific relationships. Catalog permissions, review and expiry are rechecked at retrieval time; imported assertions do not authenticate an author or become company policy.

[Schema and adapter](src/brain/graph.py) · [Ingestion implementation](src/brain/ingest/) · [Memory architecture](docs/memory-architecture.md) · [Three-brain graphs](docs/three-brain-graphs.md)

## Cypher and graph retrieval

These parameterized examples use the product's implemented paths. `$repo` is the indexed repository ID, `$ids` contains selected symbol UIDs, and `$path` is a repository-relative file path. Execute them against that repository's graph. These examples illustrate retrieval; permission, freshness, review and output-bound checks remain in the application services.

**Change impact: incoming callers up to two hops.** The service fetches 101 paths to detect overflow beyond its 100-path bound, then retrieves applicable decisions for targets and callers.

```cypher
MATCH p=(caller:Symbol)-[:CALLS*1..2]->(target:Symbol)
WHERE target.uid IN $ids
  AND all(n IN nodes(p) WHERE n.current=true AND n.repo_id=$repo)
RETURN DISTINCT [n IN nodes(p) | n.uid] AS path,
       [r IN relationships(p) | r.confidence] AS confidence,
       [r IN relationships(p) | r.resolution] AS resolution
ORDER BY path LIMIT 101
```

**Decision provenance.** Fetch candidate constraints with their supporting sources. Only active, human-approved, source-backed constraints at the approved revision can enter `must_preserve`; proposals and stale evidence remain review material.

```cypher
MATCH (d:Decision {repo_id:$repo, scope:'org'})-[:CONSTRAINS]->
      (s:Symbol {repo_id:$repo, current:true})
WHERE s.uid IN $ids
OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(src:Source {repo_id:$repo})
RETURN d.uid AS decision, d.status AS status, d.approval AS approval,
       d.approved_revision AS approved_revision,
       collect(DISTINCT s.uid) AS subjects,
       collect(DISTINCT src.uid)[0..21] AS sources
ORDER BY decision LIMIT 101
```

**Who knows this file?** Authorship provides inferred maintainer evidence; explicit CODEOWNERS rules take precedence in `find_owner`. Commit counts do not establish organizational authority.

```cypher
MATCH (p:Person {repo_id:$repo})-[:AUTHORED]->
      (c:Commit {repo_id:$repo})-[:MODIFIES]->
      (f:File {repo_id:$repo, path:$path, current:true})
RETURN p.uid AS person, p.name AS name, count(DISTINCT c) AS commits,
       collect(DISTINCT c.uid)[0..20] AS evidence_commits
ORDER BY commits DESC, person LIMIT 6
```

The full algorithms also use FalkorDB exact/full-text seeds followed by bounded connected paths, recorded Issue/PR → File associations, decision supersession and authorized native memory traversal up to four hops. Source ranking and result bounds are explicit; truncation and unavailable context are reported.

[Actual service queries](src/brain/services/core.py) · [Evidence retrieval](src/brain/services/evidence.py) · [Native memory retrieval](docs/falkor-memory-retrieval.md) · [MCP contracts](contracts.md)

### Why FalkorDB is essential

The graph is in the answer and action path, not just the visualization. `check_change` traverses incoming callers and their connected constraints; ownership and history retrieval join people, changes, files and sources. Citation validation checks native company relationships, and connected memory retrieval follows authorized source/symbol paths.

Removing FalkorDB makes those operations unavailable. The company graph adapter has **no offline query fallback**, and stale/unavailable native memory retrieval does not silently fall back to another backend. An explicit optional catalog-search mode exists for comparison, but cannot replace the connected company workflow. This architecture establishes a graph dependency; it does not by itself prove better coding performance.

## Architecture and trust boundaries

```text
Public repo + public history + synthetic/authorized documents
    → AST/Git indexer + Graphify + optional GraphRAG SDK ingestion
    → FalkorDB company graph ← verified bridge → native memory graph
    → scoped read-only MCP tools → Codex investigation
    → checked citations + source inspector + graph explorer
    → reviewed plan → explicit human approval → isolated patch + tests

SQLite memory catalog → permission/review checks → native memory projection
React UI ↔ local FastAPI server ↔ graph, catalog and isolated agent processes
```

Source prose and extracted relationships are untrusted evidence. Deterministic checks establish source bytes, access and graph provenance; model relevance review is fallible. Human approval is separate from investigation. Approved actions use bounded file scope, exact test selections and a network-disabled Codex OS sandbox; exporting a patch does not apply or publish it upstream. An unrestricted host administrator can bypass local workflow controls.

The default standalone MCP server exposes `get_context`, `trace_decision`, `find_owner`, `check_change` and `remember`. Optional memory configuration adds up to three tools. The application exposes its own nine-tool read-only investigation surface; see the [application guide](docs/company-brain-app.md). Semantic extraction uses Graphify and the optional FalkorDB GraphRAG SDK ingestion pipeline; SDK vector retrieval/completion is not implemented.

## Demonstration and verification

The signed-token demo follows a symptom-only investigation through code/document evidence, reviewed personal/team contributions, a human-approved patch and test output. The planning request explicitly asked for memory contributions; the synthetic team note included an implementation hint and exact code identity. Those are disclosed demo inputs, not upstream maintainer policy.

| Recorded check | Original code | Patched code |
| --- | --- | --- |
| Independent 16-case reproduction | 4/16 passed | 16/16 passed |
| Separate minimal extreme-timestamp regression | 1 assertion failure, 0 errors | 1 passed |
| Complete upstream suite, with patch tests where present | 297 passed | 305 passed |
| Patched suite including follow-up checks | — | 312 passed |

The historical three-brain action's automatic regression flag remains **false** because its baseline included conversion errors. The separate minimal reproduction satisfies the existing rule; it does not rewrite that historical action. [Receipts, patches and replay](docs/submission-demo/README.md) · [Full follow-up](docs/submission-demo/traceback-review.md) · [Current hardening report](docs/final-hardening-2026-10-18.md).

A small historical baseline/graph coding comparison succeeded 3/3 in both conditions; **no correctness advantage was observed**. A synthetic retrieval comparison recovered 3/3 deliberately authored graph-path cases with native traversal versus 0/3 with catalog exact/full-text search; both achieved 6/9 natural-language Hit@3. These are bounded integration results, not production or general performance claims. [Coding evaluation](docs/v5-evaluation.md) · [Retrieval methodology](docs/falkor-memory-retrieval.md).

Reproduce checks from the repository root after installing the extras above:

```sh
uv run --extra app pytest -q
uv run ruff check src tests scripts
npm run --prefix frontend test
npm run --prefix frontend build
# Isolated live FalkorDBLite suite; creates its own disposable runtime:
uv run --frozen --extra app --extra lite --extra graphify --extra ingestion \
  python scripts/validate_memory_foundation.py
```

Historical test counts and receipts describe their recorded revisions; they are not a claim that all checks were rerun for this README edit.

## Limits

This is a local, single-operator product, not hosted multi-user SaaS. Onboarding is bounded: a shallow checkout of up to 100 commits, partial public GitHub acquisition, and capped repository/document/graph results. Synchronization is manual, not always-on. Large repositories, unresolved static calls, missing history, extraction/model latency and fallible relevance judgments can limit answers. Citation provenance does not establish semantic truth. Source revocation can deny reopening a citation without erasing older report text.

See [application limits](docs/company-brain-app.md), [retention boundary](docs/company-brain-actions.md#historical-retention-and-revocation-boundary), [roadmap](docs/roadmap.md), and [evaluation limitations](docs/v5-evaluation.md).

## Original work, data and AI assistance

Work began on **15 October 2026** in this previously empty repository, as recorded in [NEW_WORK.md](NEW_WORK.md). Original work includes the ingestion adapters, source-backed graph services, MCP integration, React/FastAPI workspace, reviewed memory workflows, approval-controlled editing and verification harnesses. FalkorDB, FastMCP, Graphify, the GraphRAG SDK and other open-source packages are dependencies and retain their respective attribution/licenses.

**AI assistance disclosure:** OpenAI Codex assisted with implementation, debugging, tests and documentation. Waggle supports development conversation memory; its implementation is not copied into this product. Participant contribution, verification and understanding remain the team's responsibility; generated output alone is not evidence of correctness.

The submission demos use public upstream repositories/history and synthetic company documents/notes. Public source snapshots retain provenance and attribution; synthetic decisions are not upstream policies. For hackathon reproduction, use public or synthetic material you are permitted to use, and exclude private, login-protected, paywalled, personal or otherwise restricted information. Personal Brain denotes the product's scope model; demonstrate it with synthetic notes rather than real personal information.

Prepared against the [full Graph Hacks rules](https://www.wemakedevs.org/hackathons/falkordb/rules) and [WeMakeDevs Code of Conduct](https://www.wemakedevs.org/coc). Entry track: **Company Brain**. Deadline: **18 October 2026, 11:59 PM IST**. This repository documents the project; it does not constitute a submitted entry or certify team eligibility.

Before publishing artifacts, follow the [publication boundary](docs/security-remediation.md) and run `python scripts/check_publication.py --history` against the intended release index/history. Raw traces, databases and local runtime state are not publication artifacts.
