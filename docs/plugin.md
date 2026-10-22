# Company Brain desktop plugin

This package combines the existing native Codex skill, a setup skill and the
standalone Python MCP server. It uses portable `plugin.json` and `mcp.json`
manifests plus a generated Codex compatibility overlay. It follows the official
[plugin packaging](https://developers.openai.com/plugins/build/plugins) and
[desktop-only MCP](https://developers.openai.com/plugins/deploy/desktop-only)
layouts. It does not require the web application or a second agent harness.

## Build and install locally

You need Git, Python 3.11+, uv and a Codex client with local plugin support.
From this repository:

```sh
python scripts/build_plugin.py
codex plugin marketplace add "$PWD/dist/company-brain-plugin/marketplace"
codex plugin add company-brain@company-brain-local
```

The builder refuses an existing output directory. Use `--output` with a fresh
directory for subsequent builds. It produces a self-contained server-source ZIP,
a SHA-256 checksum and a local marketplace directory. The allowlist includes
only paths explicitly listed in `packaging/company-brain/files.json`: server
Python source, both skills, manifests, the dependency lock, selected
documentation and the Lite/discovery helper scripts. It excludes `.git`, local
configs, registry contents, secrets, runtime databases, model traces, tests,
frontend build output and virtual environments. New source files require a
reviewed entry in that manifest; unlisted files are excluded even inside source
and skill directories. Hidden files, local YAML configs, keys and escaping paths
are rejected even if added to the manifest.

The ZIP contains one top-level `company-brain/` folder. Share it with your team,
or share the generated marketplace folder to install from a local source. The
marketplace resolves its plugin relative to the marketplace root, so move the
entire folder together. No artifact upload or public-directory submission is
performed by the builder. Installing directly from this source Git repository
without building the marketplace is not supported.

The **Desktop plugin package** GitHub Actions workflow also publishes the built
directory as a downloadable CI artifact named `company-brain-desktop-plugin`.
After extracting that artifact, add its `marketplace` directory with the same
commands above. It includes the plugin ZIP and checksum; it is not a public
directory listing or a GitHub Release.

The plugin launches `uv run --frozen --no-dev` against its own installed source.
It requires uv on PATH. Python and third-party wheels are not bundled: first
launch may download the locked dependencies and create a virtual environment in
the plugin cache. To prepare it ahead of time, locate the installed plugin root
using `codex plugin list` and run:

```sh
uv sync --frozen --no-dev --project /absolute/path/to/installed/company-brain
```

The MCP declaration uses `${PLUGIN_ROOT}` so it follows the installed cache copy.
Configuration uses the desktop client's process environment. Restart the client
after changing exported configuration variables, or use the default registry path.
Some clients filter custom environment variables. When `CODEX_HOME` is absent,
the launcher derives the owning Codex profile from its installed
`plugins/cache/<marketplace>/<plugin>/<version>` path, falling back to `~/.codex`
for other layouts. Custom profiles therefore keep their own default registry.

## Configure a fresh installation

The plugin declares `extensions.com.openai.onboardingSkill` in both manifests.
Run the client's setup action after installation to open the packaged guided
workflow in a new or existing chat. You can also invoke the plugin's
`$company-brain:company-brain-setup` skill directly.
With no config, the MCP server
exposes a read-only `setup_status` diagnostic rather than claiming graph readiness.
Configuration priority is:

1. Explicit `BRAIN_REGISTRY`.
2. Explicit `BRAIN_CONFIG`.
3. `company-brain/registry.json` under `CODEX_HOME`, or `~/.codex` by default.

These overrides apply when the client forwards them. The default profile registry
is the supported configuration route when it does not.

Keep configs and the registry outside the installed plugin cache. Existing
registries created by the native installer work without conversion. For a new
project, follow [native initialization and registry setup](codex.md) using
`uv run --frozen --no-dev --project /absolute/plugin/root python -m brain ...`.
All registered configs must share the same trusted identity and memory settings.

FalkorDB must be running at each configured connection. For macOS/Linux, the
bundled `scripts/run_lite.py` can be run through the plugin environment with
`--extra lite` and Python 3.12. Docker is the alternative on Windows; the plugin
does not silently install or start a database. The standard indexing limits and
clean committed-checkout requirement still apply.

Restart the MCP server or start a fresh chat after configuration. A configured
registry exposes `list_repositories` plus the eleven repository tools; every
repository call requires the active absolute `repo_root`. A single config exposes
the eleven original standalone tools. Use the plugin's
`$company-brain:company-brain` skill for investigations. These are the qualified
names exposed by the tested Codex client; desktop skill pickers can show shorter labels.
Memory review, authorization and native-edit approval boundaries are unchanged.

## Existing manual installations

The standalone skill/MCP installer remains supported. Installing the plugin does
not delete an existing manually registered `company-brain` server or standalone
skills. If you see duplicate tools, inspect `codex mcp get company-brain --json`
and the installed skill paths before choosing which integration to use. Remove
only the duplicate you explicitly select; retain its config/registry. Keep one
installation route enabled for routine work so tool selection is clear.

## Distribution boundary

This is a local/team desktop plugin package. It has not been submitted to or
approved for the public Plugins Directory. Official OpenAI documentation states
that public submissions of local MCP servers require an allowlisted submitting
organization; packaging does not establish that eligibility.

## Validation

The package was installed using `codex plugin marketplace add` and `codex plugin
add` in an isolated Codex home. The CLI discovered both packaged skills and
launched the MCP server from its cache copy using only the locked base Python
dependencies. With no config, `setup_status` reported that profile's missing
registry. After registering a clean fixture and restarting the server, actual
Codex protocol calls verified repository/index revisions and returned code
excerpts checked against source bytes and native FalkorDB paths.

CI verifies the ZIP checksum, extracts it into a fresh profile, installs its locked
base dependencies, and launches its declared MCP command. It checks `setup_status`
before configuration, then indexes a clean fixture against an isolated FalkorDB
and verifies a configured MCP `read_code` result against the source. This test
uses the packaged stdio server without requiring a model or Codex account. Run it
locally against a disposable running database with:

```sh
python scripts/verify_plugin_package.py dist/company-brain-plugin/company-brain-0.1.0.zip --port 6379
```

Package tests check deterministic ZIP bytes, unlisted source exclusion, checksum and
marketplace resolution, setup behavior, explicit configuration and isolated
profile detection. No public plugin submission or account-wide replacement of
the existing manual installation was performed by these checks.
