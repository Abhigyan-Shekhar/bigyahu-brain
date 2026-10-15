# Read-only Codex experiment setup

Verified with Codex CLI 0.162.0-alpha.17.2. Global Codex configuration is unchanged.

The previous coding run's MCP call was blocked before execution: `MCP tool call requires approval, but approval policy is never`. Use an isolated invocation with `--ignore-user-config`, plugins/apps disabled, and the following server settings. Supply the existing absolute Python launcher, PYTHONPATH and BRAIN_CONFIG per invocation.

```toml
[mcp_servers.company-brain]
enabled_tools = ["get_context", "check_change", "find_owner", "trace_decision"]
disabled_tools = ["remember"]
default_tools_approval_mode = "prompt"

[mcp_servers.company-brain.tools.get_context]
approval_mode = "approve"
[mcp_servers.company-brain.tools.check_change]
approval_mode = "approve"
[mcp_servers.company-brain.tools.find_owner]
approval_mode = "approve"
[mcp_servers.company-brain.tools.trace_decision]
approval_mode = "approve"
```

Keep the shell sandbox and approval policy unchanged. This approves the four listed read-only MCP operations, not arbitrary shell execution. The server still implements five tools; this experiment exposes only four. No remember/approval operation is available to the model.

`scope` is `org` or `private`. It is not a repository name. Repository identity is selected by trusted BRAIN_CONFIG; private scope is selected by the configured principal. Source prose is untrusted, non-binding evidence.

Official references checked 2026-10-15:
- https://developers.openai.com/codex/config-reference/
- https://developers.openai.com/codex/mcp

The model-driven smoke trace in `data/experiments/readonly-mcp-smoke` records an autonomous get_context call with scope org, returning two actual excerpts and three graph paths. The response includes proposed-solution information in an issue comment; it is not the filtered corpus used for the subsequent paired trial.

Direct static import resolution is supported for repository top-level functions, import/from statements, aliases and relative imports under repository-root or src layouts. Conditional/ambiguous imports, re-exports, inheritance, closures and runtime dispatch are not resolved. Import edges carry `confidence=static`, `resolution=statically_resolved_import`. Existing self/cls calls remain heuristic. All symbols are stored before call edges. This is static evidence, not proof of runtime dispatch under monkeypatching.
