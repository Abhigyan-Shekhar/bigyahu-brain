# Company Brain

A local MCP server that connects a planned code change to incoming callers,
source-backed constraints, and maintainer evidence in FalkorDB. Codex remains the
code-editing agent. Source prose is untrusted evidence; remembering something
creates a proposal, never an approved rule.

**Status: graph-aware Codex coding demonstration validated; no baseline coding improvement demonstrated.**
FalkorDBLite 0.10.0 runs on this Mac with Redis 8.6.2 and graph module 4.18.3.
Final backend verification: **120 passed, 0 failed, 0 skipped**, with real graph
and Lite lifecycle integration enabled. A separate MCP STDIO selection passed
**4/4**, and an explicit privacy/poisoning/approval/caller/reference selection
passed **6/6**; those selections overlap the full suite. Ruff passes for
`src`, `tests`, and `scripts`. See [merge verification](docs/backend-verification.md).
Codex has independently selected MCP tools, received historical graph evidence,
and produced independently tested code changes. Some coding attempts failed;
successful retrieval does not establish improved coding performance. The final
[agent demonstration](docs/agent-demo-results.md) passed 12/12 independent socket
cases and 200 selected upstream tests; the integrated live suite passed 125 tests.
Use the [runner and reproduction commands](docs/agent-workflow.md).

## Docker-free local setup (verified)

See [Lite integration results and commands](docs/lite-integration.md). Install
`libomp`, run `uv sync --frozen --extra lite --python 3.12`, and keep one owner running:

```sh
.venv/bin/python scripts/run_lite.py --db "$PWD/data/runtime/lite/brain.rdb"
```

Sync and MCP connect to that engine through the existing loopback configuration.
Keep the entire ignored runtime directory for persistence. No paid Cloud resource
or global Codex configuration change is required.

## Optional Cloud setup (not live-verified)

[Cloud provisioning](docs/cloud-setup.md) and `config/brain.cloud.example.yaml`
remain available. Remote connections require verified TLS and a protected local
password file. Cloud provisioning is deferred while the hackathon uses Lite.

## Alternative Docker setup

Requires Python 3.11+, uv, Git, and a running FalkorDB 4.14.7 server. Python
packages are pinned in uv.lock (tested with Python 3.12).

```sh
uv sync --frozen
docker compose up -d
cp config/brain.example.yaml config/brain.local.yaml
# Edit repo_root, repo_id, repo_url and principal in the local config.
export BRAIN_CONFIG="$PWD/config/brain.local.yaml"
uv run python -m brain sync
uv run python -m brain.mcp_server
```

With Podman, start an existing machine and use:

```sh
podman run -d --name company-brain-db \
  -p 127.0.0.1:6379:6379 -p 127.0.0.1:3000:3000 \
  -v company-brain-data:/data docker.io/falkordb/falkordb:v4.14.7
```

STDIO waits for MCP input; it does not print a success message. Configure an MCP
client to launch the absolute `.venv/bin/python` path with arguments
`["-m", "brain.mcp_server"]` and an absolute `BRAIN_CONFIG` environment value.
Set `PYTHONPATH` to the absolute `src` directory in the MCP launcher as well, so
module discovery remains reliable even if an editable-install path file is ignored.
The server discovers its five tools even while the database is down; dependent
calls return `status: unavailable`.

The local development checkout at `.checkouts/requests` is ignored. Recreate it:

```sh
mkdir -p .checkouts
git clone https://github.com/psf/requests.git .checkouts/requests
git -C .checkouts/requests checkout 611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60
```

## Tools and model

| Tool | Purpose |
| --- | --- |
| get_context | Exact ID / bounded full-text seeds, then connected paths |
| trace_decision | Lifecycle, original evidence, replacement history |
| find_owner | Explicit file CODEOWNERS, otherwise inferred Git maintainers |
| check_change | Intended symbols, incoming callers, constraints and source-backed file history |
| remember | A new non-binding proposal in org or configured private scope |

The key relationship is `(caller)-[:CALLS]->(target)`. Decisions constrain symbols;
Sources preserve provenance. Files declare Symbols, Projects contain Files,
People author Commits that modify Files. CODEOWNERS edges carry the original rule.
Public issue/PR/comment snapshots link to Source nodes. No invented organization
hierarchy is added. Git author names are not automatically merged with GitHub users.

```cypher
MATCH path=(caller:Symbol)-[:CALLS*1..2]->(target:Symbol)
WHERE target.uid IN $ids
RETURN [n IN nodes(path) | n.uid] AS path
LIMIT 100
```

The service then queries decisions for the complete bounded set of targets and
callers in one batch. `must_preserve` requires active, human-approved constraint
metadata, source evidence, a matching approved revision and a clean checkout.
Proposals and stale evidence appear in `review`. Both contain IDs and metadata;
prose stays in `untrusted_source_excerpts`.

`check_change` also follows recorded historical Issue/PR → File associations
for the target and its bounded incoming callers, including PR references to
issues. It can return original source bodies and discussion without a Decision.
These file-level links and untrusted reference mentions are advisory evidence,
not symbol constraints or proof that an issue was fixed. Missing call edges do
not prove missing dependencies. Overflow is disclosed through `status="incomplete"`
and `truncated`, including the final union of context file associations.

## Evidence and operator approval

`data/sources/manifest.json` records 21 public Requests issues/PRs, collection time,
pinned code revision, URLs, content hash and pagination omissions. These are real
public snapshots, not synthetic chat messages. Requests is Apache-2.0 licensed;
public discussion text retains its original attribution and applicable terms.
Snapshot ingestion is manual:

