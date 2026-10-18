# Node highlights and deadline tabs

Click a company graph node to see its activity highlights above source details:

- Last modified by and last worked on use the latest commit attached to the current file, or the containing file for a symbol. This is file history within the bounded Git index, not proof of symbol-level edits or uncommitted work.
- GitHub event timestamps are separate from collection timestamps. The original author is indexed; an update timestamp does not establish who edited the issue or PR.
- Linked issues, PRs and source-backed decision records are reachable through current repository relationships. Proposal, approval and supersession states stay explicit. Comments and merged PRs never become approved decisions automatically.
- Live working shows running app actions whose planned file scope includes this node's file. It does not imply the agent is editing that file at this instant or that a person is online. The inspector polls every ten seconds and clears displayed activity if refresh fails. External editor presence is not integrated.

The **Deadlines** navigation tab offers All, Upcoming, Overdue and No deadline filters, timestamped linked decisions and source inspection. Closed/merged work remains in All and is excluded from upcoming/overdue. Dates use the browser timezone; full UTC timestamps are available on hover. GitHub milestone due dates provide deadlines. Free-text dates and arbitrary decisions in discussion are not inferred.

Initial onboarding and incremental GitHub collection preserve work authors, creation/update/closure timestamps, milestone due dates and comment/review timestamps in the snapshot and native FalkorDB properties. Existing full-text decision indexes remain in use; timeline navigation follows explicit Source links. No separate deadline database is introduced. A new GitHub acquisition is needed for old snapshots missing these fields. Refresh reads the existing index; it does not contact GitHub.

Repository authorization and readiness checks apply to `/api/repositories/{project}/deadlines` and node inspection. Lists are bounded to 200 work items and 500 decision/source links with truncation disclosed. Node work links use up to three hops across declaration, work, reference and source relations, restricted to current nodes in the same repository. The latest commit is selected from up to two declaration/modification hops. Missing values remain unknown.

Validation: disposable FalkorDB integration checks cover code-to-work navigation, decision timestamps/status and cross-repository decision exclusion. Unit checks cover live run scope, completed/queued runs, metadata refresh and deadline classification. Frontend build and component rendering are checked separately.

## Live work and visual hierarchy

The workspace now polls the authenticated `/api/repositories/{project}/activity` lifecycle snapshot every three seconds. It reports queued/running repository indexing, investigations, fix actions, semantic ingestion, documentation drafts/patches and workflows. Snapshots include only display metadata, are scoped through repository/session parent records, and disclose a 50-task limit. Awaiting approval is not active work. Failed requests stop the animated dots and label retained task information as the last received state.

A modeless tinted frosted-glass popup opens for a new set of active task IDs. Close or Escape minimizes it without cancelling jobs. A saturated red banner remains and reopens the popup. Stage changes do not reopen a minimized popup; a different set of tasks can open it again. Task text uses monospace typography and live panels have a purple background. Reduced-motion preferences disable the new animation and flatten the deadline depth effect.

Problems use red across severity levels with text labels preserved. The inline code-location flow shows repository, folders, file and reported line, plus expandable cited excerpts. This depicts containment, not a runtime call chain.

Fix-plan approval in Agent Runs and workflow artifacts uses a raised yellow review card and a native modal with solid green approval and red rejection buttons. The modal previews scoped files and exact test commands; request changes is available for Agent Runs. The existing digest-bound approval/rejection API remains authoritative. Pending or failed requests do not count as approval.

Deadline presentation offers a decision list and an interactive timeline. Timeline positions use actual milestone due timestamps. Zoom, 2D/3D depth, angle, native scrolling, vertical resize and reset adjust the view only; they do not change GitHub deadlines. Selecting a dated/undated item opens its timestamped decision trail inline.

Visual QA used explicitly synthetic fixtures at narrow mobile and 1280px desktop layouts. Checked minimize/reopen, stopping activity, keyboard zoom/angle/reset, selected decision history, and the approval dialog/rejection callback. Screenshots are local ignored artifacts under `data/validation/live-ui/`. No real task execution, GitHub mutation or plan approval was performed for these browser checks. Shiro re-review: activity, problems and authorization have distinct hierarchies; controls retain text labels, stable positions and keyboard access. Ready for local use; the existing large main-bundle build warning remains.
