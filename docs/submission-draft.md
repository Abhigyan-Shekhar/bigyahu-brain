# Company Brain — submission draft

Prepared for the actual submission panel. Do not submit until its fields and
limits are checked, the repository is public, and the fresh demo video is ready.
The form itself has not been inspected because browser origin access is blocked.
The answer blocks below are prepared copy, not a claim that these field names or
length limits exist in the live form. Adapt only after inspecting that form.

## Project

**Name:** Company Brain

**One-line description:** A FalkorDB context layer connecting repository code,
engineering history, documentation and human-reviewed constraints for Codex.

**Primary track:** Company Brain. Also enter Agents That Act on Connected Data
if the actual form permits multiple tracks, as the published rules state.

**Repository:** https://github.com/Abhigyan-Shekhar/bigyahu-brain

Public visibility and logged-out access are release gates, not yet verified.

## Problem and working implementation

Coding agents can inspect current code while missing the engineering reasons
behind it. Company Brain lets an agent retrieve connected evidence before a
change: callers, historical work items, documentation, ownership and scoped,
source-backed constraints. Returned source prose stays untrusted, and missing
static edges are reported as uncertainty.

FalkorDB is the working context layer. Python AST and Git ingestion record
revision-bound code, imports, conservative callers and provenance. Filtered
public GitHub snapshots and bounded repository RST/Markdown sections share the
organization graph. Exact changelog PR numbers bridge docs to historical PR →
file → symbol paths. Five MCP tools expose bounded, parameterized graph queries.
`remember` proposes a decision; a separate human operator must review and approve
it before `check_change` treats it as an applicable constraint. Supersession
retains history while replacing the active rule.

The agent investigates, edits and tests code; Company Brain supplies graph
evidence. The fresh approved-v5 comparison completed three sessions per condition;
both baseline and graph passed all 12 independent socket cases in every run and
their selected upstream suites. Graph-2/3 received the approved rule before edits.
No accuracy lift was observed. At three sessions per arm, differences remain
anecdotal. The [full comparison](v5-evaluation.md) includes all outcomes and
incomplete retrieval. The older 12/12 demonstration predates v5 docs/approval.

## Copy-ready technical and disclosure answers

**How FalkorDB is used:**

Company Brain stores repository code, Git history, public issue/PR snapshots,
repository document sections and human-reviewed decisions in one organization
graph. Parameterized Cypher follows exact document references to PRs, changed
files, declared symbols, conservative callers and provenance Sources. MCP exposes
bounded context, impact, ownership and decision queries to Codex. Document
references are evidence; only separately approved applicable decisions become
`must_preserve` constraints. A private graph remains outside the public demo.

**What we built:**

The Python FalkorDB adapter, deterministic ingestion, graph services, MCP tools,
operator lifecycle, coding runner, independent evaluator and tests were written
in this repository, with work beginning on 15 October 2026. The v5 additions
include bounded RST/Markdown ingestion, exact changelog PR and qualified symbol
links, eligible urllib3 snapshots, graph reconstruction, real operator
approval/supersession and a frozen six-session evaluation. Graphify, GraphRAG SDK,
semantic document extraction, team federation and a hosted application are not
part of this implementation.

**Technology and dependencies:**

Python, FalkorDB/FalkorDBLite, the FalkorDB Python client, FastMCP, Python AST,
Git, PyYAML and pathspec; pytest and Ruff for verification. OpenAI Codex is the
coding agent harness. The local runtime verified here uses FalkorDBLite 0.10.0
with Redis 8.6.2 and graph module 4.18.3. A separate reconstructed Browser demo
has recorded Lite traversal and human-approved supersession; a macOS-hosted
Docker 4.14.7 rebuild and limited Browser smoke check are also documented in the
[Browser runbook](browser-demo/README.md). These do not visually verify the frozen
v5 graph. Cross-platform offline and Ubuntu Docker database CI passed on the
Browser branch; final combined-commit validation is recorded separately.

**AI assistance and external sources:**

Implemented with OpenAI Codex. Waggle is used for development conversation memory;
no Waggle implementation is copied into Company Brain. The demonstration uses
attributed public urllib3 code and filtered historical snapshots, with upstream
license/provenance retained. The proposed and approved rules are our demo
operator's interpretation of real upstream evidence, not policies authorized by
urllib3 maintainers. See [original work and AI disclosure](../NEW_WORK.md).

**Measured outcome and limitations:**

Both baseline and graph passed 12/12 independent socket cases in all three fresh
sessions per condition and passed their selected upstream suites. No correctness
advantage was observed; n=3 per condition is anecdotal. Graph-2 and graph-3
received the active approved constraint before editing; graph-1 did not. All
12 Company Brain responses were incomplete or unknown. No coding session
received a repository document-section excerpt; that path was independently
verified afterward through the real driver and STDIO server. The locked
clean-room backend suite passed 134 tests with real graph/Lite lifecycle checks.

## Setup, queries and evidence

- [README and graph model](../README.md)
- [Complete local graph reconstruction](v5-reproduction.md), using included
  eligible public snapshots and a pinned urllib3 checkout
- [FalkorDB traversal queries](v5-reproduction.md#verified-graph-paths)
- [Fixed paired evaluation protocol](v5-evaluation-protocol.md)
- [Fresh 3+3 results and exact patches](v5-evaluation.md)
- [Real human approval/supersession evidence](v5-lifecycle-evidence.json)
- [Earlier-graph demonstration and limitations](agent-demo-results.md)
- [Original event work and AI-assistance disclosure](../NEW_WORK.md)

**Deployment:** local STDIO MCP server plus FalkorDBLite. Complete local setup
is the submission path; do not invent a hosted product URL. Docker setup remains
available but has not been live-verified on this machine.

**Demo video URL:** `[PENDING: fresh reviewed video, accessible without login]`.
The recording must use the approved, frozen v5 graph. Do not
use the checked-in older failed `docs/demo/demo.mp4` as the successful final demo.

## Operator checks in the actual form

- [ ] Inspect the live submission panel and record its exact required fields,
  character limits, deadline/timezone and edit-after-submit policy.
- [ ] Confirm video host, duration and visibility requirements; replace the
  pending URL only after the new video has been reviewed and opens without login.
- [ ] Confirm whether a deployment field accepts complete local setup. If so,
  use the public [reconstruction guide](https://github.com/Abhigyan-Shekhar/bigyahu-brain/blob/codex/v5-execution/docs/v5-reproduction.md).
  If the form requires a hosted deployment, resolve that requirement explicitly;
  no hosted URL is currently available.
- [ ] Confirm track selection, team/account details, eligibility and required
  declarations with the human operator. Membership and eligibility are unverified.
- [ ] Record the final release branch/commit. Replace branch-specific links if
  integration changes their destination, and verify every evidence link there.
- [ ] On Saturday 17 October, run the publication/history scan on that release
  commit and manually review source, snapshots and video. Then make the repo
  public and verify repository/setup/video access in a logged-out window.
- [ ] Submit by early evening Sunday 18 October IST, ahead of the plan's
  11:59 PM IST deadline, after confirming the live form's deadline. Save the
  actual submission confirmation or receipt; a prepared draft is not submission.

Do not infer these form requirements from the published rules alone. Public
visibility, visualization of the original v5 paths, the final video, live-form
inspection and submission confirmation are still outstanding.

Published requirements checked on 16 October 2026:
[official event rules](https://www.wemakedevs.org/hackathons/falkordb/rules).
Public source, README/setup/data model, Cypher, working video, deployment or
complete local setup, track selection and AI-assistance disclosure are required.
