# Final hardening and submission readiness — 18 October 2026 IST

The hardening checkpoint was recorded locally against base
`642402176c0143a35ae139470f791a84e6b10d17`. The validation table below records that
checkpoint; subsequent live execution is described separately below. This report supersedes the earlier audit
only for the changes and checks described here; historical demo receipts and the
frozen comparison are unchanged. See [the original audit](review-audit-2026-10-18.md)
and [machine-readable verification](final-hardening-verification.json).

## Implemented versus reused

**Patch transport:** Git diffs are captured as bytes, including CRLF, final
newlines, trailing spaces and new-file additions, then decoded as UTF-8 without
universal-newline translation. JSON and the existing browser Blob download retain
that string; replay uses UTF-8 bytes. Editor reads/writes and saved patch artifacts
also avoid platform newline translation. Isolated clones persist
`core.autocrlf=false`; repository `.gitattributes` remains effective. Export
includes full index identities/binary support and rejects new-file diff errors.
Before publishing a completed action report, the backend applies its final patch
to a fresh recorded base, compares all edited/deleted file bytes, and rechecks
source authorization/provenance. This replay is labeled separately from test
execution: it does not rerun tests or prove their coverage.

**Plan evidence:** the existing provenance validator and tool-free relevance
reviewer are reused. A new planning schema asks the planner to explain how each
claim informs the change. One relevance call assesses each claim/rationale and the
whole action: objective, code, documents, reviewed memories/history, file scope,
steps, preservation requirements and test selections. Any unsupported/uncertain
material claim or action stops the plan before approval. Review results are bound
to the exact inputs and approval digest. Sources, access, native graph and revision
are checked again after review and at approval/execution. Legacy plans without
this screening cannot authorize a new run; historical completed reports remain
inspectable. Accepted memories and imported assertions remain advisory.

Review input is capped at 150 KB UTF-8, 20 claims and eight citations per claim;
there is one tool-free model call with the existing 180-second timeout. Failure,
timeout, malformed or incomplete review stops the plan. Deterministic provenance
and fallible semantic judgment are explicitly distinguished. No model-based
review guarantees truth, completeness, causal necessity or improved performance.

**Interface:** retained the existing graph, citation pane, action form, test
outputs and diff download. Added visible Personal/Team navigation, action-oriented
headings and three working prompt starters, stage labels, and a compact “Why this
fix?” presentation within the existing plan. Source categories come from verified
support metadata; rationale comes from the planner and is screened with the plan.
Unavailable categories are omitted. Repository Markdown read through `read_code`
is identified as a repository document rather than program code. Test commands
are labeled “for approval” while pending. Unverified overall fixes use qualified
neutral styling; green regression status requires the existing demonstrated
regression signal. Individual passing tests still report their actual outcomes.
Historical reports explicitly keep separate follow-ups outside their original
classification.

**Coverage:** retained existing ingestion warnings and raw graph counts for
compatibility. Added presentation counts from existing `source_kind` metadata:
structural code entities, repository/uploaded sections, extracted concepts,
unknown entities, files, symbols and evidence sources. No schema migration.
Coverage shows the indexed revision, partial/unknown GitHub history, document and
entity counts, extraction counts and authorized reviewed-memory scope limits.
Counts survive neighbor navigation. The source picker exposes its listing bound.

**History:** existing ranking, work-item deduplication, file/symbol associations,
verified patch evidence, 1,000 candidate-source-row bound and manual synchronization
are preserved. A bounded history result can still be incomplete or empty despite
relevant material elsewhere. The investigation prompt now explicitly requires
material coverage warnings in answer limitations. This prompt is guidance to a
fallible model, not a deterministic guarantee that every gap will be described.
No demonstrated failure justified replacing the retrieval architecture.

