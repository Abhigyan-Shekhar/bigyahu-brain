# Company Brain

A local MCP server that connects a planned code change to incoming callers,
source-backed constraints, and maintainer evidence in FalkorDB. Codex remains the
code-editing agent. Source prose is untrusted evidence; remembering something
creates a proposal, never an approved rule.

**Status: real local graph integration verified; coding experiment still pending.**
FalkorDBLite 0.10.0 runs on this Mac with Redis 8.6.2 and graph module 4.18.3.
All 41 tests pass with live integration enabled. The pinned Requests repository
syncs, the real two-hop path is verified, and Codex's app-server successfully
invokes `check_change` through MCP after a database restart. This is a protocol
integration result, not yet a model-selected tool call or measured coding benefit.

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
| check_change | Intended symbols, incoming callers, applicable constraints |
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
The direct Browser graph URL still needs verification on the running version.

## Verification

```sh
uv run pytest -q
uv run ruff check src tests scripts
# Only against a local disposable/test database:
BRAIN_INTEGRATION=1 uv run pytest -q -m integration
```

Unit/contract checks cover poisoning proposals, private routing, scope/path
validation, CODEOWNERS precedence, caller constraints, stale revision behavior,
admin rejection, exact five-tool discovery, and real STDIO launch from another
working directory with the database unavailable. The live suite has now verified
Cypher on the measured Lite engine; mocks alone
do not prove compatibility. Set BRAIN_INTEGRATION=1 and BRAIN_LITE_TESTS=1 to
include the live graph and process-lifecycle checks.

Codex discovery is now verified through the actual app-server API. See
[the integration gate status](docs/integration-status.md) for the exact evidence
and remaining database/agent gates.

## Remaining release gates

- Revalidate on any different engine version; current live checks pass on Lite 4.18.3.
- Validate a real demo packet and compare independent baseline/graph runs on the
  same revision. The Requests candidate may be too obvious to show added value.
- Human-review and approve a real applicable constraint; agents must not do this.
- Finish old-side diff mapping (currently file fallback), cross-module import/call
  resolution, document ingestion, and reviewer-based maintainer ranking.
- Expand adversarial/integration coverage, record measured metrics, validate Browser
  routing, record the video, and perform a clean-room setup.

Static calls currently cover conservative same-module lexical calls and heuristic
self/cls method calls; dynamic calls remain unresolved. Dirty checkout detection
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
`python scripts/check_publication.py` against the Git index before publishing.
See [exposure remediation](docs/security-remediation.md) for the confirmed prior
public trace exposure and pending history cleanup.
