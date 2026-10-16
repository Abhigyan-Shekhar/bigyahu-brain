# Browser verification — 16 October 2026

Follow-up: a [fresh isolated local demo](browser-demo/README.md) has now been
built from public inputs and verified in Browser on port 6390. It includes
sampled Browser footage and the completed human-approved D-2 → superseded D-1
path with retained sources. All eleven query files pass the final approval-aware
verification. The original-database findings below are retained; the new demo does not reproduce
the unavailable experiment database's historical state.

## Initial check of the original database

**Lite attachment passed; the original eligible corpus was missing.** At that
initial stage, no successful end-to-end footage had been captured. The separate
reconstructed demonstration described above has since completed.

The saved manual-demo database opens through the actual FalkorDB Browser. Its
`org_demo` contains Requests at `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60`,
not the eligible urllib3 corpus described in [agent-demo-results.md](agent-demo-results.md).
That report explicitly says the eligible runtime database was not published.
The available database was queried without re-ingestion or approval mutations.

| Check | Observed result |
| --- | --- |
| Official FalkorDB Browser | 2.7.0, source `8d5b64e6428b1a727bb682a0bd836dd6f7f0d5e4` |
| Engine | Lite 0.10.0, Redis 8.6.2, graph module 41803 |
| Browser connection | Online at `127.0.0.1:6389`; queries execute successfully |
| Direct graph opening | `/graph?graph=org_demo&query=…&view=Table` selects the graph and fills the editor; click Run |
| Available org graph | 1,330 nodes, 1,837 edges |
| Eligible namespace nodes | 0 |
| Documents / PR #5161 | 0 / 0 |
| Decisions | One Requests proposal; neither D-1 nor D-2 exists |
| SUPERSEDES edges | 0 |
| Requested document / caller / supersession visuals | Pending the eligible database |
| Docker fallback | Not triggered: Browser attaches to Lite. Docker daemon was stopped when inspected |

Local diagnostic evidence is in ignored `data/validation/browser/`: the Browser
screenshot `org-demo-preflight.jpg`, read-only query results `preflight.json`,
and downloaded pinned public source files under `source/`. The screenshot shows
only `org_demo`, the connected engine, and the zero eligible-data counts. It is
evidence of attachment and missing data, not evidence of the requested paths.
The older `docs/demo/demo.mp4` remains an event replay, not Browser footage.

## Reopen the verified local setup

From the project directory, start the saved database (one owner only):

```sh
.venv/bin/python scripts/run_lite.py \
  --db "$PWD/data/runtime/manual-demo/brain.rdb" --port 6389
```