**Submission:** rewrote the v5 draft around the implemented React/FastAPI,
Graphify/GraphRAG SDK ingestion, FalkorDB company/memory graphs, SQLite authority,
`.abhi/2`, nine read-only application tools, reviewed plans, isolated execution and
verification/lesson workflow. Linked the pre-existing sanitized signed-token
follow-up artifacts into the release material. Preserved the historical false regression flag,
guided/symptom-only distinction, synthetic hints, edited-walkthrough disclosure,
local-operator limitation and tied six-session result. Corrected the ingestion
guide's obsolete claim that uploads do not queue model extraction.

## Validation

| Check | Result |
| --- | --- |
| Final isolated FalkorDBLite/Graphify/memory/application/process suite | **406 passed, 0 skipped**, 3 dependency deprecation warnings |
| Focused action and plan checks after replay tests were added | **45 passed**, 3 dependency deprecation warnings |
| Frontend production build | Passed; existing upstream React Flow `use client` warning |
| Ruff over `src`, `tests`, `scripts` | Passed |
| `git diff --check` | Passed |
| Index and reachable-history publication scan | Passed at existing HEAD/index |
| Working-tree scan including intended untracked follow-ups | Passed; text-boundary scan, not a general security certification |
| Actual Windows CI for modified source | **Not run**; changes are unpushed |
| Latest remote Windows run | Still fails on old `6424021`; Docker/macOS/Ubuntu/client passed there |

Commands:

```sh
PYTHONPATH="$PWD/src" .venv/bin/python scripts/validate_memory_foundation.py
PYTHONPATH="$PWD/src" .venv/bin/python -m pytest -q tests/test_app_actions.py tests/test_plan_relevance.py
npm run --prefix frontend build
.venv/bin/ruff check src tests scripts
git diff --check
python3 scripts/check_publication.py --history
```

The new replay matrix covers source `core.autocrlf` true/false, LF/CRLF, explicit
LF/CRLF attributes, tracked edits plus a new file, trailing whitespace and missing
final newlines. It round-trips the JSON/download artifact through binary replay
and compares bytes. Original two replay cases remain present. Execution tests also
prove a corrupt-but-applicable export cannot publish a successful replay report.
Plan tests cover authentic unrelated citations, unsupported actions, unresolved
conflict, revoked evidence after review and before approval, changed source and
revision, unavailable/timed-out reviewer, malformed assessments, input bounds and
legacy approval rejection. Existing live permission/revocation tests passed in
the complete suite. Disposable database owners stopped with SAVE.

Validation failures retained for interpretation: an initial offline invocation
with relative `PYTHONPATH=src` passed 303 tests and skipped 99 but failed two
cross-directory process tests because the package was not discoverable in child
working directories. Absolute source paths in the documented validation harness
resolved this without changing those tests. An intermediate integration run
passed 403 tests and failed a new display assertion that expected 106 unknown
entities from a fixture creating 105; correcting that expected count resolved it.
The final 406-test suite includes two later execution/replay cases.

## Real planner and browser checks

A fresh, explicitly synthetic retry-policy fixture was created in a separate
FalkorDB namespace and application catalog. Real `gpt-6.1-sol` Codex investigation
and relevance calls were used; tools/evidence were not faked.

1. The initial plan was withheld as uncertain: its policy/input domain was
   ambiguous and the reviewer also demanded repository evidence for the
   operator-supplied standard-library runtime. The failed result remains in local
   audit storage. The reviewer prompt now identifies that runtime as an application
   capability while retaining optional-dependency uncertainty.
2. A separate request explicitly scoped the fixture to integer inputs and the
   supplied unittest runtime. The fresh plan's two claims, rationale and whole
   action were supported; deterministic rechecks passed and it reached
   `awaiting_approval`. This is a clarified fixture run, not a selected success
   from a coding-performance benchmark. Neither plan was approved or executed.

Desktop browser inspection verified the real reviewed plan, source categories,
contribution rationale, citation reopening with current source bytes and an actual
FalkorDB path, coverage labels and entity counts. Each of the three starter
buttons populated the real composer and focused it. No starter prompt was sent.
The preview used only disposable synthetic data; its server and database owner
were stopped after inspection. Screenshots and raw model traces remain ignored
locally. Mobile layouts and a full new live editing/test journey were not
independently acceptance-tested in this turn; the existing sandbox probes and
backend execution regressions passed.

