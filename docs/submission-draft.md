# Company Brain — submission draft

Prepared 18 October 2026 IST. This is reviewable submission copy, not a submitted
entry. Repository visibility, public video hosting, live form fields and submission
confirmation remain unverified release steps. Do not change visibility or submit
without explicit operator authorization.

**Project:** Company Brain

**One-line description:** An evidence-grounded engineering agent that connects
code, history, documents and reviewed Personal/Team Brain knowledge in FalkorDB.

**Repository:** https://github.com/Abhigyan-Shekhar/bigyahu-brain

**Differentiator:** Company Brain connects current code with engineering history,
documents and reviewed personal/team knowledge so a coding agent can investigate
why something exists, make an informed change, and show the evidence behind that
change. Connected retrieval and inspectable paths are demonstrated; incremental
coding-performance benefit remains unproven.

## What is implemented

The working product is a **React frontend and FastAPI backend** for one trusted
local operator. A repository workspace combines conversational investigation,
source inspection, interactive FalkorDB graphs, reviewed memory and a human-approved
coding-action loop. It is not production multi-user SaaS.

- **Company evidence:** Python AST structure, conservative static callers, Git
  history, bounded public GitHub issues/PRs/comments/reviews, repository Markdown/
  RST and uploaded Markdown, RST, text-based PDF and DOCX. Onboarding uses a
  shallow, bounded public repository checkout and an explicitly partial sample of
  up to 20 recent issue/PR work items. Selected items are imported whole. Manual
  incremental GitHub synchronization and reconciliation exist; always-on sync
  and arbitrary semantic identity resolution do not.
- **Structural and semantic extraction:** pinned Graphify 0.9.92 structural
  extraction supplements authoritative Python AST relationships with advisory
  code entities. Uploads queue supported Graphify semantic extraction. The optional
  FalkorDB GraphRAG SDK 1.4.0 ingestion integration uses its real extraction/
  resolution pipeline through the configured Codex model and a validated staging
  adapter. SDK vector indexing and SDK retrieval/completion are not implemented.
  Extracted relations retain literal source evidence and remain advisory.
- **Three brains:** Personal Brain imports explicitly selected, consented
  conversation spans as private proposals. Team Brain shares selected reviewed
  records through membership/access checks and destination review. `.abhi/2`
  selectively transfers reviewed records and optional reviewed relationships;
  imported assertions do not authenticate the original author or establish policy.
- **Graph and catalog:** FalkorDB supplies company and native memory graph
  traversal, exact/full-text retrieval and inspectable source paths. SQLite is
  authoritative for memory permissions, review, lifecycle and audit records.
  Personal/team records remain repository-scoped. There is no hosted organization
  identity, automatic federation or production-scale completeness claim.
- **Agent investigation:** an isolated read-only Codex process chooses among nine
  application MCP tools: `get_context`, `check_change`, `find_owner`,
  `trace_decision`, `search_code`, `read_code`, `search_history`, `memory_search`
  and `memory_graph`. Identity and scope are fixed by the server. Source excerpts
  are untrusted data. Published citations recheck source bytes, access and native
  graph provenance; chat adds a fallible model relevance assessment.
- **Actions:** a separate planning run proposes an exact file scope and supported
  pytest/unittest selections. The hardening changes add claim-and-action relevance
  screening before approval, followed by another deterministic freshness/access
  check. An unsupported or uncertain material claim/action stops the plan. Model
  relevance judgment is fallible; it does not replace human review. Reviewed
  preferences and imported memories never become binding company policy.
- **Execution and learning:** digest-bound one-shot human approval authorizes
  constrained editing in an isolated clone. Exact commands run through the Codex
  OS sandbox with network disabled and bounded time/output. Original-plus-proposed
  tests and patched tests are reported separately. Exported UTF-8 patch bytes are
  applied to a fresh base and compared against edited file bytes. This artifact
  replay does not rerun tests or establish independent correctness. A coding
  lesson remains a proposal and must pass the existing regression/review gates.

The local application requires installed/authenticated Codex and GitHub CLIs,
Git, the documented Python/Node environment and a dedicated FalkorDB instance.
Approved editing/tests require a supported Codex OS sandbox; Windows patch
portability checks do not establish native Windows sandbox support.
[Complete setup](company-brain-app.md), [action workflow](company-brain-actions.md),
[document ingestion](semantic-document-ingestion.md),
[memory architecture](memory-architecture.md),
[transfer format](abhi-format.md), and [graph model/setup](../README.md).

## Demonstrated signed-token workflow

The public demo artifacts target `pallets/itsdangerous` revision
`672971d66a2ef9f85151e53283113f33d642dabd`.

The first run was **guided** and produced a two-file isolated patch: its original
code plus proposed tests reported **14 failed, 112 passed**, while patched code
reported **126 passed**. Separate fresh-clone reproduction reported **4/16
original, 16/16 patched**. [First receipt](submission-demo/verification.json).

