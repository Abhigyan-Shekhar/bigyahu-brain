# Clean setup, recovery and operations

## Preserve the demonstration

The default five-tool prototype and frozen experiments remain usable. Every
extension validation uses new graph namespaces, new database directories and an
unused loopback port. Do not sync, approve, reindex, restore or ingest into an
existing approved experiment database. No automatic migration targets that graph.

```sh
uv sync --frozen --extra lite --extra memory --python 3.12
export PYTHONPATH="$PWD/src"
python scripts/prepare_memory_model.py \
  --revision 1110a243fdf4706b3f48f1d95db1a4f5529b4d41 \
  --output data/runtime/models/minilm-v1
```

Use `uv run --frozen --extra lite --extra memory python` or the environment's interpreter for the Python
commands. Model provisioning is the only model-download step; runtime checks
hashes and loads local artifacts only. Keep the Apache-2.0 model provenance and
review any upstream notices with the deployed artifact. Without `--extra memory`
and without an embedding directory, the catalog works with lexical search and
returns `vector_not_configured` explicitly. Native Windows uses Docker for graph
tests; see the [Browser portability runbook](browser-demo/README.md).

Copy `config/brain.memory.example.yaml` to ignored `config/memory.local.yaml`.
Choose an absolute clean checkout, stable repository identity, new database path,
tenant/principal and unused port. Start a new Lite owner in another terminal:

```sh
uv run --frozen --extra lite --extra memory python scripts/run_lite.py --db data/runtime/memory/brain.rdb --port 6395
export BRAIN_CONFIG="$PWD/config/memory.local.yaml"
uv run --frozen --extra lite --extra memory python -m brain sync
uv run --frozen --extra lite --extra memory python -m brain ingest-docs README.md
uv run --frozen --extra lite --extra memory python -m brain health
uv run --frozen --extra lite --extra memory python -m brain.memory_cli --config "$BRAIN_CONFIG" health
```

The catalog uses schema version 2. Opening a version-1 catalog transactionally
adds an empty relationship-assertion table and advances its schema marker; existing
records, grants, imports, vectors and audit events are preserved. Unsupported
schema versions fail. Backups/restores accept versions 1 and 2; opening a restored
version-1 copy applies the same additive migration. Keep a backup before upgrades.
The optional catalog server exposes seven tools; graph mode adds an eighth,
`memory_graph`. Omitting `memory_db` keeps five. The MCP process must
not receive `BRAIN_OPERATOR_SESSION`. Keep configuration and catalog inaccessible
to unrelated OS users; no Windows ACL or multi-host identity isolation is implied.

Graph-enabled `memory_search` now defaults to the native Falkor engine. Run the
existing operator `sync-graph` once after upgrading to create/repair its full-text
index. The read-only CLI `search --query 'upload replay' --backend falkor` exercises
the same path; `--backend catalog` preserves the earlier optional-vector baseline.
See [native retrieval](falkor-memory-retrieval.md) for scope/company flags and bounds.

## Separate human operator actions

In an independently controlled interactive terminal, review the scope and set
`BRAIN_OPERATOR_SESSION=1` for the specific command. Each action requires typing
its exact confirmation. The following are operator examples, not agent steps:

```sh
BRAIN_OPERATOR_SESSION=1 uv run --frozen --extra lite --extra memory python -m brain.memory_cli --config "$BRAIN_CONFIG" \
  grant --principal alice --brain company --role reviewer
BRAIN_OPERATOR_SESSION=1 uv run --frozen --extra lite --extra memory python -m brain.memory_cli --config "$BRAIN_CONFIG" \
  grant --principal alice --brain team:backend --role writer
```

Use role `revoke` to remove shared membership. Reader, writer and reviewer grants
are independent; a team filename never creates one. `review --brain ... --uid ...
--hash ... --action accept|reject|expire|rollback --reason ...` displays the
exact record/citations and checks the reviewed hash. Graph decisions use existing
`approve` plus `review-decision --action reject|expire|rollback --reason ...`.
Memory acceptance does not activate a graph decision.
`brain review-history <decision_id>` prints the linked bounded audit trail.
`brain approve <decision_id> --expires-at <future-ISO-8601>` records an explicit
expiry; omission preserves the existing no-expiry decision behavior.

