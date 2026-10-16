# Company Brain — submission draft

Prepared for the actual submission panel. Do not submit until its fields and
limits are checked, the repository is public, and the fresh demo video is ready.
The form itself has not been inspected because browser origin access is blocked.

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

**Demo video:** pending a new recording on the approved, frozen v5 graph. Do not
use the checked-in older failed `docs/demo/demo.mp4` as the successful final demo.

## Operator checks in the actual form

Check required fields, character limits, repository link format, video URL host
and duration requirements, whether the deployment field allows local setup,
track selection, team/account state and any final declarations. Confirm links
without login before final submission. Do not infer these form requirements
from the published rules alone.

Published requirements checked on 16 October 2026:
[official event rules](https://www.wemakedevs.org/hackathons/falkordb/rules).
Public source, README/setup/data model, Cypher, working video, deployment or
complete local setup, track selection and AI-assistance disclosure are required.
