# Fresh local Browser demonstration

**Historical macOS/Lite manual verification: 16 October 2026, including human-approved supersession.**

The receipt and footage below describe that specific local run. They do not certify
Windows execution, automated UI coverage, or approval in a newly rebuilt database.

The reviewed [verification receipt](verification-receipt.json) records the
final checks, source URLs, saved approval state, and recording hash.

This is a reconstructed demonstration, not the original experiment database or
an upstream policy history. The original Requests database remains on port 6389.
This demo has a separate Lite persistence directory on port 6390 and only one
graph, `org_demo`. No private graph is created.

The integrated v5 workflow separately supports native RST/Markdown ingestion
through `ingest-docs` and the [v5 rebuild script](../v5-reproduction.md). This
Browser setup deliberately retains its editorial Document and REFERENCES link;
it does not use the v5 MENTIONS bridge or reproduce the frozen trial corpus.
Its D-1/D-2 constrain `HTTPConnectionPool.urlopen` and have different text from
the v5 decisions on `PoolManager.urlopen`. Keep the recording and approval
receipts attributed to their respective graph; their IDs alone are not identity.

## Built and checked

- Public urllib3 pinned at `a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`.
- Real sync: 176 files, 2,093 AST symbol records (2,058 unique Symbol nodes),
  869 resolved call sites; 7,579 unresolved calls are explicitly retained as a gap.
- Only merged #5161 and #3780 from the checked-in public snapshot fixture are
  ingested. #5181 and #5242 records are omitted. A text scan found no known
  excluded #5181/#5191/#5242 references in the resulting evidence text.
- 2,525 nodes and 3,543 edges after human approval, including the labeled local
  demo additions and one SUPERSEDES edge.
- Document → #5161 → connectionpool.py → HTTPConnectionPool.urlopen: one path.
- Direct caller: HTTPConnectionPool.urlopen → set_file_position, line 772,
  `static` / `statically_resolved_import`.
- Re-export caller: WrappedSocket.recv → wait_for_read, line 324,
  `static` / `statically_resolved_import`.
- Two supplemental IMPORTS edges explain the actual source route:
  pyopenssl.py:61 → util/__init__.py:20 → util/wait.py. They are checked against
  the Python AST and labeled `demo_verified_ast_import`; they are demo additions,
  not an assertion that the normal ingester emits IMPORTS edges.
- The human operator approved D-1, then D-2 through the existing interactive
  CLI. D-2 is **active**, D-1 is **superseded**, and D-2 → SUPERSEDES → D-1 exists.
  Both have `human_approved` metadata at the pinned revision. D-1's exact two
  original sources and D-2's exact four original sources remain linked.
- Graceful shutdown saved the database. Restarting from the same persistence
  directory preserved all 2,525 nodes, 3,542 edges, paths, and source links.
  The original Requests graph still has its original 1,330 nodes.
- All eleven saved Cypher files execute on Lite. Query 05 returns eight rows
  (the combinations of D-1's two and D-2's four sources), rendered as six unique
  nodes and seven edges in Browser. Query 11 shows both statuses and source counts.

The document's local source uses a URN and `local_relative_path`, because it has
not been published. Its content is [document.md](document.md). Public historical
sources retain their actual URLs, snapshot timestamp, and untrusted status.
CHANGES remains a historical file association, not proof of a symbol-level change.

## Rebuild on Windows, macOS, or Linux

Install Git, uv, and Docker Desktop (Linux containers on Windows). Run these
commands from this project directory in PowerShell or a Unix terminal. No Bash,
`PYTHONPATH`, hardcoded absolute paths, or native Windows Lite package is required.

```text
uv sync --frozen --python 3.12
git clone https://github.com/urllib3/urllib3.git .checkouts/urllib3-browser-demo
git -C .checkouts/urllib3-browser-demo checkout --detach a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8
docker run -d --name brain-browser-demo -p 127.0.0.1:6379:6379 -p 127.0.0.1:3000:3000 -v brain-browser-demo-data:/data falkordb/falkordb:v4.14.7
uv run --frozen python scripts/prepare_browser_demo.py --checkout .checkouts/urllib3-browser-demo
uv run --frozen python scripts/verify_browser_demo.py
```

