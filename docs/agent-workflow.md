# Reproduce the graph-aware coding demonstration

This workflow uses Codex CLI, the existing Company Brain STDIO MCP server,
FalkorDBLite, and the already indexed urllib3 repository. No backend or ingestion
change is required. See [the actual run report](agent-demo-results.md) for results
and failures. Model output is nondeterministic; reproducing the protocol does not
guarantee an identical patch or a successful result.

## Prerequisites and boundaries

- Company Brain based on merged backend `070dc03`, Python 3.12, dependencies from
  `uv.lock` with the Lite extra, Codex CLI 0.162.0-alpha.17.2, authenticated Codex.
- Existing local upstream checkout `.checkouts/urllib3` containing revision
  `a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`, plus uv's cached locked test dependencies
  (or network access to obtain them).
- One running FalkorDBLite owner, using the already populated database. See
  [Lite startup instructions](lite-integration.md). Never launch another owner
  against the same file, or modify the indexed namespace during the run.
- The existing `experiment:urllib3:5181:eligible` namespace must be present. It
  contains merged historical PRs #3780 and #5161; solution PRs #5191/#5242 and
  solution-revealing #5181 material are excluded. The preflight fails closed if
  these known exclusions fail. It is a targeted contamination check, not a proof
  against every possible semantic leak. Do not substitute the unfiltered graph.

A clean public clone does not include the database or private research bundle.
The commands below reproduce against the existing indexed repository/database,
which is an explicit prerequisite; they do not claim zero-input graph rebuilds.
The public oracle is included and needs no private bundle.

The runner disables apps/plugins/web and automatic project documents, ignores
user Codex configuration, starts an ephemeral workspace-write session, and
removes `BRAIN_OPERATOR_SESSION`. Four read-only tools are approved; `remember`
is disabled for this model run. The backend still exposes all five original MCP
tools with unchanged signatures. The coding shell retains workspace-write sandboxing. Checkout-only access and
avoidance of evaluator material are prompt restrictions audited from
emitted commands, not a hostile-user security guarantee.

## Fresh coding run

Run from the Company Brain root. Use a new label and checkout every time; all
output directories are exclusively created. Paths passed to the runner must be
absolute. The model gets only `agent-task.txt` and `agent-instructions.txt`.
Never include prior patches, oracle code, prior traces or evaluator feedback.

```sh
export BRAIN_ROOT="$PWD"
export LABEL=demo-fresh-1
export WORK="/tmp/company-brain-$LABEL"
export RECORDS="$BRAIN_ROOT/data/experiments/$LABEL"
export SHA=a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8
mkdir -p "$RECORDS"
git clone --no-hardlinks "$BRAIN_ROOT/.checkouts/urllib3" "$WORK"
git -C "$WORK" checkout --detach "$SHA"
uv sync --offline --frozen --python 3.12 --group test --project "$WORK"
```

Copy `config/agent-demo.example.yaml` into `$RECORDS/brain.yaml`, replacing
`repo_root` with the absolute resolved `$WORK` (on macOS `/tmp` resolves to
`/private/tmp`). Use the existing endpoint settings; never publish credentials.
Then run:

```sh
PYTHONPATH="$BRAIN_ROOT/src" "$BRAIN_ROOT/.venv/bin/python" \
  scripts/capture_agent_corpus.py --config "$RECORDS/brain.yaml" \
  --out "$RECORDS/corpus-before.json"
"$BRAIN_ROOT/.venv/bin/python" scripts/run_codex_agent.py \
  --work "$WORK" --out "$RECORDS/graph-1" \
  --task "$BRAIN_ROOT/docs/agent-task.txt" \
  --instructions "$BRAIN_ROOT/docs/agent-instructions.txt" \
  --model gpt-6.1-sol --reasoning high --revision "$SHA" \
  --brain-config "$RECORDS/brain.yaml" \
  --brain-python "$BRAIN_ROOT/.venv/bin/python" --brain-src "$BRAIN_ROOT/src"
PYTHONPATH="$BRAIN_ROOT/src" "$BRAIN_ROOT/.venv/bin/python" \
  scripts/capture_agent_corpus.py --config "$RECORDS/brain.yaml" \
  --out "$RECORDS/corpus-after.json"
```

Compare the before/after `snapshot_sha256`. Preserve and investigate any mismatch.
The preflight reads via the driver only for operator verification; the model
retrieves evidence through MCP. Expected workflow: independent local inspection,
org historical retrieval, `check_change` before edits, explanation of evidence
versus local-code knowledge, source/test edits and verification.

Local artifacts preserve the exact prompt/invocation, runtime versions,
runner bytes/hash, backend revision, dependencies, timestamps, emitted JSONL,
MCP arguments and responses, commands, final answer, patch including new files,
and completion state. Started/completed events share IDs: count completed calls
once. Requested model identity is recorded, not independently attested. Emitted
JSONL does not expose hidden reasoning or establish complete read isolation.

## Independent evaluation, only after the agent exits

The unchanged public oracle has SHA-256
`d077b08c3c911fc146f59305ca305d3f216749e0218727b4e3b3adbabe7ff3d0`.
It checks 12 real HTTP socket scenarios, including bare-pool controls. The
selected upstream suite also runs new regression tests added to the selected
files. Run these with permission to bind loopback sockets; an agent sandbox
failure is not a passing test.

```sh
"$BRAIN_ROOT/.venv/bin/python" scripts/evaluate_agent_run.py \
  --work "$WORK" --run "$RECORDS/graph-1" \
  --oracle "$BRAIN_ROOT/docs/demo/oracle.py" \
  --oracle-sha256 d077b08c3c911fc146f59305ca305d3f216749e0218727b4e3b3adbabe7ff3d0
```

The evaluator verifies the imported urllib3 path, captures both exact commands
and actual outputs, and returns nonzero if either check fails. Read
`evaluation/summary.json` and `upstream-results.txt`; do not equate a completed
agent turn with correctness. Never repair the patch between agent completion
and evaluation. Save failures and stop repeated attempts if the task stays
unsuccessful; choose a smaller genuine task based on source evidence.

Raw outputs and configurations stay in ignored `data/experiments/`. Use
`scripts/audit_agent_runs.py` for a local read-only inventory if needed. Publish
only manually reviewed summaries and source patches. Check the staged tree and
reachable history with `scripts/check_publication.py --history` before committing.
No baseline improvement claim follows from this single demonstration.

## Native three-brain runner mode

Use `--memory-graph` with an enabled graph/catalog config to expose both
`memory_search` and `memory_graph` alongside the four historical read-only tools.
`remember` and `memory_propose` remain disabled. The config must point at the
coding checkout and use the trusted tenant/principal; no caller identity inputs
are accepted. Baseline and existing `--memory-search` invocations are unchanged.

The [fresh guided three-brain fixture](graphify-three-brain-integration.md) uses
consented conversation proposals, synthetic review and selected team/company
sharing, then launches a real fresh Codex process. It preserves raw local traces
and runs a separate oracle; see [verification](three-brain-agent-verification.json).
This experiment does not replace the historical frozen urllib3 comparisons.
