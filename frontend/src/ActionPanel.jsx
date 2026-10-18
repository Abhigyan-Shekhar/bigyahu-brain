import React, { useEffect, useRef, useState } from "react";
import {
  Check,
  LoaderCircle,
  Play,
  FileText,
  X,
  Download,
  GitBranch,
} from "lucide-react";
import { createPortal } from "react-dom";
import { api, send } from "./api";
import { elapsedLabel, testSummary } from "./actionPresentation";

function contributionLabel(support) {
  if (support.kind === "code")
    return /\.(md|rst|txt)(:|$)/i.test(support.title)
      ? "Repository document"
      : "Current code";
  if (support.kind === "team_memory" || support.brain?.startsWith("team:"))
    return "Reviewed Team Brain evidence";
  if (support.kind === "memory" || support.brain?.startsWith("private:"))
    return "Reviewed Personal Brain evidence";
  if (support.kind === "history_diff") return "Historical patch";
  if (
    ["repository_document", "app_upload", "app_binary_upload"].includes(
      support.source_kind,
    )
  )
    return "Engineering document";
  if (support.source_kind === "graphify_structural")
    return "Extracted code evidence";
  return "Source evidence";
}

function download(action) {
  const url = URL.createObjectURL(
    new Blob([action.patch], { type: "text/plain;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `company-brain-${action.id}.patch`;
  a.click();
  URL.revokeObjectURL(url);
}
export default function ActionPanel({
  turn,
  project,
  onEvidence,
  onReviewMemory,
}) {
  const [focused, setFocused] = useState(false);
  const dialog = useRef(null);
  const focusButton = useRef(null);
  const wasFocused = useRef(false);
  useEffect(() => {
    if (focused) dialog.current?.showModal();
    else if (wasFocused.current) focusButton.current?.focus();
    wasFocused.current = focused;
  }, [focused]);
  const [action, setAction] = useState(null),
    [form, setForm] = useState(false),
    [objective, setObjective] = useState(turn.question),
    [error, setError] = useState(""),
    [submitting, setSubmitting] = useState(false),
    [lessonNotice, setLessonNotice] = useState("");
  useEffect(() => {
    let active = true;
    api(`/turns/${turn.id}/actions`)
      .then((list) => {
        if (list.length) return api(`/actions/${list.at(-1).id}`);
      })
      .then((a) => {
        if (active && a) {
          setAction(a);
          setObjective(a.objective || turn.question);
        }
      })
      .catch((e) => setError(e.message));
    return () => {
      active = false;
    };
  }, [turn.id]);
  useEffect(() => {
    if (
      !action ||
      !["queued", "running", "awaiting_approval"].includes(action.status)
    )
      return;
    let active = true;
    const timer = setInterval(
      () =>
        api(`/actions/${action.id}`)
          .then((a) => {
            if (active) setAction(a);
          })
          .catch((e) => setError(e.message)),
      1500,
    );
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [action?.id, action?.status]);
  async function propose(e) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      setAction(
        await send(`/turns/${turn.id}/actions`, { question: objective }),
      );
      setForm(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }
  async function decide(choice) {
    setSubmitting(true);
    setError("");
    try {
      setAction(
        await send(
          `/actions/${action.id}/${choice}`,
          choice === "approve" ? { plan_digest: action.plan_digest } : {},
        ),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }
  const busy =
    action &&
    ["queued", "running", "awaiting_approval"].includes(action.status);
  const baselineErrors = action?.baseline_tests?.some((t) =>
    /errors=[1-9]\d*|\b[1-9]\d* errors?\b/.test(t.output || ""),
  );
  const summaryClaims = [
    ...new Set(
      [
        action?.claims?.[0],
        action?.claims?.find((c) =>
          c.support.some(
            (s) => s.kind === "memory" || s.brain?.startsWith("private:"),
          ),
        ),
        action?.claims?.find((c) =>
          c.support.some(
            (s) => s.kind === "team_memory" || s.brain?.startsWith("team:"),
          ),
        ),
        ...(action?.claims || []),
      ].filter(Boolean),
    ),
  ].slice(0, 3);
  const stages = ["Investigate", "Plan", "Approve", "Edit", "Verify"];
  const stageIndex = !action
    ? 0
    : action.status === "complete" ||
        /^(Running approved tests|Testing |Checking exported patch)/.test(
          action.stage || "",
        )
      ? 4
      : action.phase === "execution"
        ? 3
        : action.status === "awaiting_approval"
          ? 2
          : 1;
  const panel = (
    <section
      className="action-panel"
      id={`fix-${turn.id}`}
      aria-label="Plan and execution"
    >
      <div className="action-heading">
        <GitBranch size={14} />
        <strong>From investigation to a fix</strong>
        <button ref={focusButton} onClick={() => setFocused(!focused)}>
          {focused ? "Close focused review" : "Open focused review"}
        </button>
        {action?.patch && (
          <button onClick={() => download(action)}>
            <Download size={13} /> Download final patch
          </button>
        )}
        {!busy && !form && (
          <button
            onClick={() => {
              setObjective(action?.objective || objective);
              setForm(true);
            }}
          >
            {action?.status === "failed"
              ? "Review objective and retry"
              : action
                ? "Plan another change"
                : "Plan a change"}
          </button>
        )}
      </div>
      <ol className="workflow-stages" aria-label="Fix workflow stages">
        {stages.map((label, i) => (
          <li key={label} aria-current={i === stageIndex ? "step" : undefined}>
            {label}
          </li>
        ))}
      </ol>
      {error && (
        <p className="failure" role="alert">
          {error}
        </p>
      )}
      {form && (
        <form className="plan-form" onSubmit={propose}>
          <label htmlFor={`objective-${turn.id}`}>
            What should the fix accomplish?
          </label>
          {action?.status === "failed" && (
            <p>
              Correct the issue described above in this objective before
              retrying. A retry creates a new read-only plan and requires fresh
              approval before any editing.
            </p>
          )}
          <textarea
            id={`objective-${turn.id}`}
            rows={3}
            required
            maxLength={8000}
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
          />
          <p>
            Planning is read-only. You will review the files, evidence, and test
            commands before approving execution.
          </p>
          <div>
            <button type="button" onClick={() => setForm(false)}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={submitting || !objective.trim()}
            >
              Prepare cited plan
            </button>
          </div>
        </form>
      )}
      {action && (
        <>
          <div className="action-state agent-step" role="status">
            {["queued", "running"].includes(action.status) ? (
              <LoaderCircle className="spin" size={14} />
            ) : action.status === "complete" &&
              action.regression_demonstrated ? (
              <Check size={14} />
            ) : null}
            <div>
              <small>
                {action.phase === "execution" ? "EXECUTION" : "FIX WORKFLOW"}
              </small>
              <strong>{action.stage}</strong>
            </div>
          </div>
          {action.error && (
            <div className="failure" role="alert">
              <strong>
                {action.phase === "execution"
                  ? "Execution stopped"
                  : "Plan could not be prepared"}
              </strong>
              <p>
                {action.error ===
                "This milestone edits bounded Python, documentation and TOML files"
                  ? "The model returned a path outside the supported file scope. Use literal Python, documentation or TOML filenames without annotations such as '(new)'. No execution was approved. Review the objective and retry."
                  : action.error}
              </p>
            </div>
          )}
          {action.progress && (
            <div className="action-progress">
              <span>
                {elapsedLabel(action.progress.elapsed_seconds)} ·{" "}
                {action.progress.completed_count} completed tool actions
              </span>
              {action.progress.current_tool && (
                <span>Current tool: {action.progress.current_tool}</span>
              )}
              <details>
                <summary>
                  Tool activity{" "}
                  {action.progress.trace_bounded ? "(bounded trace)" : ""}
                </summary>
                {action.progress.completed_tools.length ? (
                  <ol>
                    {action.progress.completed_tools.map((item, i) => (
                      <li key={i}>
                        {item.tool} · {item.status}
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p>No completed tool actions recorded yet.</p>
                )}
                <small>
                  Tool names and completion events only. Evidence review and
                  test stages are reported above; no progress percentage is
                  estimated.
                </small>
              </details>
            </div>
          )}
          {action.status === "complete" && (
            <div className="action-outcome">
              <div
                className="test-comparison"
                aria-label="Before and after test results"
              >
                {[
                  ["Original + proposed tests", action.baseline_tests],
                  ["Patched code", action.tests],
                ].map(([label, results]) => (
                  <div key={label}>
                    <strong>{label}</strong>
                    {results?.length ? (
                      results.map((t, i) => {
                        const summary = testSummary(t);
                        return (
                          <div key={i} className="test-count-summary">
                            <p
                              className={
                                t.passed && t.tests_reported > 0
                                  ? "test-pass"
                                  : "failure"
                              }
                            >
                              {t.passed && t.tests_reported > 0
                                ? "Command passed"
                                : t.outcome === "exited" && t.exit_code !== 0
                                  ? "Command failed"
                                  : "Unverified"}{" "}
                              · exit {t.exit_code ?? "unknown"}
                            </p>
                            <p>
                              {summary.count ?? "Unknown"} {summary.unit}
                            </p>
                            {(summary.failures !== null ||
                              summary.errors !== null) && (
                              <p>
                                {summary.failures ?? "Unknown"} assertion
                                failures
                                {summary.errors !== null
                                  ? ` · ${summary.errors} runner errors`
                                  : ""}
                              </p>
                            )}
                            {summary.subtests > 0 && (
                              <p>
                                {summary.detailsComplete
                                  ? summary.subtests
                                  : `At least ${summary.subtests}`}{" "}
                                subtest failures
                                {summary.detailsComplete
                                  ? ` · ${summary.failures - summary.subtests} method/case failures`
                                  : " visible in retained log; failure details may be truncated"}
                              </p>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <p>No test results recorded</p>
                    )}
                  </div>
                ))}
              </div>
              <p className="action-note">
                Verification:{" "}
                {action.regression_demonstrated
                  ? "matched baseline failures resolved in approved tests; independent bug confirmation still requires review."
                  : "fix remains unverified; inspect the test report below."}
              </p>
            </div>
          )}
          {action.plan && (
            <div className="action-brief">
              <strong>{action.plan.summary}</strong>
              <p>
                {action.plan.files.length} permitted files ·{" "}
                {action.claims?.length || 0} evidence contributions
              </p>
              <h4>Why this fix?</h4>
              {summaryClaims.map((claim, i) => (
                <p className="contribution-brief" key={i}>
                  <strong>
                    {[...new Set(claim.support.map(contributionLabel))].join(
                      " · ",
                    )}
                  </strong>
                  : {claim.influence || claim.text}
                </p>
              ))}
              {action.claims?.length > summaryClaims.length && (
                <small>
                  {action.claims.length - summaryClaims.length} more
                  contributions in the full plan below.
                </small>
              )}
              <p className="action-note">
                Reviewed memories are advisory evidence. Inspect the full plan
                and sources before approval.
              </p>
            </div>
          )}
          {action.plan && (
            <details
              className="plan-detail"
              open={action.status === "awaiting_approval"}
            >
              <summary>Fix plan · Why this fix?</summary>
              <p>{action.plan.summary}</p>
              <p className="action-note">
                {action.relevance_review?.kind === "fallible_model_plan_review"
                  ? "Source provenance checked. Claims, rationale and proposed action reviewed by a fallible model; review the evidence before approving."
                  : "Historical plan: no claim-and-action relevance review was recorded. Prepare a new plan before approving another execution."}
              </p>
              <ol>
                {action.plan.steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ol>
              <h4>Files permitted to change</h4>
              <ul>
                {action.plan.files.map((p) => (
                  <li key={p}>
                    <code>{p}</code>
                  </li>
                ))}
              </ul>
              <h4>
                {action.status === "awaiting_approval"
                  ? "Test commands for approval"
                  : "Approved test commands"}
              </h4>
              {action.plan.commands.map((argv, i) => (
                <pre key={i}>{argv.join(" ")}</pre>
              ))}
              <p className="action-note">
                Tests run against the original code with proposed regression
                tests, then the patched code. Network is disabled. No
                dependencies are installed. Each command is capped at 120
                seconds and 512 KB of output.
              </p>
              {action.claims?.map((c, i) => (
                <div className="plan-evidence" key={i}>
                  <h4>
                    {[...new Set(c.support.map(contributionLabel))].join(" · ")}
                  </h4>
                  <p>{c.text}</p>
                  {c.influence && (
                    <p className="plan-influence">
                      <strong>How this informs the plan:</strong> {c.influence}
                    </p>
                  )}
                  <div className="citations">
                    {[
                      ...new Map(
                        c.support.map((s) => [s.evidence_id, s]),
                      ).values(),
                    ].map((s) => (
                      <button
                        key={s.evidence_id}
                        onClick={() => {
                          setFocused(false);
                          onEvidence(action.id, s.evidence_id);
                        }}
                      >
                        <FileText size={12} />
                        {s.title.split("/").slice(-2).join("/")}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </details>
          )}
          {action.status === "awaiting_approval" && (
            <div className="approval-controls">
              <p>
                Approval authorizes only this plan’s files and test commands in
                a separate checkout. Your indexed source stays unchanged.
              </p>
              <div>
                <button disabled={submitting} onClick={() => decide("reject")}>
                  <X size={14} /> Reject plan
                </button>
                <button
                  className="primary"
                  disabled={submitting}
                  onClick={() => decide("approve")}
                >
                  <Play size={14} /> Approve isolated execution
                </button>
              </div>
            </div>
          )}
          {action.status === "complete" && (
            <div className="execution-report">
              <details>
                <summary>Implementation handoff before test validation</summary>
                <p>{action.summary}</p>
              </details>
              <strong
                className={
                  action.regression_demonstrated
                    ? "test-pass"
                    : action.tests_passed
                      ? "test-qualified"
                      : "failure"
                }
              >
                {action.tests_passed
                  ? action.regression_demonstrated
                    ? "Test regression signal · matched baseline failures resolved"
                    : baselineErrors
                      ? "Tests passed · baseline errors need review"
                      : "Tests passed · fix remains unverified"
                  : "Tests did not pass — inspect the report"}
              </strong>
              <p className="action-note">
                {action.regression_demonstrated
                  ? "The same approved test command failed on the original and passed on the patch. Review its coverage; this signal does not independently prove the reported bug is fixed."
                  : baselineErrors
                    ? "The original run reported test errors. Automatic verification excludes these because they may indicate setup problems. Inspect the trace and verify the reproduction independently; a coding lesson cannot be proposed from this report."
                    : "No matched baseline regression has been demonstrated. Passing tests alone do not verify the fix; a coding lesson cannot be proposed from this report."}
              </p>
              <p className="action-note">
                {action.patch_replay?.status === "applies_to_base"
                  ? `Patch replay: applied to base ${action.patch_replay.revision.slice(0, 8)} with exact edited-file bytes. This did not rerun tests.`
                  : "Independent follow-up verification is not recorded in this action. Separate replay or follow-up results do not replace its original automated classification."}
              </p>
              <p className="action-note">
                Original checkout unchanged. This patch has not been applied,
                committed, or pushed.
              </p>
              {action.baseline_tests && (
                <details>
                  <summary>Original code with proposed tests</summary>
                  <p>
                    {action.baseline_includes_proposed_tests
                      ? "Regression test changes were copied onto the original code."
                      : "No proposed test-file changes were detected."}
                  </p>
                  {action.baseline_tests.map((t, i) => (
                    <div key={i}>
                      <code>{t.argv.join(" ")}</code>
                      <p>
                        Exit {t.exit_code} · {t.tests_reported} runner-reported
                        cases · {t.outcome}
                      </p>
                      <pre>{t.output}</pre>
                    </div>
                  ))}
                </details>
              )}
              <details>
                <summary>Patched code test results</summary>
                {action.tests.map((t, i) => (
                  <div key={i}>
                    <code>{t.argv.join(" ")}</code>
                    <p>
                      Exit {t.exit_code} · {t.tests_reported} runner-reported
                      cases · {t.outcome}
                    </p>
                    <pre>{t.output}</pre>
                  </div>
                ))}
              </details>
              <details>
                <summary>
                  Final diff{" "}
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      download(action);
                    }}
                  >
                    <Download size={13} /> Download patch
                  </button>
                </summary>
                <pre className="patch">{action.patch}</pre>
              </details>
              {action.lesson_proposal?.text && (
                <details>
                  <summary>Draft lesson for later review</summary>
                  <p>{action.lesson_proposal.text}</p>
                  <small>
                    This is the model’s draft. Personal Brain tracks its
                    separate proposal and review status.
                  </small>
                  <div className="lesson-controls">
                    <button
                      disabled={submitting || !action.regression_demonstrated}
                      onClick={async () => {
                        setSubmitting(true);
                        setError("");
                        try {
                          const r = await send(
                            `/repositories/${project}/actions/${action.id}/lesson`,
                            {},
                          );
                          setLessonNotice(
                            `Private memory ${r.state}. Open Personal Brain to inspect its source and review.`,
                          );
                        } catch (e) {
                          setError(e.message);
                        } finally {
                          setSubmitting(false);
                        }
                      }}
                    >
                      Send to Personal Brain review
                    </button>
                    <button onClick={onReviewMemory}>
                      Open Personal Brain
                    </button>
                  </div>
                  {lessonNotice && <p role="status">{lessonNotice}</p>}
                </details>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
  return focused
    ? createPortal(
        <dialog
          className="action-focus"
          ref={dialog}
          aria-label="Focused plan and execution review"
          onCancel={() => setFocused(false)}
        >
          {panel}
        </dialog>,
        document.body,
      )
    : panel;
}
