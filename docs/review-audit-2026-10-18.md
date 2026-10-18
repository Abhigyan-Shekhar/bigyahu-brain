# Audit of the pasted Company Brain review

Audited 18 October 2026 IST against HEAD
`642402176c0143a35ae139470f791a84e6b10d17`, the current working tree, and
GitHub repository/Actions metadata. No application source, existing demo
records, repository settings, or remote state were changed during this audit.

The review is substantially accurate about release and presentation gaps.
Its strongest recommendations remain justified. However, Docker is green,
some proposed UI capabilities already exist, and newer local validation
material establishes more than the review describes.

The working tree already contained edits to `README.md` and
`docs/submission-demo/README.md`, plus seven untracked follow-up files. These
predate this audit. Their results must be distinguished from the committed
submission package and its CI checks.

| Review claim | Audit verdict | Current evidence and qualification |
| --- | --- | --- |
| Latest release CI fails on Windows exported-patch replay | **Confirmed** | Latest portability run has exactly two failing replay parameterizations: 277 passed, 105 skipped. macOS, Ubuntu, frontend build, and Docker jobs passed. Publication boundary also passed. |
| Docker is failing | **Incorrect if read as a Docker-job failure** | The combined workflow is named “Portability and Docker demo”; its Docker job succeeded. The pasted review mostly identifies Windows correctly, but the workflow name can obscure this distinction. |
| Coding plans lack citation-relevance screening | **Confirmed** | `prepare_plan` checks evidence authenticity through `verified_claims`, validates file/test selections, checks the revision, and exposes the plan for approval. It does not invoke `relevance.assess`. Chat does invoke it and withholds unsupported/uncertain claims. |
| Submission draft describes obsolete v5 implementation | **Confirmed** | It still says Graphify, GraphRAG SDK and semantic document extraction are absent, describes a STDIO-only deployment, and contains a pending video URL. Current code and README include those ingestion capabilities and the local web application. |
| Repository still needs public release | **Confirmed** | `gh repo view` returned `PRIVATE`, default branch `master`. No visibility change was made. Logged-out access and a real submission receipt were not established. |
| First demo: 126 targeted passes and 16/16 independent checks | **Consistent with saved evidence** | The committed receipt, patch and demo README describe these results. The first guided run was not independently rerun during this audit. |
| Second demo's automatic regression gate remains false | **Correct historically; incomplete as a description of current validation** | The historical receipt remains false. New local follow-up files establish a separate clean assertion failure → pass and full-suite checks. This audit independently reproduced those newer results below. |
| Graph-specific coding advantage is not demonstrated | **Confirmed, with existing evaluation to acknowledge** | A frozen six-session baseline/graph comparison already exists: both arms succeeded 3/3, with no correctness advantage. Synthetic retrieval comparisons also exist. The gap is demonstrated causal benefit for the current three-brain action, rather than absence of all evaluation. |
| Fresh discovery proves autonomous investigation | **Supported with limits** | Saved records describe the symptom-only prompt and 16 read calls. The plan explicitly requested memory contributions; synthetic reviewed notes contain hints and an exact code identity. This is not a clean-room graph-necessity benchmark. The current nine read tools are listed in `agent.py`. |
| Main invitation emphasizes Q&A; Personal/Team are hidden | **Confirmed in source** | The heading remains “What would you like to understand?”; Personal and Team Brain are under “More workspace tools.” This audit did not repeat a live usability study. |
| Need a “Why this fix?” view with reopenable evidence | **Partially implemented** | The plan already displays supporting claims with buttons that reopen action evidence. The evidence pane displays actual relationships and a compact graph. A concise explanation grouping code, requirement, reviewed memory and history by their effect on the proposed change is missing. |
| Need a before/after result card, diff and honest verification | **Largely implemented; presentation gap remains** | Original/patched results, command outputs, diff download, and explicit unverified/baseline-error text already exist. Independent replay is documented separately, not integrated into the action report. The overall result text uses the green `test-pass` class whenever `tests_passed` is true, including an unverified fix. The wording is conservative, but the color deserves correction. |
| Need visible knowledge coverage | **Partially implemented** | “Repository coverage & extraction” already exposes warnings and Graphify counts. Backend onboarding labels GitHub partial coverage and stores structured coverage metadata. A compact source-by-source summary with freshness remains absent. |
| Initial history is limited to 20 recent issue/PR items | **Confirmed** | `github_initial.py` selects up to 20 recently updated work items and budgets requests. It checks whole selected items rather than claiming full history. `search_history` returns incomplete with no items above its 1,000 candidate-source-row bound. |
| Knowledge can become stale | **Confirmed with qualification** | Manual incremental GitHub sync, reconciliation, document refresh/deletion and revision fences exist. No always-on webhook/synchronization service was found. “No synchronization” would overstate the gap. |
| Structural Graphify entities inflate Document counts | **Confirmed** | Graphify structural nodes are stored as `Document`; the UI displays raw `Document` label counts alongside File/Symbol/Source. This can be interpreted as a document count despite the mixed representation. |
| Public-repo and small-document ingestion restrictions | **Confirmed** | App cloning requires a public GitHub repository; checkout, file, document and extraction bounds are explicit. These are current product limits. |
| Permission-aware prototype, not hosted multi-user identity | **Confirmed** | Server uses loopback binding, a local bearer session and fixed `app_operator` principal. Reviewed memory access controls exist; they should not be described as hosted organizational authentication. |
| Walkthrough is 100 seconds of edited still frames | **Confirmed by manifest/disclosure** | The manifest and demo README explicitly disclose format, omitted waits, no audio and captions. This audit did not rewatch the supplied recordings or independently decode the video. |

