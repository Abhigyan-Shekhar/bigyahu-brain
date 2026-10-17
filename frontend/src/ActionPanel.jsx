import React, { useEffect, useState } from "react";
import {
  Check,
  LoaderCircle,
  Play,
  FileText,
  X,
  Download,
  GitBranch,
} from "lucide-react";
import { api, send } from "./api";

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
export default function ActionPanel({ turn, project, onEvidence, onReviewMemory }) {
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
        if (active && a) setAction(a);
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
  return (
    <section className="action-panel" aria-label="Plan and execution">
      <div className="action-heading">
        <GitBranch size={14} />
        <strong>From investigation to a fix</strong>
        {!busy && !form && (
          <button onClick={() => setForm(true)}>
            {action ? "Plan another change" : "Plan a change"}
          </button>
        )}
      </div>
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
          <div className="action-state">
            {["queued", "running"].includes(action.status) ? (
              <LoaderCircle className="spin" size={14} />
            ) : action.status === "complete" ? (
              <Check size={14} />
            ) : null}
            <span>{action.stage}</span>
          </div>
          {action.error && <p className="failure">{action.error}</p>}
          {action.plan && (
            <details
              className="plan-detail"
              open={action.status === "awaiting_approval"}
            >
              <summary>Fix plan & supporting evidence</summary>
              <p>{action.plan.summary}</p>
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
              <h4>Approved test commands</h4>
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
                  <p>{c.text}</p>
                  <div className="citations">
                    {[
                      ...new Map(
                        c.support.map((s) => [s.evidence_id, s]),
                      ).values(),
                    ].map((s) => (
                      <button
                        key={s.evidence_id}
                        onClick={() => onEvidence(action.id, s.evidence_id)}
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
              <strong className={action.tests_passed ? "test-pass" : "failure"}>
                {action.tests_passed
                  ? "Approved tests passed"
                  : "Tests did not pass — inspect the report"}
              </strong>
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
              <details open>
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
                    This is the model’s draft. Personal Brain tracks its separate proposal and review status.
                  </small>
                  <div className="lesson-controls"><button disabled={submitting || !action.tests_passed} onClick={async () => {
                    setSubmitting(true);setError("");
                    try {const r = await send(`/repositories/${project}/actions/${action.id}/lesson`,{});setLessonNotice(`Private memory ${r.state}. Open Personal Brain to inspect its source and review.`);} catch(e){setError(e.message);} finally {setSubmitting(false);}
                  }}>Send to Personal Brain review</button><button onClick={onReviewMemory}>Open Personal Brain</button></div>
                  {lessonNotice && <p role="status">{lessonNotice}</p>}
                </details>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
}