## Subsequent live browser acceptance

After this checkpoint, a new post-hardening action completed investigation,
evidence and graph inspection, plan review, explicit human approval, isolated
editing, baseline/patched tests, browser patch download and a proposed Personal
Brain lesson. The first plan failed literal-file validation; the corrected plan
was reviewed before approval. Seven test methods produced 37 baseline subtest
assertion failures and passed after editing. The downloaded patch matched the
action bytes, replayed cleanly, and passed an independent 16/16 reproduction and
304-test upstream suite (original: 4/16 and 297 tests). The lesson remains
proposed. Synthetic documents and hint-bearing memories were reused; this is not
a comparative performance experiment. See the [live receipt](live-demo-verification-2026-10-18.json).

The earlier browser inspection paragraph describes its own checkpoint, before
this later completed journey. The machine-readable hardening receipt likewise
retains its original uncommitted-checkpoint status. Branch publication and CI
status should be read from the associated pull request.

## Exact file inventory

Changed implementation and tests:

- `src/brain/app/actions.py`
- `src/brain/app/action_mcp.py`
- `src/brain/app/relevance.py`
- `src/brain/app/evidence.py`
- `src/brain/app/agent.py`
- `src/brain/app/server.py`
- `frontend/src/main.jsx`
- `frontend/src/ActionPanel.jsx`
- `frontend/src/IngestionPanel.jsx`
- `frontend/src/style.css`
- `scripts/verify_app_actions.py`
- `tests/test_app_actions.py`
- `tests/test_plan_relevance.py` (new)
- `tests/test_chat_knowledge_workflow.py`

Changed/new release documentation:

- `docs/submission-draft.md`
- `docs/company-brain-actions.md`
- `docs/semantic-document-ingestion.md`
- `docs/final-hardening-2026-10-18.md` (this report)
- `docs/final-hardening-verification.json` (new)
- `README.md` (adds the current report while preserving pre-existing follow-up edits)

Preserved pre-existing local changes/artifacts referenced by the release copy:

- `docs/review-audit-2026-10-18.md`
- `docs/submission-demo/README.md`
- `docs/submission-demo/baseline-error-analysis.json`
- `docs/submission-demo/followup-verification.json`
- `docs/submission-demo/inspect_timestamp_conversion.py`
- `docs/submission-demo/original-baseline-tracebacks.txt`
- `docs/submission-demo/test_signature_compatibility.py`
- `docs/submission-demo/test_timestamp_regression.py`
- `docs/submission-demo/traceback-review.md`

Built frontend assets remain ignored, as before. No unrelated local artifacts
were staged, committed, deleted or published. Historical patch/receipt content
hashes were checked against HEAD and remain unchanged.

## Release blockers and demo narrative

Actual Windows acceptance remains a release gate. The local regression matrix
passes, but it cannot substitute for a new Windows job. At the hardening
checkpoint the latest GitHub run was for unchanged HEAD. The user subsequently
authorized a new branch, commit, push and pull request. No visibility change,
deployment, public video upload or submission is included in that authorization.
Public access, the live submission form and its requirements, and a submission
receipt remain unverified. There is no new graph-versus-flat-versus-plain coding
benchmark; the frozen baseline/graph 3/3 tie remains the only six-session result.

The demo narrative is now: **Investigate → inspect why this fix → review the exact
plan → approve isolated editing → compare original and patched tests → inspect the
replayable diff → review a lesson.** Use real code/document/memory paths to explain
what informed the change. Disclose the synthetic hints and show the second
signed-token action's conservative false flag beside its separate clean regression
and 297/305/312 full-suite follow-up. Do not claim the graph was necessary, that
passing tests alone verify a fix, or that the historical demo used the new gate.

The subsequent [demo usability follow-up](demo-usability-2026-10-18.md) records
the stopped-plan diagnosis, clearer counts, focused views, activity display and
actual Windows CI acceptance for the original hardening commit.
