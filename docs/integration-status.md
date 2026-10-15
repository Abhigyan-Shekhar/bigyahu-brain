# Integration gates — 15 October 2026

Local Lite integration is verified. See [measured results and startup](lite-integration.md).

| Gate | Status | Evidence |
| --- | --- | --- |
| Real FalkorDB responds | Verified | Lite 0.10.0; Redis 8.6.2; graph module 41803 |
| Real repository sync | Verified | Requests pinned SHA; 131 files, 807 symbols; repeated sync unchanged |
| Real integration tests | Verified | 41 total tests pass, including six live integration/lifecycle tests |
| Valid two-hop graph paths | Verified | resolve_redirects → rebuild_auth → should_strip_auth checked against source AST |
| Codex discovers all five tools | Verified | Actual app-server inventory, no tool discovery error |
| Codex invokes graph-backed check_change | Verified at protocol layer | Actual app-server mcpServer/tool/call; recorded response after engine restart |
| Human reviews and approves real decision | Pending | Synthetic approval tests pass; real proposal is still non-binding |
| Graph-informed code edit | Pending | Model-selected tool/patch experiment has not run |
| Baseline comparison and video | Pending | No measured coding benefit or video claimed |

The Codex global registration and local YAML were preserved. Its absolute
interpreter, BRAIN_CONFIG and PYTHONPATH continue to target the same MCP module
and loopback database. The source path avoids the previously observed macOS
hidden editable `.pth` import issue.

```sh
.venv/bin/python scripts/verify_codex_discovery.py
.venv/bin/python scripts/verify_codex_discovery.py --check-change \
  --output data/demo/lite-codex-call.json
```

The second command uses an ephemeral Codex protocol session, not a model turn.
This distinction is recorded in the output (`model_selected_tool: false`).

Cloud configuration remains ready but no paid instance is needed for this local
milestone. No more Podman repairs. Next action is the controlled coding experiment,
not another framework, frontend, or schema expansion.