Relevant implementation anchors:

- [Plan preparation](../src/brain/app/actions.py), `prepare_plan`, lines 283–348;
  [chat screening](../src/brain/app/agent.py), lines 181–217;
  [provenance validator](../src/brain/app/evidence.py), `verified_claims`.
- [Action interface](../frontend/src/ActionPanel.jsx), lines 178–228 and 245–374;
  [main interface](../frontend/src/main.jsx), lines 442–449, 641, 676–690 and
  1083–1096.
- [Onboarding](../src/brain/app/sources.py), `onboard`;
  [partial history acquisition](../src/brain/ingest/github_initial.py);
  [history search](../src/brain/app/history.py), `search` (the `search_history` tool);
  [manual incremental sync](../src/brain/ingest/github_sync.py).
- [Graphify structural storage](../src/brain/ingest/graphify.py), lines 178–205;
  [submission draft](submission-draft.md);
  [existing paired evaluation](v5-evaluation.md).

## Independent verification performed

**CI inspection.** Queried the exact HEAD's jobs and failure logs through `gh`.
The [portability run](https://github.com/Abhigyan-Shekhar/bigyahu-brain/actions/runs/39076546905)
fails at `git apply` in both
`test_downloaded_patch_applies_in_fresh_checkout` cases. The
[publication run](https://github.com/Abhigyan-Shekhar/bigyahu-brain/actions/runs/39076546857)
succeeded. These authenticated links require repository access while it is private.

**Line-ending reproduction.** In disposable macOS repositories, simulated a
source Git configuration with `core.autocrlf=true`, CRLF source text, and the
current `clone_at`/`patch_for` helpers. The clone helper suppresses global Git
configuration, yielding LF replay bytes. The exported patch is LF after Python
text-mode decoding. Feeding it through the equivalent Windows text-mode stdin
translation (LF → CRLF) reproduces `x.py: patch does not apply`; supplying UTF-8
LF bytes passes `git apply --check`. The trailing-whitespace warning is not the
blocking error. This isolates a reproducible transport/configuration mismatch;
the exact hosted Windows environment was not independently executed here.
Fixing only the old stripped-final-newline defect does not address this mismatch.

**Focused application checks.** Executed:

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_app_actions.py tests/test_app_review_fixes.py
```

Result: **33 passed, 1 skipped**; the skipped check requires live FalkorDB.
An initial invocation without `PYTHONPATH=src` failed collection because this
local virtual environment does not expose the package; setting the source path
resolved collection without a repository change. No live database was modified.

**Independent signed-token replay.** Created fresh temporary clones of
`672971d66a2ef9f85151e53283113f33d642dabd` from the available local repository.
Applied the actual `three-brain.patch` only to the patched clone. Its SHA-256,
`0b2937cbe3577e4a49bb35139cf6050d60ccb95fa936a5994d1906bf558a795f`, matches both
the historical and follow-up receipts. Ran identical follow-up test files using
the current interpreter and existing Codex OS test sandbox, with network disabled
and pytest plugin autoload disabled:

| Check | Original | Patched |
| --- | --- | --- |
| Minimal timestamp regression | 1 assertion failure, 0 errors | 1 passed |
| Signature compatibility | 6 passed | 6 passed |
| Complete upstream suite, plus patch tests where present | 297 passed | 305 passed |
| Patched suite plus both follow-up files | — | 312 passed |

The current `verification_result` returns `regression_demonstrated=true` for
the separate matched minimal check. The historical action remains false. The
review's warning about that historical flag remains valid; saying the bug has
only targeted/ambiguous validation is now outdated for the local working tree.
These checks validate this artifact and contract, not general agent superiority.

## Recommended priorities after the audit

1. Fix patch bytes/line-ending handling and verify the actual Windows job.
2. Extend relevance review to planning, including whether the proposed action
   follows from the evidence; authentic claims alone do not justify arbitrary steps.
3. Reconcile the submission draft with the implemented app and reviewed demo.
   Include the new follow-up artifacts in the intended release if they are to
   support public claims; preserve the historical results.
4. Improve existing plan/result views: summarize why evidence changed the plan,
   make unverified results visually distinct, surface source coverage and separate
   structural entities from document counts. Reuse existing citation/graph plumbing.
5. If time permits, run a controlled comparison for the current three-brain task.
   Retain the existing tied evaluation and disclose synthetic hints. A successful
   graph path or model self-report alone does not establish necessity.

The competition's current capabilities, event rules/deadline, live submission
form, prize prospects and visual quality of the recordings were not independently
reassessed. They are external or subjective claims, not conclusions established
by this repository audit. Public release and submission remain operator actions;
this audit neither requested nor performed them.
