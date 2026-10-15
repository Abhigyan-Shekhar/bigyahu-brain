# FalkorDBLite integration — 15 October 2026

## Outcome

FalkorDBLite works on this Apple Silicon Mac with Python 3.12.13. Installed:
FalkorDBLite 0.10.0, FalkorDB Python driver 1.8.0, libomp 23.1.3. The running
engine reports Redis 8.6.2 and graph module version 41803 (FalkorDB 4.18.3).
This is newer than the previously proposed Docker image 4.14.7; these results
prove compatibility with the measured Lite engine, not every FalkorDB version.

The installed Lite wrapper uses the existing falkordb-py Graph API. No graph
schema change, MCP contract change, alternate query engine, or database adapter
was necessary. Cloud TLS configuration remains available and unchanged. No Cloud
resources were provisioned and no further Podman repairs were attempted.

Upstream references:
- https://github.com/FalkorDB/falkordblite/blob/master/README.md
- https://docs.falkordb.com/operations/falkordblite/falkordblite-py

## One owner, many ordinary clients

Use a single explicit Lite owner process. It opens the database file and exposes
the embedded engine only on 127.0.0.1:6379. Sync, operator CLI, tests and MCP use
the existing network driver; they do not instantiate independent embedded
wrappers against the same file. The owner holds an exclusive advisory file lock;
a second launcher for that file fails. This lock protects cooperating launchers,
not arbitrary programs that ignore it. Do not open the runtime file directly
from additional Lite wrappers.

Persistence uses AOF with every-second fsync and SAVE on graceful shutdown.
Keep the entire `data/runtime/lite/` directory, including AOF files, not just the
RDB file. A sudden crash can lose roughly the latest second of writes under this
fsync policy. This is a development setup, not a hostile local-user security
boundary. Concurrent database clients were tested; concurrent repository syncs
are still unsupported. Finish sync before relying on change reports.

## Start and verify

Python 3.12 is required for the Lite extra. From this project:

```sh
brew install libomp
uv sync --frozen --extra lite --python 3.12
export PYTHONPATH="$PWD/src"
export BRAIN_CONFIG="$PWD/config/brain.local.yaml"
.venv/bin/python scripts/run_lite.py --db "$PWD/data/runtime/lite/brain.rdb"
```

Leave that terminal running. In another terminal, with the same PYTHONPATH and
BRAIN_CONFIG:

```sh
.venv/bin/python -m brain sync
.venv/bin/python -m brain ingest-snapshots data/sources
BRAIN_INTEGRATION=1 BRAIN_LITE_TESTS=1 .venv/bin/pytest -q
.venv/bin/python scripts/verify_codex_discovery.py --check-change \
  --output data/demo/lite-codex-call.json
```

Stop the owner with Ctrl-C (or SIGTERM); it shuts down with SAVE. Start the same
command to recover the database. The existing Codex configuration and local YAML
already target this loopback endpoint; no configuration change was made.

## Measured checks

- 41 tests pass with both integration flags enabled; no skipped tests in that run.
- Five live integration tests cover repeated sync, caller traversal, full-text
  search, poisoning/non-binding proposals, private-data isolation, approval and
  supersession, rejection of unrelated supersession, stale checkout downgrade,
  and all five tools through a separate STDIO MCP process.
- One separate lifecycle integration test verifies two independent writer
  processes, client exit without server shutdown, duplicate-owner rejection,
  and persisted data/full-text indexes after owner restart.
- Approval tests simulate operator input only for synthetic fixture repositories.
  No real Requests decision has been approved by the agent.
- Requests at `611c6162cbc4ac2020a2f91c7cfa4f3abf9bbb60` synced: 131 files,
  807 symbols, 2,492 unresolved static calls. 21 public issue/PR snapshots ingested.
- Repeated real sync retained 1,276 repo-scoped nodes. One measured repeat sync
  took approximately 1.72 seconds; this is a single observation, not a benchmark.
- The path `resolve_redirects → rebuild_auth → should_strip_auth` was checked
  against the actual Python AST. Method-call edges remain labeled heuristic.
- A proposed constraint on `rebuild_auth`, sourced to Requests issue #4716,
  appears in the target's `review`; `must_preserve` is empty as required.
- After restarting the main owner, the real graph count, revision, proposal,
  full-text results, and Codex call were checked again successfully.

Artifacts: `data/demo/lite-tests.xml`, `lite-metrics.json`, `lite-codex-call.json`,
`lite-service-check.json`, and `lite-proposal.json`. These are local research records and are ignored by Git. Earlier versions were
tracked and exposed local environment metadata; see `security-remediation.md`.
Only the reviewed exports under `docs/demo/` are intended for publication.

## Compatibility issue fixed

The existing bootstrap expected `db.indexes()` to yield `type`. The real engine
rejects that field. It returns `types`, a map from each indexed property to its
index kinds. Bootstrap now inspects that map and creates only missing full-text
properties. Repeated bootstrap/sync passes on the real engine. This issue would
not have been detected by the original mocked tests.

## Remaining work and limits

The saved Codex trace is an actual `mcpServer/tool/call` executed by Codex's
app-server in an ephemeral protocol session. It proves Codex → MCP → FalkorDB and
returns real graph evidence. It does **not** prove that a separate Codex model
selected the tool, authored a patch, or improved a baseline. No model turn or
persistent new chat was created by that verification script.

Next: run the frozen refactor prompt in separate clean baseline and graph-enabled
checkouts, capture model-selected pre-edit tool calls and actual tests/diffs, and
measure whether the graph changes validation or implementation. The existing
Requests candidate may already be handled by the baseline; reject it if it shows
no added value. A real binding decision still needs independent human review.
Browser/video validation remains pending; Lite does not start the Docker Browser
web service. Cloud connectivity remains unverified and optional.
