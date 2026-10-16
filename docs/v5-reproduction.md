# Rebuild the v5 demonstration graph

Use Python 3.12, uv, Git, and a local FalkorDB endpoint. For Lite install `libomp`
and run `uv sync --frozen --extra lite --python 3.12`. Keep one owner running in
another terminal:

```sh
.venv/bin/python scripts/run_lite.py --db "$PWD/data/runtime/v5/brain.rdb" --port 6393
```

Docker alternative: `docker compose up -d` uses loopback DB port 6379 and Browser
port 3000. That image's compatibility must be verified before claiming it tested.
Use a new database/volume; never reuse the unfiltered research/test namespace.

```sh
git clone https://github.com/urllib3/urllib3.git .checkouts/urllib3
git -C .checkouts/urllib3 checkout a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8
cp config/agent-demo.example.yaml config/v5.local.yaml
# Set repo_root to the absolute clean checkout and port to 6393 for Lite.
export BRAIN_CONFIG="$PWD/config/v5.local.yaml"
export PYTHONPATH="$PWD/src"
.venv/bin/python scripts/rebuild_demo_graph.py \
  --config "$BRAIN_CONFIG" --out "$PWD/data/experiments/v5-lifecycle" --phase prepare
```

This one script runs sync, imports only `data/sources/urllib3`, ingests tracked
`CHANGES.rst`, `docs/reference/urllib3.poolmanager.rst`, `docs/user-guide.rst`,
and proposes the #5161 rule. It saves the pre-approval `must_preserve=[]` response
and review record. Sources stay untrusted; ingestion creates no active decisions.

In a **separate human-controlled interactive terminal**, inspect the original
[PR #5161](https://github.com/urllib3/urllib3/pull/5161), the pinned 303 branch
and existing tests. Read the full proposal and target printed by the script.
Then run:

```sh
export PYTHONPATH="$PWD/src"
export BRAIN_CONFIG="$PWD/config/v5.local.yaml"
BRAIN_OPERATOR_SESSION=1 .venv/bin/python scripts/rebuild_demo_graph.py \
  --config "$BRAIN_CONFIG" --out "$PWD/data/experiments/v5-lifecycle" --phase approve
BRAIN_OPERATOR_SESSION=1 .venv/bin/python scripts/rebuild_demo_graph.py \
  --config "$BRAIN_CONFIG" --out "$PWD/data/experiments/v5-lifecycle" --phase supersede
```

Each approval displays the reviewed sources/subjects/text and requires typing the
exact `APPROVE <id>` confirmation. D-1 becomes active, then the narrower D-2
supersedes it on the same symbol. Both are demo operator rules grounded in real
sources, not policies authorized by urllib3 maintainers. No agent should execute
these two phases. Do not put `BRAIN_OPERATOR_SESSION` in MCP environments.

After both human steps, an agent may run the read-only freeze phase:

```sh
.venv/bin/python scripts/rebuild_demo_graph.py \
  --config "$BRAIN_CONFIG" --out "$PWD/data/experiments/v5-lifecycle" --phase freeze
```

This requires active approved D-2, superseded D-1, matching revision and nonempty
`must_preserve`. It audits excluded work, captures corpus/hash, and refuses to
overwrite a prior freeze. Follow [the paired protocol](v5-evaluation-protocol.md).
Raw graph captures and trial logs stay ignored. Export reviewed evidence only.

## Verified graph paths

The primary bridge is the exact #5161 mention at `CHANGES.rst:127`. `MENTIONS`
is one additive relation used for exact PR numbers and exact symbol references;
both carry document Source UID, source line, reference and non-binding confidence.
PR → file remains a historical file association, not proof of a symbol change.

Run this in FalkorDB Browser on **org_demo only**, replacing the repo ID if needed:

```cypher
MATCH p=(d:Document {repo_id:'experiment:urllib3:5181:eligible', path:'CHANGES.rst'})
  -[:MENTIONS]->(pr:PR {number:5161})-[:CHANGES]->(f:File)
  -[:DECLARES]->(s:Symbol {qualname:'PoolManager.urlopen'})
MATCH evidence=(d)-[:SUPPORTS]->(src:Source)
RETURN p, evidence LIMIT 5
```

Exact public re-export bonus (no suffix matching or inherited-method guessing):

```cypher
MATCH p=(d:Document {repo_id:'experiment:urllib3:5181:eligible',
  path:'docs/reference/urllib3.poolmanager.rst'})
  -[:MENTIONS]->(s:Symbol {qualname:'ProxyManager'})
  <-[:CALLS]-(caller:Symbol)
MATCH evidence=(d)-[:SUPPORTS]->(src:Source)
RETURN p, evidence LIMIT 5
```

If that particular symbol has no exact document mention, use a verified linked
symbol or show `no_verified_symbol_link`; never manufacture a connection. The
API already returns document Sources and exact mention provenance via get_context.

Browser verification is a separate gate from successful driver traversal.
The official Browser can run from source against Lite's TCP endpoint; startup
alone does not establish successful visual attachment. See the execution log.
