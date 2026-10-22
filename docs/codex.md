# Company Brain in native Codex

Codex can use the standalone graph server directly, without launching the web
application or a nested agent. The skill supplies the investigation workflow;
MCP supplies repository evidence. This follows the official
[skills](https://learn.chatgpt.com/docs/build-skills) and
[MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) interfaces.

## Install against an already indexed repository

From the Company Brain source checkout, with Git, uv, and the Codex CLI installed:

```sh
uv sync --frozen
uv run python scripts/install_codex.py --config /absolute/path/to/brain-config.yaml --dry-run
uv run python scripts/install_codex.py --config /absolute/path/to/brain-config.yaml
codex mcp list
```

The installer validates the configuration, copies `skills/company-brain` into
`$CODEX_HOME/skills/company-brain` (default `~/.codex/skills/company-brain`), and
uses `codex mcp add` to register the current environment's Python interpreter.
Keep this source checkout and its environment available. An editable source path
is supplied explicitly so the server works regardless of Codex's working directory.
No model, API key, web frontend, or nested agent is needed for these graph calls.
FalkorDB must already be running at the configured connection.

The default config is this checkout's `config/brain.local.yaml`, when present.
Always inspect its repository identity before using it: an existing demo config
may point to Requests rather than your project. `--skill-only` installs only the
workflow. `--codex-home` isolates the installation. Differing existing skills or
MCP entries require `--force`; old skills are backed up under `skill-backups`.
An MCP replacement uses Codex's configuration writer and preserves unrelated entries.

Start a new Codex chat in the indexed checkout, then invoke:

```text
$company-brain Investigate this bug, inspect callers and prior decisions,
then implement and test a fix within my requested scope.
```

The first graph call should be `repository_status`. It identifies the configured
checkout, local/indexed revisions, dirty state, and incomplete indexing. The skill
compares these with the active project before using graph evidence. Registration
alone is not proof that the database is reachable or the index is fresh.

## Initialize another local project without the web UI

Start FalkorDB using the [local setup](../README.md#2-start-falkordb). Then create
a configuration outside the target checkout (or in a gitignored location):

```sh
uv run python -m brain init \
  --repo /absolute/path/to/project \
  --config /absolute/path/to/brain-config.yaml \
  --repo-id github.com/owner/project --repo-url https://github.com/owner/project \
  --principal local_operator --port 6379 --sync
uv run python scripts/install_codex.py --config /absolute/path/to/brain-config.yaml
```

Use a stable repository ID, the same ID used by any existing index. Initialization
accepts an optional public GitHub URL for source citations and later enrichment.
For a local-only repository, omit `--repo-url`; public source links and GitHub
enrichment will be unavailable. Initialization
never overwrites a config, clones a repository, or starts a database. `--sync`
uses the existing bounded Python/Git indexer and requires a clean committed tree.
If indexing fails the config remains available for repair and a later retry:

```sh
BRAIN_CONFIG=/absolute/path/to/brain-config.yaml uv run python -m brain sync
```

Without `--sync`, only the config is created. This base path indexes Python
structure, repository file metadata, ownership and bounded Git history. GitHub
discussion snapshots, documents and Graphify enrichment use the separate existing
operator commands. Non-Python call graphs are not supported by this indexer.
For TLS, credentials, tenant or memory options, edit the validated YAML using
the existing [configuration examples](../config/brain.example.yaml).

## Use one installation across registered projects

Create one validated config per checkout with `brain init` above. Use the same
trusted principal, tenant and optional memory settings for every entry. Keep the
registry outside indexed checkouts, for example in your Codex home:

```sh
uv run python -m brain register --registry /absolute/path/to/registry.json --config /absolute/path/to/project-a.yaml
uv run python -m brain register --registry /absolute/path/to/registry.json --config /absolute/path/to/project-b.yaml
uv run python scripts/install_codex.py --registry /absolute/path/to/registry.json
```

When switching an existing single-config MCP registration to registry mode, use
`--force` after inspecting the installer's `--dry-run` output. The registry
contains only versioned absolute config paths, not credentials. It allows up to
64 checkouts and rejects duplicate roots or mixed identities/catalog settings.
Registration uses an atomic write and a fail-fast writer lock; a stale `.lock`
directory needs operator inspection before removal. Referenced configs are
validated on registration and server startup.

In a new Codex chat, `$company-brain` reads the current Git root and calls
`list_repositories`. Every repository tool then requires `repo_root`; there is no
shared selected project. Unregistered roots fail before retrieval. Responses
identify their repository, and citation descriptors stay in separate per-root
contexts. A client cannot supply a different config, tenant or operator identity.
The existing single-config mode and its tool signatures continue to work.

After a registry/config edit, restart the MCP server or start a fresh chat so it
loads the new allowlist. Freshness is checked against live graph and Git state;
an ordinary index refresh is visible immediately. To refresh one registered root:

```sh
uv run python -m brain sync --registry /absolute/path/to/registry.json --repo-root /absolute/path/to/project-a
uv run python scripts/verify_codex_discovery.py --repo-root /absolute/path/to/project-a --repository-status --retrieve-file path/to/indexed.py
```

Sync refuses dirty trees and never commits, resets or discards files. Routing
does not automatically index arbitrary projects or start their databases. The
database in each registered config must be running. Worktrees at different HEADs
sharing one repository graph still share that graph's single indexed revision;
status exposes the mismatch rather than promising independent indexes.

## Verification and current boundaries

```sh
uv run python scripts/verify_codex_discovery.py
uv run python scripts/verify_codex_discovery.py --repository-status
uv run python scripts/verify_codex_discovery.py --repository-status --retrieve-file path/to/indexed.py
```

These check actual Codex MCP discovery and optional retrieval without a model turn.
`--retrieve-file` exercises code search, inventory, verified reads, historical
retrieval and citation reopening for an indexed file with Git history. The optional
`--check-change` verification is specifically for the indexed Requests demo
fixture, not arbitrary repositories. A successful discovery is not an end-to-end
model investigation; `repository_status` plus a real graph query establish the
database path independently.

The base server exposes eleven tools: `repository_status`, `get_context`,
`trace_decision`, `find_owner`, `check_change`, `remember`, `search_code`,
`read_code`, `repository_files`, `search_history`, and `resolve_evidence`.
Authorized memory extensions remain optional. Registry mode additionally exposes
`list_repositories` and requires an absolute `repo_root` on repository tools.
The skill selects from registered projects; arbitrary project discovery,
background synchronization and web action approval services remain follow-up work.
Native Codex edits use its own execution controls;
they do not acquire the web app's isolated, digest-locked replay guarantees.

The application and standalone server share `RepositoryRetrieval`, which calls the
same provenance and history engines. It needs no web app, active app session,
frontend, or FastAPI service. The app continues writing evidence to its per-run
ledger. Standalone retrieval keeps at most 128 citation descriptors in memory and
does not persist source excerpts. IDs expire on eviction or server restart;
retrieve again rather than treating an old ID as evidence.

`resolve_evidence` accepts exactly one of `evidence_id` (from standalone retrieval)
or `source_uid` (from graph results). It rechecks the configured repository,
revision, original bytes, provenance and topology; a changed citation returns no
checked excerpt. Evidence is always advisory and does not approve a change.
Tenant deployments recheck company access before every retrieval, including a
previously issued citation. App-specific personal/team evidence remains in its
existing authorized app workflows; the standalone memory extension is unchanged.

## Validation recorded on October 22, 2026

- Full Python suite against an isolated FalkorDBLite engine: 655 passed, 1 skipped.
- A clean synthetic Git repository was initialized and indexed through `brain init --sync`.
- Installation into a fresh isolated Codex home succeeded, including a second installation.
- Actual `codex app-server` discovery returned all eleven base tools; protocol tool
  calls verified matching repository revisions, indexed code search, path inventory,
  source reads, historical retrieval and exact citation reopening against FalkorDB.
- Source-byte changes, removed graph provenance, unknown/cross-repository IDs,
  stale indexes and revoked company access fail closed in regression tests.
- Importing the standalone server loaded neither FastAPI nor the app server.
- Registry routing additionally passed an actual Codex protocol smoke check and
  a two-repository STDIO regression: root isolation, cross-root citation rejection,
  dirty sync refusal and live refresh without server restart. Interleaved in-process
  calls retain their explicit roots; registry conflicts/mixed identities fail closed.
- Ruff and skill frontmatter validation passed. No model-driven investigation was
  run; the smoke check verifies the tool transport and database path.
