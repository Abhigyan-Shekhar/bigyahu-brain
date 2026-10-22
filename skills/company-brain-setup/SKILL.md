---
name: company-brain-setup
description: Configure or repair a locally installed Company Brain plugin, connect existing repository configs, and verify its MCP tools. Use for Company Brain plugin onboarding rather than ordinary code investigation.
---

# Company Brain plugin setup

Use the existing server and operator CLI. Read the bundled
`docs/plugin.md` relative to the installed plugin root for install/runtime details.
The plugin root is the parent of this skill's `skills/` directory; it contains
`pyproject.toml`, `uv.lock`, and `src/brain`. Commands below use its absolute path
as `PLUGIN_ROOT`; quote actual paths in shell commands.

Check `uv` and Git availability. Run
`uv sync --frozen --no-dev --project PLUGIN_ROOT` if the packaged environment is
not prepared. First-time dependency installation may require network access.
The plugin does not bundle Python binaries, database data or third-party wheels.

Call `setup_status` if available. Otherwise call `list_repositories` or
`repository_status` to inspect the current setup. The configuration priority is
`BRAIN_REGISTRY`, then `BRAIN_CONFIG`, then
`${CODEX_HOME:-~/.codex}/company-brain/registry.json`.
Some desktop transports filter custom environment variables; use the path
reported by `setup_status` in that case. The installed Codex cache path also
identifies the owning profile when `CODEX_HOME` was filtered. Keep operator files outside
the plugin cache, which may be replaced by updates. Do not overwrite existing
configs, copy credentials into the plugin, or replace unrelated MCP registrations.

For an existing config, validate it and add it with:

```text
uv run --frozen --no-dev --project PLUGIN_ROOT python -m brain register --registry ABSOLUTE_REGISTRY --config ABSOLUTE_CONFIG
```

For a new checkout, identify its actual Git root and stable repository identity.
Use the same trusted principal and memory settings as existing registry entries.
Create a config outside the checkout with `python -m brain init --repo ROOT
--config CONFIG --repo-id ID --principal PRINCIPAL`. Include `--repo-url` for a
public GitHub URL when appropriate. Use `--host` and `--port` for the intended
FalkorDB connection, then register that config as above. These commands run
through the packaged `uv run --frozen --no-dev --project PLUGIN_ROOT` environment.

FalkorDB must be running. If its connection is unknown, resolve that before
claiming setup is complete. The bundled run guide covers Docker and optional
Lite; starting the plugin alone does not start a database. For a clean committed
checkout, index with `python -m brain sync --registry REGISTRY --repo-root ROOT`
in the same environment. Preserve dirty files; never reset, stash or commit them
merely to satisfy indexing. Report indexing failures and coverage gaps.

Restart the MCP server or start a fresh chat after changing configuration.
Verify the root and matching indexed/local revisions with `repository_status`,
then perform a bounded `search_code` and `read_code` on an actual indexed file.
Distinguish a healthy setup diagnostic, tool discovery, database readiness and
verified retrieval. Switch to the company-brain skill for the investigation.

If a manually registered Company Brain server or standalone skill already exists,
explain any duplicate tools/skills. Migration is optional: preserve its settings
before removing a duplicate, and remove only the explicitly selected entry.