Session exports are curated `{"format":"session/1","session":"id",
"selected_memories":["explicitly selected note"]}` JSON. Compute its canonical
digest, inspect/redact it, then the operator runs `import-session <file>
--consent-digest <digest>`. The command asks for exact-digest consent; all entries
stay private proposals. `import-abhi <file.abhi>` requires current team write
membership and produces only proposals. Neither format reads arbitrary logs.

## Sync, refresh, retry and deletion

`python -m brain sync-github --output data/runtime/github/<new-capture>` acquires
bounded read-only GitHub API data through the existing `gh` login. The captured
manifest contains repository identity, checkout revision, cursor and source hash.
Cursor moves only after a complete publish. Preserve failed captures privately;
retry with a new output directory. Use periodic `--reconcile` for child edits and
deletions. Large histories that exceed bounds need an explicitly partitioned
repository/window policy before proceeding; do not accept truncated success.

Native `ingest-docs <selected paths>` reuses stable logical section keys while
preserving immutable version citations. Failed graph refreshes leave a reader
fence; rerun that operation successfully. `retire-docs <paths>` is a human-only
logical retirement of current graph links. It does not erase historical evidence.

Catalog `memory_cli ingest-docs --brain <brain> --source-base <HTTPS-or-URN> <paths>`
atomically refreshes explicitly selected documents and removes missing sections.
It treats them as source evidence, never policy decisions. Entire-document
erasure uses explicit `delete --brain ... --uid ...` for its current section IDs.
`purge-expired --brain ...` erases expired content and vectors. Model changes use
operator `reindex --brain ...`; never mix vector model identities silently.

After edits, `verify-citation <local-source-file> --start <line> --end <line>
--sha256 <excerpt-digest>` compares the actual cited text. A mismatch requires
retrieval and plan review, not silent acceptance of a stale quote.

## Backup, restore and health

`memory_cli backup <new-file>` uses SQLite's consistent backup API and refuses
overwrite. Hash the result and store it under the same private retention policy.
`restore <backup> <new-database> --sha256 <digest>` requires separate human
confirmation, verifies checksum/integrity/schema and restores only to a new path.
Replay later deletion tombstones and membership revocations before adopting a
restored catalog; an old backup must not resurrect erased material or access.
This replay is an operator step, not an automated distributed deletion ledger.

For Lite, stop the dedicated owner gracefully with SAVE and preserve its entire
persistence directory, including AOF files. Restore a complete copy into another
directory with another port/owner and run health, source and permission checks
before switching config. Never open the same files with two Lite owners or copy
only an RDB while omitting AOF state. Docker follows its persistent-volume backup
procedure. No online cross-version engine migration or HA claim is made.

`brain health` reports graph revision/sync fences. `memory_cli health` reports
schema, integrity and model identity without returning private record counts.
Authorization errors return `scope_unavailable`; bounds/model conflicts explain
recovery; transport/database failures do not return cached apparently valid facts.

## Reproducible checks

```sh
PYTHONPATH="$PWD/src" uv run --frozen --extra lite --extra memory python scripts/validate_memory_foundation.py \
  --model-dir data/runtime/models/minilm-v1 \
  --benchmark-output data/validation/memory-benchmark.json
uv run --frozen --extra lite --extra memory ruff check src tests scripts
```

The helper allocates disposable engine paths/ports and stops every owner with
SAVE, including failures. It runs all live tests, then starts a separate empty
engine for the retrieval benchmark. Raw logs/configs/databases stay ignored.
Parser comparison is opt-in in an isolated comparison environment with the
pinned upstream checkouts; those projects are not runtime dependencies.

## Optional semantic extraction and local viewing

`import-conversation --semantic-model MODEL` sends the exactly consented selected
envelope to a fresh Codex process for durable-span/literal-entity selection. It
uses existing Codex authentication and account model usage; omit this option to
retain deterministic extraction. Record proposals and correction link proposals
require their existing separate review steps before acceptance. Refresh each
affected graph projection after review.

Run `python -m brain.memory_viewer --config /ABSOLUTE/PATH/memory.local.yaml` to
inspect current authorized slices as the configured principal. Open the printed
loopback session URL; reopen it after reload. Do not expose this local viewer as
a hosted multi-user service. Member selection shows authored shared memories in
the currently selected scopes, without access to another private brain.
See [the integration guide](graphify-three-brain-integration.md) for Graphify
ingestion, model boundaries and the guided demonstration commands.