A second conversation used a **symptom-only prompt**, made 16 read-tool calls and
selected company code/documents without the prompt naming files. Reviewed demo
memories were synthetic and included implementation hints and an exact code
identity. The subsequent planning request explicitly asked for personal/team
contributions. Its recorded memory path is a real `MENTIONS → RESOLVES_TO` path;
it does not prove the graph was causally necessary.

The second approved patch passed eight unittest methods and separate 16-case
reproduction. Its historical automatic regression flag remains **false** because
the original run contained five assertion failures and 18 conversion errors
across subtests. The gate was not weakened and the historical action is unchanged.
[Second receipt](submission-demo/three-brain-verification.json),
[plan](submission-demo/three-brain-plan.json),
[path](submission-demo/reviewed-memory-path.json).

Separate follow-up validation inspected every error and used identical checks
against fresh original/patched clones under the same interpreter and network-disabled
Codex OS sandbox. The audit independently reproduced:

| Check | Original | Patched |
| --- | --- | --- |
| Minimal authentic extreme-timestamp regression | 1 assertion failure, 0 errors | 1 passed |
| Invalid-signature compatibility | 6 passed | 6 passed |
| Complete upstream suite, plus patch tests where present | 297 passed | 305 passed |
| Patched suite including both follow-up test files | — | 312 passed |

The separate minimal check satisfies the existing automatic regression criterion.
It does not retroactively change the second action. The replayed
[three-brain patch](submission-demo/three-brain.patch) SHA-256 is
`0b2937cbe3577e4a49bb35139cf6050d60ccb95fa936a5994d1906bf558a795f`.
[Follow-up report and commands](submission-demo/traceback-review.md),
[machine-readable receipt](submission-demo/followup-verification.json),
[repository audit](review-audit-2026-10-18.md).

Those historical receipts predate the new plan-review gate. A subsequent
[live browser run](live-demo-verification-2026-10-18.json) exercised the hardened
planner through explicit approval and isolated execution using the same synthetic
documents, repository and hint-bearing memories. Its first plan failed literal
file validation; the corrected plan passed review. Seven methods produced 37
baseline subtest assertion failures and passed after editing. Independent replay
of the downloaded patch passed 16/16 reproduction cases and 304 upstream tests
(original: 4/16 and 297 tests). The lesson remains proposed. This does not establish
a graph performance advantage. Current hardening checks and remaining gaps are in
[the hardening report](final-hardening-2026-10-18.md).

## Evaluation and limitations

The [frozen six-session comparison](v5-evaluation.md) is retained unchanged.
Baseline and graph conditions each succeeded **3/3**, with **12/12** independent
socket cases per session. **No correctness advantage was observed.** Only two
graph sessions received the approved preservation constraint before editing; all
12 Company Brain responses were incomplete/unknown. This is a small historical
comparison, not evidence of general speed, accuracy or graph necessity.

The product also has small, disclosed synthetic retrieval/path fixtures. Do not
present their acceptance cases as a broad benchmark. Large repositories, missing
static edges, bounded candidate sets, stale snapshots, model extraction/relevance
errors and ingestion/model latency remain material limitations. Source-backed
paths establish provenance and association, not automatic semantic truth.

## Demo narrative and media

“Describe a bug. Company Brain investigates current code, engineering documents,
recorded history and authorized reviewed knowledge. Inspect the evidence and the
small graph path behind a proposed fix. Review its claims, rationale, files and
exact tests; approve isolated execution. Compare original and patched behavior,
inspect the actual diff, and keep test passes distinct from demonstrated
regressions. Review any lesson before sharing it.”

Show the three-brain signed-token example with its synthetic-hint disclosure and
historical false regression flag, then the separate clean regression and complete
suite follow-up. Explain the evidence contribution without claiming performance
superiority.

The local [walkthrough](submission-demo/walkthrough.mp4) is a **100-second edited,
captioned still-frame presentation of captured application states**, with waits
omitted, not uninterrupted real-time footage. [Captions](submission-demo/captions.srt)
and [capture manifest](submission-demo/capture-manifest.json) retain the disclosure.
It predates the hardening UI. No public hosted video URL is verified here.

## Original work and submission checks

Built in this repository with OpenAI Codex assistance. Waggle is used for
project-development conversation memory; no Waggle implementation is copied.
Public upstream code/history are attributed; synthetic requirements and reviewed
notes are ours, not upstream maintainer policies. Graphify and the FalkorDB SDK
are dependencies, not original frameworks authored here.
[Original work and AI disclosure](../NEW_WORK.md).

Before submission, the authorized operator must:

- Inspect the actual form, track options, eligibility, deadline/timezone, required
  fields and video/local-setup requirements. Do not infer live fields from this draft.
- Choose the intended release commit and include the reviewed, sanitized follow-up
  artifacts. Run publication/history checks and confirm release CI on that commit.
- Explicitly authorize any public release, then verify repository/setup links
  while logged out. The repository was private at audit time.
- Review/upload the intended video and verify its actual public URL; do not reuse
  the older failed `docs/demo/demo.mp4` as the successful demo.
- Submit only with explicit authorization and retain the real confirmation/receipt.

No hosted deployment, public-access verification, completed submission or prize
result is claimed.
