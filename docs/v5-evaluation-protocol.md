# v5 paired evaluation protocol — fixed before trials

Status: protocol prepared; no trials on the v5 graph yet. Do not start until the
independent human approval/supersession and corpus freeze have passed.

- Task: verbatim `docs/agent-task.txt`; common instructions:
  `docs/v5-agent-instructions.txt`. Copy these unchanged outside each checkout.
- Repository: urllib3 at `a37bc93b65d6bcf00d3dc43d966bab6bd130ecd8`.
- Corpus: only #3780/#5161 public snapshots, pinned Git/code, the three documented
  repository documents, and independently approved D-2 (with superseded D-1 retained).
  No #5181/#5191/#5242 source material, previous patches, oracle or run outcomes in
  agent context. Existing adjacent upstream 303 tests remain visible in both arms.
- Freeze using `scripts/rebuild_demo_graph.py --phase freeze`; keep the exact
  corpus, oracle, protocol and backend file hashes with each run. Reject a pair
  if the corpus changes during it. Never resync or add facts during trials.
- Same model `gpt-6.1-sol`, reasoning `high`, 900-second timeout, runner revision,
  Python/dependency environment, task and common instructions for both arms.
  If that model is unavailable, revise and hash this protocol **before** any run;
  do not pool results from different settings. Record the resolved model from
  the actual session when available, rather than assuming an alias is immutable.
- Baseline has no Company Brain MCP. Graph arm gets only `get_context`,
  `check_change`, `trace_decision`, `find_owner`; no remember, operator capability,
  arbitrary database access, web research, oracle or prior solutions.
- Both use the same sandbox and runner. Each starts in a fresh clean checkout
  and ephemeral model session. Outputs live outside the work tree. Never repair
  a failed run, reuse its conversation, or cherry-pick the old passing patch.
- Planned order: baseline-1, graph-1, graph-2, baseline-2, baseline-3, graph-3.
  Evaluate only after each agent exits. All attempted sessions stay in the table.
  Stop at a completed pair if quota/time threatens the working demo. Usage limits,
  timeouts, discovery failures and incomplete retrieval are explicit outcomes.

## Success criteria

A successful coding session must complete within its budget, pass **all 12/12**
independent socket-oracle cases (including 303 disposal and bare-pool checks),
and pass the fixed selected upstream suite in `scripts/evaluate_agent_run.py`.
The evaluator requires exactly 12 oracle results, with every result passing;
upstream counts come from pytest JUnit XML, and an empty/all-skipped suite fails.
Report actual collected/pass/fail/skip counts; do not substitute the older run's
200 tests. Record patch hash, model/effort, exit status, elapsed time, tool calls,
retrieval completeness, and whether the active constraint reached the model.

For each arm report successful sessions / attempted sessions, oracle cases per
session, upstream outcomes, time and tool overhead. Incomplete sessions stay in
the attempted denominator with their failure reason; also show completed-only
counts separately. A descriptive difference is graph success fraction minus
baseline success fraction. **At n=3 per arm all differences are anecdotal**;
there is no significance or general lift claim. A tie or no difference in 303
preservation is valid and expected given the visible upstream tests.

Evidence reaching the model, model-reported influence, observed edits and measured
correctness are separate observations. Do not infer causality from co-occurrence.
The pre-v5 12/12 demonstration remains an earlier-graph execution artifact and
cannot be shown as the consequence of v5 docs or approval.
