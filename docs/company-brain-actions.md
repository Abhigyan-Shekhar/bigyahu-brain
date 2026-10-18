# Approved coding actions

The local application can turn a completed cited investigation into a fix plan,
then produce an isolated patch and test report after explicit operator approval.
The original indexed source remains unchanged. There is no apply, commit, push,
merge or memory-acceptance endpoint.

## Workflow

1. Ask a repository question and inspect its cited source.
2. Choose **Plan a change**, describe the desired result, and prepare a cited plan.
   A fresh read-only Codex process chooses its own investigation tools. The server
   checks source bytes, literal quotations and native graph evidence again.
   One tool-free, fallible model assessment then reviews both claim support and
   whether the entire action follows from the objective and evidence, including
   its stated rationale, preservation requirements and test selections. All
   material claims and the action must be supported; uncertain/conflicting or
   unrelated evidence stops approval. The input is bounded to 150 KB UTF-8,
   20 claims/eight citations each and one existing 180-second model invocation.
   Provenance and authorization are rechecked after that invocation and again
   at approval/execution. Preferences and imported statements remain advisory.
   Legacy plans without this review must be regenerated before a new execution;
   historical completed reports retain their original classification.
3. Review the summary, steps, permitted files, exact test commands and citations.
   Reject the plan or choose **Approve isolated execution**. Approval consumes the
   exact plan digest once. Revision, evidence or plan changes require a new plan.
4. A separate editor receives digest-checked `read_file` / `write_file` tools for
   the approved paths in a fresh clone. It cannot run tests or shell commands.
5. The backend runs the approved commands against original code with proposed
   test-file changes, then against patched code. It rechecks patch scope and source
   evidence before publishing the report. A failing baseline helps demonstrate a
   regression, but baseline failure is not required for every legitimate change.
6. Inspect baseline/patched output and the final diff; download the patch. The
   backend also applies the byte-preserved UTF-8 artifact to a fresh base and
   compares edited file bytes. This replay checks patch transport, not independent
   test correctness, and does not rerun tests. Passing tests without a matched
   regression use a qualified neutral status; a separate follow-up does not
   rewrite the original action's automatic verification.
   The
   implementation handoff is generated before backend test validation. The test
   report carries the execution result. Draft lessons remain proposals until separately accepted in
   [Personal Brain](personal-brain-app.md). The report can send a regression-backed lesson
   directly to that review screen.

Concurrent approval retries consume one lifecycle transition. A failed execution
cannot reuse approval; prepare a new plan. Restarted running/queued jobs fail
visibly. Uploads pause while a plan awaits review or execution so cited documents
cannot change underneath approval.

## Supported execution and limits

