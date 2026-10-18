import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Workflow, X } from "lucide-react";
import { api, send, watchResource } from "./api";
import DocumentationPanel, { downloadText } from "./DocumentationPanel";
import ApprovalDecision from "./ApprovalDecision";

function ArtifactReview({ project, workflow, artifact }) {
  const [value, setValue] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const route = `/repositories/${project}/workflows/${workflow}/artifacts/${artifact.id}`;
  async function load() {
    setValue(await api(route));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [artifact.id]);
  useEffect(() => {
    if (!value || !["queued", "running", "send_queued"].includes(value.status))
      return;
    const timer = setInterval(
      () => load().catch((e) => setError(e.message)),
      2000,
    );
    return () => clearInterval(timer);
  }, [value?.status, artifact.id]);
  async function perform(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  if (artifact.kind === "document")
    return (
      <DocumentationPanel
        project={project}
        documentId={artifact.id}
        label="Review document draft"
      />
    );
  if (!value) return <p>{error || "Loading prepared action…"}</p>;
  return (
    <div className="workflow-artifact">
      <h4>
        {artifact.kind} · {value.status}
      </h4>
      {error && <p className="failure">{error}</p>}
      {value.error && <p className="failure">{value.error}</p>}
      {artifact.kind === "github" && (
        <>
          <p>
            Publish as {value.login} to {value.repository} · {value.operation}
          </p>
          <h4>{value.payload.title}</h4>
          <pre>{value.payload.body}</pre>
          {value.payload.head && (
            <p>
              {value.payload.head} → {value.payload.base}
            </p>
          )}
          {value.status === "draft" && (
            <button
              disabled={busy}
              onClick={() =>
                perform(() =>
                  send(
                    `/repositories/${project}/github/actions/${value.id}/publish`,
                    { consent_digest: value.consent_digest },
                  ),
                )
              }
            >
              Publish exact GitHub draft
            </button>
          )}
          {value.url && (
            <a href={value.url} target="_blank" rel="noreferrer">
              Open on GitHub
            </a>
          )}
        </>
      )}
      {artifact.kind === "email" && (
        <>
          <p>
            From: {value.sender || "Sender not configured"} · Recipient:{" "}
            {value.recipient}
          </p>
          <h4>{value.subject}</h4>
          <pre>{value.body}</pre>
          {value.status === "draft" && (
            <button
              disabled={busy}
              onClick={() =>
                perform(() =>
                  send(
                    `/repositories/${project}/workflows/${workflow}/emails/${value.id}/refresh-sender`,
                    { consent_digest: value.consent_digest },
                  ),
                )
              }
            >
              Refresh sender preview
            </button>
          )}
          {value.status === "draft" && (
            <button
              disabled={busy || !value.sender}
              onClick={() =>
                perform(() =>
                  send(
                    `/repositories/${project}/workflows/${workflow}/emails/${value.id}/send`,
                    { consent_digest: value.consent_digest },
                  ),
                )
              }
            >
              Approve & send this exact email
            </button>
          )}
          {value.email_result && (
            <>
              <p>{value.email_result.stage}</p>
              {value.email_result.error && (
                <p className="failure">{value.email_result.error}</p>
              )}
              <p>{value.email_result.notice}</p>
            </>
          )}
        </>
      )}
      {artifact.kind === "fix" && (
        <>
          <p>{value.stage}</p>
          {value.plan && (
            <>
              <h4>{value.plan.summary}</h4>
              <ol>
                {value.plan.steps.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
              <p>Approved file scope: {value.plan.files.join(", ")}</p>
              <pre>
                {value.plan.commands
                  ?.map((command) => command.join(" "))
                  .join("\n")}
              </pre>
            </>
          )}
          {value.status === "awaiting_approval" && <div className="approval-controls">
            <ApprovalDecision key={value.plan_digest} action={value} busy={busy} error={error}
              onApprove={() =>
                perform(() =>
                  send(`/actions/${value.id}/approve`, {
                    plan_digest: value.plan_digest,
                  }),
                )
              }
              onReject={() =>
                perform(() => send(`/actions/${value.id}/reject`, {}))
              }
            />
          </div>}
          {value.summary && <p>{value.summary}</p>}
          {value.patch && (
            <details>
              <summary>Isolated patch</summary>
              <pre>{value.patch}</pre>
              <button
                onClick={() =>
                  downloadText(value.patch, `workflow-${value.id}.patch`)
                }
              >
                Download patch
              </button>
            </details>
          )}
          {value.tests && (
            <details>
              <summary>Actual baseline and patched test results</summary>
              {[
                ["Baseline", value.baseline_tests],
                ["Patched", value.tests],
              ].map(([label, tests]) => (
                <div key={label}>
                  <strong>{label}</strong>
                  {tests?.map((test, i) => (
                    <pre key={i}>
                      {test.argv.join(" ")}
                      {"\n"}Exit {test.exit_code} · {test.outcome}
                      {"\n"}
                      {test.output}
                    </pre>
                  ))}
                </div>
              ))}
            </details>
          )}
          <p>
            Original repository checkout is unchanged. Publication is separate.
          </p>
        </>
      )}
    </div>
  );
}

const choices = [
  ["draft_document", "Documentation draft"],
  ["propose_fix", "Reviewed fix plan"],
  ["draft_github_issue", "GitHub issue draft"],
  ["draft_github_comment", "GitHub comment draft"],
  ["draft_github_pr", "GitHub draft PR description"],
  ["draft_email", "Email draft"],
];

export default function WorkflowPanel({ project, sourceTurn }) {
  const [open, setOpen] = useState(false),
    [optIn, setOptIn] = useState(false),
    [goal, setGoal] = useState("");
  const [capabilities, setCapabilities] = useState(["research"]),
    [targets, setTargets] = useState({
      recipient: "",
      issue_number: "",
      head: "",
      base: "",
    });
  const [items, setItems] = useState([]),
    [current, setCurrent] = useState(null),
    [evidence, setEvidence] = useState(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [clarification, setClarification] = useState("");
  const dialog = useRef(null),
    trigger = useRef(null);
  const route = `/repositories/${project}/workflows`;
  const running = ["queued", "running"].includes(current?.status);
  async function refresh() {
    setItems((await api(route)).items.slice().reverse());
  }
  useEffect(() => {
    if (!open) return;
    refresh().catch((e) => setError(e.message));
    dialog.current?.focus();
    function keys(e) {
      if (e.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
      if (e.key !== "Tab") return;
      const nodes = Array.from(
        dialog.current.querySelectorAll("button,input,textarea,select"),
      ).filter((n) => !n.matches(":disabled") && n.getClientRects().length);
      if (
        e.shiftKey &&
        [dialog.current, nodes[0]].includes(document.activeElement)
      ) {
        e.preventDefault();
        nodes.at(-1)?.focus();
      } else if (!e.shiftKey && document.activeElement === nodes.at(-1)) {
        e.preventDefault();
        nodes[0]?.focus();
      }
    }
    dialog.current?.addEventListener("keydown", keys);
    return () => dialog.current?.removeEventListener("keydown", keys);
  }, [open, project]);
  useEffect(() => {
    if (!open || !current || !running) return;
    return watchResource(
      `${route}/${current.id}/events`,
      `${route}/${current.id}`,
      setCurrent,
      (e) => setError(e.message),
    );
  }, [open, current?.id, running]);
  async function perform(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button ref={trigger} onClick={() => setOpen(true)}>
        <Workflow size={15} /> Auto-investigate
      </button>
      {open &&
        createPortal(
          <div className="modal-backdrop">
            <section
              className="modal authoring-panel"
              role="dialog"
              aria-modal="true"
              aria-label="Evidence-driven workflows"
              ref={dialog}
              tabIndex={-1}
            >
              <button
                className="modal-close"
                aria-label="Close workflows"
                onClick={() => {
                  setOpen(false);
                  trigger.current?.focus();
                }}
              >
                <X />
              </button>
              <h2>Evidence-driven workflows</h2>
              <p>
                Additional read-only research, capped at four steps, eight model
                calls, 60 retrieval calls and 15 minutes. Documents, code
                changes and messages have separate review controls.
              </p>
              {error && (
                <p className="failure" role="alert">
                  {error}
                </p>
              )}
              <div className="authoring-layout">
                <aside>
                  <h3>Agent workflows</h3>
                  <button onClick={() => setCurrent(null)}>New workflow</button>
                  {items.map((item) => (
                    <button
                      key={item.id}
                      onClick={() =>
                        api(`${route}/${item.id}`)
                          .then(setCurrent)
                          .catch((e) => setError(e.message))
                      }
                    >
                      {item.goal.slice(0, 65)} · {item.status}
                    </button>
                  ))}
                </aside>
                <div>
                  {!current && (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        perform(async () =>
                          setCurrent(
                            await send(route, {
                              goal,
                              auto_investigate: optIn,
                              capabilities,
                              source_turn_id: sourceTurn?.id || null,
                              ...targets,
                              recipient: targets.recipient || null,
                              issue_number: targets.issue_number
                                ? Number(targets.issue_number)
                                : null,
                            }),
                          ),
                        );
                      }}
                    >
                      <label>
                        Goal
                        <textarea
                          required
                          rows={4}
                          maxLength={8000}
                          value={goal}
                          onChange={(e) => setGoal(e.target.value)}
                          placeholder="Investigate the problem, inspect unanswered questions, and prepare the selected drafts."
                        />
                      </label>
                      <label className="workflow-optin">
                        <input
                          type="checkbox"
                          checked={optIn}
                          onChange={(e) => setOptIn(e.target.checked)}
                        />{" "}
                        Auto-investigate (up to 4 steps)
                      </label>
                      <fieldset>
                        <legend>
                          Allowed outcomes · research is always enabled
                        </legend>
                        {choices.map(([key, label]) => (
                          <label className="workflow-optin" key={key}>
                            <input
                              type="checkbox"
                              checked={capabilities.includes(key)}
                              onChange={(e) =>
                                setCapabilities(
                                  e.target.checked
                                    ? [...capabilities, key]
                                    : capabilities.filter(
                                        (item) => item !== key,
                                      ),
                                )
                              }
                            />
                            {label}
                          </label>
                        ))}
                      </fieldset>
                      {capabilities.includes("draft_email") && (
                        <label>
                          Email recipient (chosen by you)
                          <input
                            required
                            type="email"
                            value={targets.recipient}
                            onChange={(e) =>
                              setTargets({
                                ...targets,
                                recipient: e.target.value,
                              })
                            }
                          />
                        </label>
                      )}
                      {capabilities.includes("draft_github_comment") && (
                        <label>
                          Issue or PR number
                          <input
                            required
                            type="number"
                            min="1"
                            value={targets.issue_number}
                            onChange={(e) =>
                              setTargets({
                                ...targets,
                                issue_number: e.target.value,
                              })
                            }
                          />
                        </label>
                      )}
                      {capabilities.includes("draft_github_pr") && (
                        <>
                          <label>
                            Existing pushed head branch
                            <input
                              required
                              value={targets.head}
                              onChange={(e) =>
                                setTargets({ ...targets, head: e.target.value })
                              }
                            />
                          </label>
                          <label>
                            Base branch (optional)
                            <input
                              value={targets.base}
                              onChange={(e) =>
                                setTargets({ ...targets, base: e.target.value })
                              }
                            />
                          </label>
                        </>
                      )}
                      {sourceTurn && (
                        <p>
                          Starting from completed investigation:{" "}
                          {sourceTurn.question}
                        </p>
                      )}
                      <button className="primary" disabled={busy || !optIn}>
                        Start bounded workflow
                      </button>
                    </form>
                  )}
                  {current && (
                    <>
                      <h3>{current.goal}</h3>
                      <p role="status">
                        <strong>{current.stage}</strong> · {current.status}
                      </p>
                      <p>
                        {current.steps?.length || 0}/{current.limits.max_steps}{" "}
                        steps · {current.model_calls}/
                        {current.limits.max_model_calls} model calls ·{" "}
                        {current.retrieval_calls || 0}/60 retrieval calls ·{" "}
                        {Math.round(current.elapsed_seconds || 0)} seconds
                        recorded
                      </p>
                      {running && (
                        <button
                          disabled={busy || current.stop_requested}
                          onClick={() =>
                            perform(async () =>
                              setCurrent(
                                await send(`${route}/${current.id}/stop`, {}),
                              ),
                            )
                          }
                        >
                          Stop
                        </button>
                      )}
                      {current.stopping_reason && (
                        <p>{current.stopping_reason}</p>
                      )}
                      {(current.steps || []).map((step, i) => (
                        <details
                          className="workflow-step"
                          key={step.id}
                          open={step.status === "running"}
                        >
                          <summary>
                            Step {i + 1} — {step.objective} · {step.status}
                          </summary>
                          <p>{step.rationale}</p>
                          <p>
                            Allowed read tools:{" "}
                            {(step.allowed_tools || step.required_tools).join(
                              ", ",
                            ) || "none"}
                          </p>
                          <p>
                            Completion criteria:{" "}
                            {step.completion_criteria.join("; ")}
                          </p>
                          {step.error && (
                            <p className="failure">{step.error}</p>
                          )}
                          {step.claims?.map((claim, n) => (
                            <p key={n}>
                              {claim.text}
                              {claim.support.map((source) => (
                                <button
                                  className="doc-citation"
                                  key={source.evidence_id}
                                  onClick={() =>
                                    api(
                                      `${route}/${current.id}/evidence/${source.evidence_id}`,
                                    )
                                      .then(setEvidence)
                                      .catch((e) => setError(e.message))
                                  }
                                >
                                  Source {source.evidence_id.slice(0, 6)}
                                </button>
                              ))}
                            </p>
                          ))}
                          {step.limitations?.map((text, n) => (
                            <p key={n}>Limitation: {text}</p>
                          ))}
                          {step.artifacts?.map((artifact) => (
                            <ArtifactReview
                              key={artifact.id}
                              project={project}
                              workflow={current.id}
                              artifact={artifact}
                            />
                          ))}
                        </details>
                      ))}
                      {evidence && (
                        <details open>
                          <summary>Checked source: {evidence.title}</summary>
                          <pre>{evidence.text}</pre>
                        </details>
                      )}
                      {["stopped", "needs_input", "failed"].includes(
                        current.status,
                      ) && (
                        <form
                          onSubmit={(e) => {
                            e.preventDefault();
                            perform(async () =>
                              setCurrent(
                                await send(`${route}/${current.id}/resume`, {
                                  clarification,
                                  expected_status: current.status,
                                }),
                              ),
                            );
                          }}
                        >
                          <label>
                            Clarification or approval follow-up
                            <textarea
                              value={clarification}
                              maxLength={4000}
                              onChange={(e) => setClarification(e.target.value)}
                            />
                          </label>
                          <p>
                            Resume retains the original scope and remaining
                            budget; it does not approve external actions.
                          </p>
                          <button disabled={busy}>
                            Resume within remaining budget
                          </button>
                        </form>
                      )}
                    </>
                  )}
                </div>
              </div>
            </section>
          </div>,
          document.body,
        )}
    </>
  );
}
