# Shiro UI review and targeted improvements

Mode: fix. Evidence: running local app, synthetic investigation and reviewed fix
plan, source inspection, and browser interaction at an 855 × 756 viewport.

## Findings addressed

- **P1 — Reading space was squeezed.** At the observed width, the persistent
  context panel left a narrow column for findings. Below 1100 px, chat now uses
  its full reading width and exposes Sources & context on demand. Citation
  inspection uses the same drawer. Opening focuses it; Escape closes it and
  restores focus to the context control.
- **P1 — Results competed with repeated content.** Investigation details repeated
  the vulnerability descriptions below their alert cards; the original question
  and full completed activity also preceded the findings. Alerts now own those
  descriptions, the question and completed trace are disclosures, and ordinary
  context stays separate from vulnerability findings.
- **P1 — The next action was repeated and indirect.** Each finding exposed the
  same fix-workflow action. One primary action now sits with the results summary
  and directly opens an existing plan. Source links remain on each finding.
- **P2 — Alerts lacked a clear visual hierarchy.** Added concise severity badges,
  a consistent location row, readable impact text, a distinct recommendation
  block, and source controls. Severity filters expose pressed state and counts.
  Color reinforces the severity text; it does not replace it.
- **P2 — Plan review repeated its rationale.** Recorded activity and evidence
  rationale now start closed. Proposed changes, permitted files and exact test
  commands remain directly available. Supporting evidence and retention details
  remain accessible through a disclosure. Text contrast and sizes are improved.

## Keep

The restrained green palette, explicit approval stages, original source text,
and visible caveat about model-assessed severity serve the task. These remain.

## Changed implementation

- `frontend/src/FindingAlerts.jsx`: result summary, one primary action, severity
  filters, structured finding details and distinct evidence controls.
- `frontend/src/InvestigationRun.jsx`: concise result header, question/trace
  disclosure, removal of duplicate findings.
- `frontend/src/AgentRuns.jsx`: direct navigation from results to plan review.
- `frontend/src/main.jsx`: context drawer, keyboard focus and Escape handling,
  reduced duplicate summaries and clearer additional-context labeling.
- `frontend/src/ActionPanel.jsx`: focused plan disclosure and readable scope,
  commands, supporting evidence and approval information.
- `frontend/src/style.css`: targeted styles and narrower-viewport behavior.

## Verification and re-review

Frontend tests and production build pass. In the live browser, verified the high
severity filter hides the medium finding, citations show original indexed source,
Sources & context opens and receives keyboard focus, Escape closes it and restores
focus, and the primary results action opens the existing plan awaiting approval.
No execution was approved during the UI review.

Re-review: the observed result and plan screens are ready to ship. The findings,
impact, proposed fix, evidence and next step are now distinct. No remaining P0 or
P1 issue was observed in these tested flows. A separate phone/tablet viewport and
hover interactions were not exercised; responsive and hover rules were inspected
in code. This is not a full accessibility or whole-application audit.