Use the [application setup](company-brain-app.md), an installed compatible Codex
CLI with granular named permission profiles and its OS sandbox, and the existing
Python runtime. The verified local CLI was `codex-cli 0.163.0-alpha.10.2`. See the
[Codex permissions documentation](https://learn.chatgpt.com/docs/permissions).
The runner invokes `codex sandbox` directly with a generated profile; incompatible
or unavailable sandbox execution fails closed. macOS was verified with actual
host-file denial and loopback-network denial probes. Linux is supported only when
its installed CLI/OS can enforce the profile; it has not been acceptance-tested
here. Native Windows coding execution is unavailable; read-only chat still works.

- One to twelve approved relative files; Python, Markdown, RST, text or TOML;
  100 KB per edited file, 200 KB total displayed patch. Hidden paths, symlinks,
  absolute paths and traversal are rejected. New test files must be approved.
- One to three generated `python -m pytest` or `python -m unittest` path selections.
  Arbitrary flags, shell commands and dependency installation are unavailable.
- Tests can read the checkout and installed Python runtime, write the disposable
  checkout/scratch area, and have no network access. Git metadata is read-only.
  The subprocess environment excludes inherited credentials/operator variables.
  Runtime directories must contain trusted operator-installed packages.
- Each test command has 120 seconds and 512 KB combined output. Process groups are
  terminated on completion, timeout or overflow; only the output tail is displayed.
  Zero reported tests cannot count as a passing run. Test counts are runner output,
  not independent proof that tests cover the objective.
- Changes outside approved paths, including ignored untracked files, prevent report
  publication. Tests may write inside the disposable checkout; final scope is
  audited again. This is a local operator prototype, not an enterprise execution
  service or a guarantee against malicious tests falsifying their own output.

No dependencies are fetched. Projects needing unavailable packages stop with a
visible failure. Keep runtime traces, application SQLite state and clones under
ignored `data/runtime` or `data/validation`; source-hash manifests identify the
backend code used for each model invocation.

## Reproduce the synthetic acceptance run

The existing real-public-repository investigation remains documented in the
[first milestone report](application-milestone-verification.json). Coding approval
was separately exercised on a deliberately small synthetic retry-policy fixture,
clearly labelled in the UI. Its example GitHub URL is not a real hosted repository.

With an existing running local application and its database owner, add a new
fixture namespace (this does not approve or execute anything):

```sh
PYTHONPATH=src python scripts/prepare_app_action_fixture.py \
  --config /ABSOLUTE/PATH/config/app.local.yaml \
  --data /ABSOLUTE/PATH/data/runtime/company-brain-app/sources \
  --model gpt-6.1-sol
```

Select **Synthetic coding acceptance fixture** in the UI. Ask why retry intervals
stay unchanged across attempts and how invalid inputs should behave. Prepare a
plan to fix the policy and add standard-library unittest regression tests. Review
and approve the displayed plan. No file names or prescribed tool order are needed
in the question. The model can vary its plan, patch and tests between runs.

After completion, independently verify its action ID:

```sh
PYTHONPATH=src python scripts/verify_app_actions.py \
  --config /ABSOLUTE/PATH/config/app.local.yaml \
  --data /ABSOLUTE/PATH/data/runtime/company-brain-app/sources \
  --action ACTION_ID --output data/validation/action-report.json
```

The verifier checks approval/evidence, rejects consumed approval replay, applies
the downloadable patch to a fresh clone and runs 15 held-out oracle cases through
the OS sandbox. Original code must fail the oracle. It accepts only the explicit
synthetic fixture, never approves a plan and never applies to the original source.
The oracle itself is not passed to the planning/editor prompts.

[Recorded result](application-action-verification.json): the actual model wrote
six regression tests, which failed on original code and passed on patched code;
the reproduced downloadable patch passed all 15 oracle cases. The original
checkout stayed clean. This demonstrates the approval-to-report plumbing on this
fixture, not general coding quality. The separate
[Personal Brain verification](application-personal-verification.json) now checks
private lesson review and fresh-chat recall; [Team Brain](team-brain-app.md)
provides selected sharing and separate review. The
[integrated synthetic demo](application-integrated-demo.md) now combines imported
team memory, company policy, approved coding and later reviewed-lesson recall.

Validation also includes approval tampering/replay/concurrency, authentication,
path and command injection rejection, ignored-file scope violations, actual macOS
filesystem/network sandbox probes, timeout/output caps and zero-test rejection.
Run `scripts/validate_memory_foundation.py` with the documented app/lite/graphify
extras for the full disposable graph suite.

## Passing tests and regression evidence

`tests_passed` requires successful exits and positive reported test counts for
every approved patched command. `regression_demonstrated` additionally requires
proposed tests on the baseline, matching command selections and reported case
counts, and at least one original-code assertion failure resolved by the patch.
Timeouts, runner errors, collection errors and a baseline that already passes do
not provide this signal. The API exposes `fix_verification` and the report labels
a passing run without this signal **Tests passed · fix remains unverified**.

Only a demonstrated regression can propose a new coding lesson. Explicit notes
and existing accepted memories retain their normal review workflow. This checks
test-run evidence; it cannot establish that agent-written tests cover the reported
bug. Review coverage and independent acceptance evidence separately.