The Docker image includes Browser. See the [Docker review receipt](docker-review.md)
for the separate macOS-hosted Linux-container check. Open `http://127.0.0.1:3000` and connect to
host `127.0.0.1`, database port `6379`, empty password, TLS off. Existing services
must release these ports first, or choose different host ports. For example,
map `127.0.0.1:6390:6379` and `127.0.0.1:3002:3000`, pass `--port 6390` to
preparation, and open Browser at port 3002. Inside Docker the database remains
on 6379. The bundled Browser server shares the database container, so its login
uses host `127.0.0.1`, **port 6379**, even when the host maps database port 6390.
Python commands running on your host use `--port 6390`. A separately hosted
Browser needs a host reachable from its own server process. Preparation writes
the selected host port into its generated config; verification and human review
read it.

Use an empty dedicated database and fresh output directory. Preparation refuses
**any existing graph on every port**, a dirty/wrong checkout, invalid fixture, or
existing output corpus. It never clears a database. `--output` selects another
output directory and `--config` selects a separate generated config; pass that
same config to verification and human review. The default config is ignored
`config/brain.browser-demo.local.yaml`.

To resume a stopped Docker demo: `docker start brain-browser-demo`.
Stop it gracefully with `docker stop brain-browser-demo`. Its named volume keeps
the data; restarting an existing demo does not require rerunning preparation.
A rebuild needs a separate empty volume/container and unused host ports.

Lite is an alternative on macOS/Linux or inside WSL:

```text
uv sync --frozen --extra lite --python 3.12
uv run --frozen python scripts/run_lite.py --db data/runtime/browser-demo/brain.rdb --port 6390
```

Leave that terminal running. Prepare in a second terminal with `--port 6390`
and use the separately installed Browser described below. Native Windows Lite
is unavailable in this setup; the launcher now explains Docker/WSL before
importing POSIX-only modules. The optional dependency excludes Windows.
Password-file authentication still requires POSIX permission checks; it is not
a Windows ACL implementation. The loopback Docker demo does not use a password file.

Fixture SHA-256 is defined over UTF-8 bytes with LF newlines. `.gitattributes`
keeps snapshot files LF on new checkout; the loader also normalizes CRLF from
existing Windows checkouts before checking the same digest. Other byte changes
still fail integrity validation, before database access. Generated config and
source excerpts explicitly use UTF-8.

## What this demonstration actually exercises

| Graph content | Origin |
| --- | --- |
| File, Symbol, DECLARES, CALLS and static call-resolution metadata | Native sync/AST ingestion |
| PR, snapshot Source, CHANGES and historical provenance | Native snapshot ingestion, filtered to two public PRs |
| Document and its REFERENCES link | Demo-specific editorial seed; no native document-ingestion claim |
| Two File IMPORTS edges and exact-line Sources | Demo-specific setup verified against the pinned AST; normal ingestion does not emit these edges |
| D-1/D-2 proposals and their source/subject links | Demo-specific policy seeds, explicitly marked `is_demo`; not upstream decisions or automatic policy extraction |
| Human approval, active/superseded states and SUPERSEDES | Existing interactive operator functionality, only after independent human approval |

The script never calls approval or writes approved states. Bounded Git history
and snapshot omissions mean this is not exhaustive upstream history.

## Open and verify in Browser

