# Docker portability review, 16 October 2026

This is a separate fresh rebuild from the historical approved Lite recording.
Host: macOS, Docker Desktop with Linux containers. Native Windows execution has
not been verified locally; the portability workflow adds a Windows offline test
job and a separate Ubuntu Docker database job. CI results must be checked after push.

- Image: `falkordb/falkordb:v4.14.7`, pulled digest
  `sha256:6420bc72c44588f91030bdb3dd48633b281e7ec57b85b8dcd9044a88eda82526`.
- Database published only on `127.0.0.1:6379`; bundled Browser on
  `127.0.0.1:3002` (container port 3000).
- Preparation at the pinned urllib3 revision succeeded: 176 files, 2,093 symbol
  records, 869 calls, 353 statically resolved imports, 7,579 unresolved calls.
  The graph has 2,525 nodes and 3,542 edges before approval.
- All eleven saved Cypher database checks passed. Exact original source sets
  remain linked. D-1/D-2 are both proposed; approved supersession is pending in
  this new graph. No approval was performed by the agent.
- Manual UI smoke check: actual Browser login succeeded with host 127.0.0.1 and
  port 6379. Selected `org_demo`, cleared the editor, pasted query 01, clicked
  Run, and visually inspected the four-node Document → #5161 → File → Symbol
  graph. Query 09 rendered both caller paths in Table view with call lines
  772/324, definition lines 176/113, static confidence and imported resolution.
- Reload retained the connection and graph, but reset the query/view to the
  default graph query. Clearing, pasting and rerunning query 09 succeeded again.
  Query/view persistence is therefore **not verified as passing** for this
  bundled Browser. The procedure now explicitly allows rerunning saved queries.
- Screenshot: ignored local artifact
  `data/validation/browser-demo-docker-review/browser-callers.png`, SHA-256
  `ca15dcf41084f4fdd49862eab3ce1d9373af077dac1424f17a07a16d767aff66`.

This smoke check is narrower than the full manual UI acceptance checklist. It
is not an automated UI regression suite, a new approved-supersession recording,
or proof that Docker Desktop works on a particular Windows machine. The original
Lite receipt remains the evidence for the human-approved supersession UI run.
