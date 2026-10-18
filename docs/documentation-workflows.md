# Documentation and bounded workflows

The baseline [design specification](agent-documentation-and-orchestration.md) is
retained separately from the historical implementation guide. This page describes
the actual features and boundaries.

## Docs

Open **Docs** in a repository workspace, or **Create documentation** after a
completed investigation. Completed patch runs also offer **Document this patch
run**, which attaches the real execution record rather than inventing a fix.

Choose architecture, runbook, incident, ADR, API guide, change summary or custom;
describe the desired document in ordinary language. A read-only research process
retrieves code, history, indexed documents and authorized evidence. Existing
investigation/action evidence is reopened and revalidated before reuse. A second
model reviews claims and the document outline against those sources. This is a
fallible semantic review, not guaranteed correctness.

The model returns cited claims and section membership; the backend constructs
the Markdown and nearby source references deterministically. Factual paragraphs
cannot bypass the checked-claim list. Proposed next actions and limitations have
their own clearly labelled sections. The rendered preview escapes text and never
executes HTML. Use source buttons to inspect original text and graph provenance.

Drafts are immutable, content-addressed UTF-8 artifacts, limited to 60 KiB. A
revision request creates a new unapproved version and preserves earlier approved
versions. It does not overwrite an approved artifact. Raw Markdown, source
citations, a diff against the current target file, and `.md` download are available.

Two destinations remain distinct:

- **App Docs:** approve the exact digest and source revision to save the artifact
  locally. **Index approved App Doc** is a separate optional action. Indexed
  sources have `source_kind=agent_generated_document`, reviewed provenance and
  `binding=false`. They cannot be reused as independent factual support by the
  documentation author or coordinator, which prevents self-citation loops.
- **Git repository patch:** prepare the target change in a disposable clone,
  inspect the exact diff, then approve export. The backend applies it to another
  fresh clone and compares exact resulting bytes. Download the approved patch.
  Nothing is applied, committed or pushed to the original indexed checkout.

Automatic suggestions stay under `docs/**/*.md`. Users may explicitly select
another Markdown target, including `README.md`; hidden paths, configuration,
secrets, traversal, symlinks, case collisions and non-Markdown files are rejected.
Documentation checks are separate from code testing. Ordinary code plans still
require Python tests, exact approval, isolated execution and patch replay.

An old document remains visible after a source change but is marked stale, and
its approval/index/export actions are rejected. Regenerate for current evidence.
Downloading historical prose does not claim it is current or indexed.

## Auto-investigate

Open **Auto-investigate** from Ask Brain or Agent Runs. State the original goal,
check the opt-in box, and select allowed draft outcomes. Research is always
enabled; documentation, fix planning, GitHub issue/comment/PR and email drafts
are individually optional. The capability selection is permission, not a promise
that every artifact will fit in one run.

Limits are server enforced: four executed steps, eight model invocations including
planning/relevance checks, 900 seconds of active wall time, 60 aggregate retrieval
calls, and the existing per-run retrieval limits. Model timeouts are clamped to
the remaining budget. A bounded partial result is expected when a broad request
does not fit; the UI shows the real stopping reason and retains prepared artifacts.
The coordinator never fabricates future steps or resets consumed usage on resume.
No token or monetary estimate is presented as measured usage.

The model proposes one structured next task at a time. Server code checks the
capability, read-tool allowlist, current parent evidence, duplicate task signature
and budget. Fresh research workers cannot use shell, editing or publication tools.
Each task is a `workflow_step` child, not a fake user message or a recursively
submitted chat turn. Prompts and sources are untrusted data; the original selected
repository and user capability grant remain fixed.

Expand actual timeline rows for the reason, completion criteria, sources, evidence
gaps and prepared artifacts. Tool/requested-model provenance and prompt hashes
remain in durable records; private reasoning is not displayed. Select **Stop** to
request cancellation. The research subprocess is terminated; a tool-free review
already in progress may take until its bounded call returns before the workflow
reaches its final stopped state. Resume is available only for stopped/failed/input
states with remaining budget and unchanged evidence. Clarification does not expand
capabilities or approve actions. A server restart fails active work visibly; it
does not automatically replay child tasks or external effects.

## Review queue and connectors

Prepared artifacts appear under their producing timeline step:

- Document drafts open the same Docs review UI.
- Fix plans use the existing cited plan review, exact-digest approval, isolated
  editor and real baseline/patched test pipeline. The timeline shows the actual
  plan, test output and downloadable diff. It never edits the indexed original.
- GitHub issues, conversation comments and draft PR descriptions remain local
  drafts until **Publish exact GitHub draft**. The account/repository/content
  checks still apply, and workflow source evidence is revalidated. Comment targets
  and existing pushed PR branches must be entered by the user.
- Email drafts retain the exact recipient, sender, subject and body. Recipients
  must be entered in workflow settings, never inferred from documents. Configure
  the [SMTP sender](email-connector.md), refresh the sender preview if needed, then
  explicitly choose **Approve & send this exact email**. This sends the reviewed
  text without regenerating it. The original standalone Email panel keeps its
  explicit **Generate & send** action; workflows do not invoke that action.

No workflow publishes, sends mail, accepts memory, changes grants, merges,
deploys, commits or pushes automatically. GitHub and email transports keep their
unknown-outcome and no-automatic-retry semantics. SMTP provider acceptance is not
proof of inbox delivery. Review generated statements and recipient scope before
publishing them outside the application.

## Validation

Focused tests cover forged/revoked/stale citations, immutable artifacts and
approval digests, generated-source provenance, no recursive citation, new/existing
Markdown patch replay, unsafe paths, Python code gate preservation, bounded model
calls and retrieval, cancellation, duplicate steps and drafts-only compound flows.
The compound fixture prepares documentation, a reviewed fix plan, a GitHub issue
draft and an email draft without posting or sending anything.

The full disposable-engine validation runner remains:

```sh
PYTHONPATH=src .venv/bin/python scripts/validate_memory_foundation.py
```

Frontend tests include safe cited Markdown rendering. Provider responses and model
outputs in automated authoring/coordinator tests are fixtures; this does not measure
live-model completion quality or performance. Browser visual verification depends
on local browser access being enabled. No external messages are sent by tests.