The [official Browser source](https://github.com/FalkorDB/falkordb-browser)
can run separately from Lite. The following pins the version actually tested;
Node 24 or newer is required. Keep the database and Browser terminals running.

```sh
BROWSER_ROOT="$PWD/data/runtime/falkordb-browser"
git clone https://github.com/FalkorDB/falkordb-browser.git "$BROWSER_ROOT"
cd "$BROWSER_ROOT"
git checkout 8d5b64e6428b1a727bb682a0bd836dd6f7f0d5e4
npm ci --no-audit --no-fund
python3 - <<'PY'
from pathlib import Path
import secrets
p = Path('.env.local')
p.write_text('AUTH_URL=http://127.0.0.1:3000\n'
             'NEXT_TELEMETRY_DISABLED=1\n'
             'AUTH_SECRET=' + secrets.token_hex(32) + '\n'
             'ENCRYPTION_KEY=' + secrets.token_hex(32) + '\n')
p.chmod(0o600)
PY
npm run build
npm start -- --hostname 127.0.0.1
```

`ENCRYPTION_KEY` is required by this Browser version: without it the Browser
rejects login before connecting. The initial development-server attempt exposed
this configuration error; adding the key and using a production build fixed it.
`npm start` warns about the upstream standalone output setting but served the
tested login, graph page, and successful query. Use `127.0.0.1` consistently;
the service binds IPv4 loopback. No Cloud service or tunnel is needed.

1. Open `http://127.0.0.1:3000/login`.
2. Enter host `127.0.0.1`, port `6389`, username `default`, empty password,
   and TLS off for this local endpoint. Click Log in.
3. Dismiss the download suggestion, tutorial, and release notes if displayed.
4. Open `http://127.0.0.1:3000/graph?graph=org_demo&view=Table` directly.
   Keep the graph picker closed when capturing; other graph names must stay out
   of the recording.
5. Paste the preflight below into the editor and click Run. The selected graph,
   online endpoint, and returned table must all be visible.

```cypher
MATCH (n)
RETURN count(n) AS total_nodes,
  sum(CASE WHEN n.repo_id = 'experiment:urllib3:5181:eligible'
      THEN 1 ELSE 0 END) AS eligible_nodes,
  sum(CASE WHEN 'Document' IN labels(n) THEN 1 ELSE 0 END) AS documents,
  sum(CASE WHEN n.uid ENDS WITH ':pr:5161'
      THEN 1 ELSE 0 END) AS pr_5161
```

Observed Browser row: `1330, 0, 0, 0`. A database with this row cannot satisfy
the requested demo. Obtain the existing eligible database/backup or its live
endpoint before continuing. Preserve the complete Lite persistence directory,
including AOF files; do not open the same files with two owner processes.

## Public source lines independently checked

These files were fetched from the documented pinned urllib3 commit, independent
of the unavailable eligible graph. They confirm source code, not stored graph
edges or graph provenance.

- Direct caller: [connectionpool.py:45](https://github.com/urllib3/urllib3/blob/a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8/src/urllib3/connectionpool.py#L45)
  imports `set_file_position` directly from `.util.request`;
  [line 772](https://github.com/urllib3/urllib3/blob/a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8/src/urllib3/connectionpool.py#L772)
  calls it inside `HTTPConnectionPool.urlopen`. The definition starts at
  [util/request.py:176](https://github.com/urllib3/urllib3/blob/a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8/src/urllib3/util/request.py#L176).
  This call does not go through a package re-export.
- Re-export example from [graph-backend-progress.md](graph-backend-progress.md):
  `WrappedSocket.recv` calls `util.wait_for_read` at
  [contrib/pyopenssl.py:324](https://github.com/urllib3/urllib3/blob/a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8/src/urllib3/contrib/pyopenssl.py#L324),
  after importing `util` at [line 61](https://github.com/urllib3/urllib3/blob/a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8/src/urllib3/contrib/pyopenssl.py#L61).
  [util/__init__.py:20](https://github.com/urllib3/urllib3/blob/a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8/src/urllib3/util/__init__.py#L20)
  re-exports it from `.wait`; its definition starts at
  [util/wait.py:113](https://github.com/urllib3/urllib3/blob/a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8/src/urllib3/util/wait.py#L113).
- Historical public discussion: [urllib3 PR #5161](https://github.com/urllib3/urllib3/pull/5161).
  Existing reviewed response URLs remain in [agent-demo-evidence.json](agent-demo-evidence.json).
  Their presence in a report does not prove their presence in this runtime graph.

## Remaining acceptance checks

After connecting the actual eligible org graph, inspect its real properties and
relationships, then capture the following in the Browser:

1. Document → #5161 → File → Symbol, including the document Source URL,
   PR source/snapshot provenance, CHANGES confidence/basis, and pinned symbol
   path/lines. A historical File association is not a symbol-level constraint.
2. Both caller paths above, with CALLS `line`, `confidence`, `resolution`,
   file UID, and revision. Static analysis is not complete runtime dispatch.
3. D-2 → SUPERSEDES → D-1, with D-2 active, D-1 superseded, human approval
   metadata, and both decisions' retained SUPPORTED_BY sources/URLs.
4. Repeat direct graph opening after reload and execute the same saved queries.
5. Record the actual Browser session with only org_demo visible. Inspect the
   resulting video before exporting it. Do not present screenshots/event replay
   as continuous footage or create/approve replacement decisions to fill a gap.

Docker is needed only if a correctly configured local Browser actually fails
to attach to Lite. Moving the current database to Docker would not supply the
missing eligible corpus, Documents, or approved supersession history.