```sh
uv run python -m brain ingest-snapshots data/sources
```

The CLI supports `list-proposals`, `inspect <id>`, and `approve <id>`. A separate
human-controlled terminal must set `BRAIN_OPERATOR_SESSION=1`, inspect source,
text, subject and any replacement, then type the exact confirmation. **Do not
put this flag in the MCP environment or have the agent approve its own proposal.**
Approval checks and supersession run in one conditional database mutation.

This is an application workflow boundary, not hostile-shell isolation. An agent
with unrestricted shell or database write access can bypass it. The environment
flag is a workflow guard, not a secret credential. The MVP must not be described
as tamper-proof. Private data is routed to a separate configured graph; it is not
protected from database administrators. Browser recordings must show only org_demo.
Browser 2.7.0 attaches to Lite and opens `/graph?graph=org_demo` directly;
see the [verified procedure and missing eligible-data blocker](docs/browser-verification.md).
The original eligible runtime remains unavailable. A separate
[reconstructed public-source Browser demo](docs/browser-demo/README.md) now
verifies the document and caller paths and includes sampled Browser footage;
its human-approved D-2 → superseded D-1 path and retained sources are now
verified in Browser. The runbook includes reproduction commands and final footage.

## Verification

```sh
uv run pytest -q
uv run ruff check src tests scripts
# Only against a local disposable/test database:
BRAIN_TEST_CONFIG=/absolute/path/to/isolated-test.yaml \
  BRAIN_INTEGRATION=1 BRAIN_LITE_TESTS=1 uv run pytest -q
```

Unit/contract checks cover poisoning proposals, private routing, scope/path
validation, CODEOWNERS precedence, caller constraints, stale revision behavior,
admin rejection, exact five-tool discovery, and real STDIO launch from another
working directory with the database unavailable. The live suite has now verified
Cypher on the measured Lite engine; mocks alone
do not prove compatibility. Set BRAIN_INTEGRATION=1 and BRAIN_LITE_TESTS=1 to
include the live graph and process-lifecycle checks.

The live suite verifies repository/private graph boundaries, source poisoning,
independent approval, two-hop callers, Issue → PR → File history, explicit
re-exports, stale revisions and sync recovery. Separate-process STDIO tests
verify exactly five tools and real source-backed responses. The publication
workflow scans indexed content and reachable history; it does **not** run pytest.

## Recorded Codex coding experiments

Saved urllib3 #5181 experiments used pin
`a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`. The first graph attempt's MCP call
was denied and also used an invalid scope; its patch passed 10/12 independent
socket cases and regressed 303 body disposal. An older six-attempt paired batch
completed only three coding sessions; usage limits interrupted the others, and
the completed graph session selected empty private scope. A separate early
guided run retrieved history but passed only 9/12 oracle cases.

Two later graph-only workflow demonstrations each passed 12/12 socket cases
and 131 selected upstream tests. A subsequently frozen matched baseline/graph
pair completed both sessions: **both passed 9/12 socket cases and 131 selected
upstream tests**, with the same failed-tell first-upload regressions. The graph
session retrieved org evidence and checked impact before editing, but reported
that the history did not change its implementation. These are separate protocols;
the successful graph-only runs cannot be treated as comparison wins.

Eligible comparison history included merged #5161/#3780, with solution-revealing
#5181/#5191/#5242 content excluded before execution. Related merged history is
additional information, not evidence of independent discovery. No measured
baseline coding improvement has been demonstrated. The reviewed runner and evaluation code are now integrated on a fresh branch
from the merged backend. A new failed attempt (9/12 oracle cases) and a final
passing graph-aware attempt (12/12) are recorded in
[agent-demo-results.md](docs/agent-demo-results.md). Raw traces and experiment
data stay local and are not publication inputs.

## Remaining release gates

- Revalidate on any different engine version; current live checks pass on Lite 4.18.3.
- Broaden controlled coding evaluation beyond the recorded matched pair; no
  general correctness or reasoning advantage is established.
- Human-review and approve a real applicable constraint; agents must not do this.
- Finish old-side diff mapping (currently file fallback), document ingestion,
  and broader runtime call resolution. Reviewer evidence remains advisory.
- Expand adversarial/integration coverage, record measured metrics, validate Browser
  routing, record the video, and perform a clean-room setup.

Static calls cover conservative same-module lexical calls, deterministic direct
imports and explicit Python `from`-import re-export chains, including aliases and
relative imports in repository-root and src layouts. Ambiguous modules, star or
conditional imports, reassignment, re-export cycles, decorated targets, closures,
inheritance and runtime dispatch remain unresolved rather than guessed. Existing
self/cls method edges are heuristic. Dirty checkout detection
is intentionally conservative across the entire repository. Graph queries have
explicit bounds and no offline answer cache. Synchronization is single-operator;
concurrent writers are not supported. Python dependency warnings currently come
from FastMCP's Authlib integration.

See docs/plan.md and docs/implementation.md for intended scope, contracts.md for
current interfaces, and NEW_WORK.md for AI assistance disclosure. Planned event
tracks: Company Brain and Agents That Act on Connected Data; eligibility and final
submission requirements remain to be verified.

## Publication boundary

Raw agent traces, experiment runs, validation logs and database state are local-only.
Use the reviewed [demo export](docs/demo/README.md), and run
`python scripts/check_publication.py --history` against the Git index and all
reachable history before publishing.
See [exposure remediation](docs/security-remediation.md) for the confirmed prior
public trace exposure and completed history rewrite.
Old local branches must be rebased or have their changes transplanted onto the
cleaned history; merging old history can reintroduce exposed records.
