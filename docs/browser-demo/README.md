# Fresh local Browser demonstration

**Completed on 16 October 2026, including human-approved supersession.**

The reviewed [verification receipt](verification-receipt.json) records the
final checks, source URLs, saved approval state, and recording hash.

This is a reconstructed demonstration, not the original experiment database or
an upstream policy history. The original Requests database remains on port 6389.
This demo has a separate Lite persistence directory on port 6390 and only one
graph, `org_demo`. No private graph is created.

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

## Rebuild from public inputs

Run from the Company Brain project directory. Use a new empty persistence
directory for a rebuild; the preparation script refuses a nonempty database.
It also refuses ports other than 6390 and a dirty/wrong-revision checkout.
Stop an existing owner gracefully before reusing its port. Never delete the
original Requests persistence directory.
An immediate restart on this Mac briefly reported `Address already in use`
despite no remaining listener. Waiting for the loopback port to release, then
rerunning the same owner command, succeeded; no Docker fallback was needed.

```sh
git clone https://github.com/urllib3/urllib3.git .checkouts/urllib3-browser-demo
git -C .checkouts/urllib3-browser-demo checkout --detach a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8
.venv/bin/python scripts/run_lite.py \
  --db "$PWD/data/runtime/browser-demo/brain.rdb" --port 6390
```

Leave the owner running, then in another terminal:

```sh
PYTHONPATH=src .venv/bin/python scripts/prepare_browser_demo.py \
  --checkout .checkouts/urllib3-browser-demo
```

The script writes ignored `config/brain.browser-demo.local.yaml`, filtered
snapshot metadata, and `data/validation/browser-demo/build.json`. It never calls
the approval function or writes approved states. Bounded Git history and
snapshot omissions mean this corpus is not an exhaustive history or a proof
against all possible semantic leakage.

## Open and verify in Browser

The [Browser setup procedure](../browser-verification.md#reopen-the-verified-local-setup)
pins official Browser 2.7.0. Open `http://127.0.0.1:3000/graph`.

1. In Connections, add/select host `127.0.0.1`, port **6390**, username `default`,
   empty password, TLS off for loopback. Do not select the Requests port 6389.
   After a database restart, Browser may return to login; reconnect with these
   same port-6390 details.
2. Open `http://127.0.0.1:3000/graph?graph=org_demo&view=Graph` directly.
3. Paste each `.cypher` file into the editor and click Run.
4. Use Graph view for queries 01–03 and 05; use Table view for the other queries.
   Query 06 shows historical source/snapshot provenance. Query 07 shows both
   exact caller lines and target definitions. Queries 09–10 give compact call
   resolution and import-line tables. Query 04 shows retained source URLs.
5. Tools → Tree → Top → Down makes the document chain easier to inspect.
   Reload preserves the graph, query, and layout. Keep connection menus closed
   during captures. If an auxiliary mobile drawer obstructs the view, reload
   before capturing.

This is a real Browser-to-Lite connection. Docker fallback is unnecessary for
this successfully attached engine.

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

Recheck the populated graph without mutating it:

```sh
PYTHONPATH=src .venv/bin/python scripts/verify_browser_demo.py
```

The final successful acceptance command is:

```sh
PYTHONPATH=src .venv/bin/python scripts/verify_browser_demo.py --require-approved
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
sh scripts/review_browser_demo.sh
```

It displays each proposal and invokes the existing operator CLI. Approval occurs
only if you type `APPROVE D-1`, then `APPROVE D-2` at the respective prompts.
Decline either prompt to stop. This is required by the existing repository rule:
“A separate human-controlled terminal must set BRAIN_OPERATOR_SESSION=1” and
“Do not ... have the agent approve its own proposal.” See [README](../../README.md).

D-2 approval atomically makes D-1 superseded and adds D-2 → SUPERSEDES → D-1.
Queries 05, 11, and 04 now verify the edge, statuses, and retained sources in the
actual Browser. The original experiment's historical approval state remains
unverified; this is a new local approval history.