The [Browser setup procedure](../browser-verification.md#reopen-the-verified-local-setup)
pins official Browser 2.7.0. Open `http://127.0.0.1:3000/graph`.

1. In Connections, add/select host `127.0.0.1`, port **6379** for Docker or **6390** for the historical Lite run, username `default`,
   empty password, TLS off for loopback. Do not select the Requests port 6389.
   After a database restart, Browser may return to login; reconnect with these
   same connection details.
2. Open `http://127.0.0.1:3000/graph?graph=org_demo&view=Graph` directly.
3. Paste each `.cypher` file into the editor and click Run.
4. Use Graph view for queries 01–03 and 05; use Table view for the other queries.
   Query 06 shows historical source/snapshot provenance. Query 07 shows both
   exact caller lines and target definitions. Queries 09–10 give compact call
   resolution and import-line tables. Query 04 shows retained source URLs.
5. Tools → Tree → Top → Down makes the document chain easier to inspect.
   Record whether reload preserves graph, query, and layout for your Browser version.
   The bundled Docker Browser used in the portability check reset the query on
   reload; paste the saved query and Run again. Keep connection menus closed
   during captures. If an auxiliary mobile drawer obstructs the view, reload
   before capturing.

The historical recording used a real Browser-to-Lite connection. A fresh Docker
run must be recorded and reported separately; it does not inherit those approvals.

## Captured Browser evidence

The completed artifact is
`data/validation/browser-demo/browser-demo-approved-sampled.mp4`: approximately
43 seconds, made from 85 actual Browser screenshots sampled at roughly two
frames per second, with actual frame timing preserved. Its nine views show the
document graph, direct caller, re-export graph, document table, caller resolution
and lines, import evidence, supersession graph, approved decision statuses, and
retained source URLs. The complete MP4 decodes successfully; extracted encoded
frames were visually inspected. This is sampled Browser footage, not an event
replay or a claim of continuous high-frame-rate capture.

The earlier `browser-demo-sampled.mp4` remains a 35-second pre-approval recording.
The separate original demo event-replay video is unchanged.

Key JPEGs and the recording's frame/timing manifest remain in ignored
`data/validation/browser-demo/`. No upload or publication was performed.
The Browser's narrow responsive layout clipped the graph behind an auxiliary
drawer after interactions; the capture uses the desktop layout to verify all
nodes together. This is a Browser presentation limitation, not a Lite connection
failure. The temporary capture viewport is reset after verification.

## Database verification versus Browser UI verification

`verify_browser_demo.py` checks database query results only. Its JSON explicitly
reports `verification_layer: database` and `browser_ui_tested_by_this_script: false`.
It does not test login, graph selection, editor/Run, rendering, clicks, reload,
layout, source inspection, or recording. A passing database check is insufficient
to mark Browser UI verification complete. There is no automated UI regression suite.

For a **manual Browser UI acceptance run**, record OS, engine/image, Browser
version, host ports, and whether the database is fresh or human-approved, then:

1. Log in and select `org_demo`; check the selected graph in the UI.
2. Paste query 01 and click Run. In Graph view inspect the four-node document →
   #5161 → file → symbol chain and click nodes to inspect their properties.
3. Run queries 02/03 and inspect both caller paths. In Table view run 09/10;
   verify call lines 772/324, definition lines 176/113, and imports 61/20.
4. Run 04/06 and inspect source URLs, line anchors, revision and snapshot basis;
   distinguish the local document URN from public GitHub sources.
5. After independent approval in a human terminal, run 05/11. Inspect D-2 →
   SUPERSEDES → D-1, statuses active/superseded and retained source counts 4/2.
   A fresh unapproved build must report this step pending.
6. Reload the page, record graph/query persistence (including any reset), rerun a query, and capture
   clean Graph and Table views with menus closed. Record interaction results and
   footage/screenshot hashes separately from the database report.

Recheck the populated graph without mutating it:

```sh
uv run --frozen python scripts/verify_browser_demo.py
```

The final successful acceptance command is:

```sh
uv run --frozen python scripts/verify_browser_demo.py --require-approved
```

That check requires the actual
SUPERSEDES path, active/superseded statuses, approval metadata, the pinned
revision, and the exact original source sets on both decisions.

## Human approval and reproduction

Approval is already complete in the current demo. The procedure below records
how to repeat the workflow after rebuilding a fresh database; do not rerun the
approval script against these already-approved records.

Both proposals constrain the same pinned `HTTPConnectionPool.urlopen` symbol.
They are local demo policies, not statements attributed to urllib3 maintainers.

**D-1:** Preserve 303 cleanup: drop the body, chunked framing, saved body position,
and body-specific headers. Evidence:
[merged #5161](https://github.com/urllib3/urllib3/pull/5161) and
[connectionpool.py:910–922](https://github.com/urllib3/urllib3/blob/a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8/src/urllib3/connectionpool.py#L910-L922).

**D-2:** Preserve D-1's cleanup and explicit UnrewindableBodyError when replay
cannot rewind the body. A failed tell() alone must not reject the initial
request before replay is required. Evidence: both D-1 sources, plus
[merged #3780](https://github.com/urllib3/urllib3/pull/3780) and
[request.py:176–230](https://github.com/urllib3/urllib3/blob/a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8/src/urllib3/util/request.py#L176-L230).

In a fresh rebuild, a human independently reviews the sources and texts, then
runs this in an interactive terminal from the project directory:

```sh
uv run --frozen python scripts/review_browser_demo.py
```

It displays each proposal and invokes the existing operator CLI. Approval occurs
only if you type `APPROVE D-1`, then `APPROVE D-2` at the respective prompts.
Decline either prompt to stop. This is required by the existing repository rule:
“A separate human-controlled terminal must set BRAIN_OPERATOR_SESSION=1” and
“Do not ... have the agent approve its own proposal.” See [README](../../README.md).

D-2 approval atomically makes D-1 superseded and adds D-2 → SUPERSEDES → D-1.
Queries 05, 11, and 04 now verify the edge, statuses, and retained sources in the
actual Browser. The original experiment's historical approval state is recorded
separately in [v5 lifecycle evidence](../v5-lifecycle-evidence.json); this Browser
run does not visually verify that state and creates a new local approval history.
