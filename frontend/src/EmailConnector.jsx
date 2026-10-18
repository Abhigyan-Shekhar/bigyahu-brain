import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Mail, X } from "lucide-react";
import { api, send } from "./api";

export default function EmailConnector({ project, latestTurn }) {
  const [open, setOpen] = useState(false);
  const [account, setAccount] = useState(null);
  const [recipient, setRecipient] = useState("");
  const [purpose, setPurpose] = useState("");
  const [job, setJob] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const dialog = useRef(null),
    trigger = useRef(null);
  const pending = useRef(null);
  const route = `/repositories/${project}/emails`;
  const active = submitting || ["queued", "running"].includes(job?.status);

  async function refresh() {
    try {
      const [connection, recent] = await Promise.all([
        api("/email/connection"),
        api(route),
      ]);
      setAccount(connection);
      setHistory(recent.items.slice().reverse());
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    if (!open) return;
    refresh();
    dialog.current?.focus();
    function keys(event) {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
      if (event.key !== "Tab") return;
      const nodes = Array.from(
        dialog.current.querySelectorAll("button, input, textarea"),
      ).filter(
        (node) => !node.matches(":disabled") && node.getClientRects().length,
      );
      const first = nodes[0],
        last = nodes.at(-1);
      if (
        event.shiftKey &&
        [dialog.current, first].includes(document.activeElement)
      ) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    dialog.current?.addEventListener("keydown", keys);
    return () => dialog.current?.removeEventListener("keydown", keys);
  }, [open, project]);

  useEffect(() => {
    if (!open) return;
    let stopped = false;
    const timer = setInterval(async () => {
      try {
        const recent = await api(route);
        if (stopped) return;
        setHistory(recent.items.slice().reverse());
        if (job) {
          const value = recent.items.find((item) => item.id === job.id);
          if (value) setJob(value);
        }
      } catch (e) {
        if (!stopped) setError(e.message);
      }
    }, 2500);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [open, project, job?.id]);

  async function submit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    const body = { recipient, purpose, turn: latestTurn?.id || null };
    const key = JSON.stringify(body);
    if (pending.current && pending.current.key !== key) {
      setError(
        "Resolve the previous request before changing the recipient or message.",
      );
      setSubmitting(false);
      return;
    }
    pending.current ||= { key, request_id: crypto.randomUUID() };
    try {
      const value = await send(route, {
        ...body,
        request_id: pending.current.request_id,
      });
      setJob(value);
      await refresh();
    } catch (e) {
      if (e.status >= 400 && e.status < 500) {
        pending.current = null;
        setError(e.message);
      } else {
        setError(
          e.message +
            " Retry the same request to check its status; it will not send twice.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }
  function newMessage() {
    pending.current = null;
    setJob(null);
    setError("");
    setPurpose("");
  }
  return (
    <>
      <button ref={trigger} onClick={() => setOpen(true)}>
        <Mail size={15} /> Email
      </button>
      {open &&
        createPortal(
          <div className="modal-backdrop">
            <section
              className="modal github-connector email-connector"
              role="dialog"
              aria-modal="true"
              aria-label="Project email"
              tabIndex={-1}
              ref={dialog}
            >
              <button
                className="modal-close"
                aria-label="Close email connector"
                onClick={() => {
                  setOpen(false);
                  trigger.current?.focus();
                }}
              >
                <X size={20} />
              </button>
              <h2>Email a collaborator</h2>
              <p>
                Enter their address. AI will write and send a project email
                using the discussion below.
              </p>
              {account?.configured ? (
                <p>
                  From <strong>{account.sender}</strong> ·{" "}
                  {account.verified
                    ? "Connection verified"
                    : "Sender configured"}
                </p>
              ) : (
                <p>
                  {account?.error || "Checking sender setup…"} Configure the
                  sender on the app server using <code>BRAIN_EMAIL_CONFIG</code>
                  . See docs/email-connector.md.
                </p>
              )}
              <button
                disabled={active}
                onClick={async () => {
                  setError("");
                  try {
                    setAccount(await send("/email/connection/check", {}));
                  } catch (e) {
                    setError(e.message);
                  }
                }}
              >
                Check sender connection
              </button>
              {error && (
                <p className="failure" role="alert">
                  {error}
                </p>
              )}
              <form onSubmit={submit}>
                <fieldset disabled={active || !!job || !account?.configured}>
                  <label>
                    Recipient email
                    <input
                      type="email"
                      required
                      maxLength={254}
                      value={recipient}
                      onChange={(e) => setRecipient(e.target.value)}
                    />
                  </label>
                  <label>
                    What should the email ask or discuss? (optional)
                    <textarea
                      rows={3}
                      maxLength={4000}
                      value={purpose}
                      onChange={(e) => setPurpose(e.target.value)}
                      placeholder="Ask for feedback, clarify requirements, or summarize the discussion"
                    />
                  </label>
                  {latestTurn ? (
                    <p>
                      Discussion: <strong>{latestTurn.question}</strong>
                    </p>
                  ) : (
                    <p>
                      No completed discussion selected. Add a purpose so AI
                      knows what to write.
                    </p>
                  )}
                  <p>
                    Generate & send emails the AI-written subject and body to
                    this recipient immediately.
                  </p>
                  <button
                    className="primary"
                    type="submit"
                    disabled={
                      active ||
                      !!job ||
                      !account?.configured ||
                      (!latestTurn && !purpose.trim())
                    }
                  >
                    {active ? "Writing & sending…" : "Generate & send"}
                  </button>
                </fieldset>
              </form>
              {job && (
                <div className="github-preview" role="status">
                  <h3>{job.stage}</h3>
                  <p>
                    {job.sender} → {job.recipient}
                  </p>
                  {job.error && <p className="failure">{job.error}</p>}
                  {job.subject && <h4>{job.subject}</h4>}
                  {job.body && <pre>{job.body}</pre>}
                  {job.notice && <p>{job.notice}</p>}
                  {!active && <button onClick={newMessage}>New email</button>}
                </div>
              )}
              {!!history.length && (
                <details>
                  <summary>Recent emails</summary>
                  <ul>
                    {history.map((item) => (
                      <li key={item.id}>
                        <button
                          disabled={active}
                          onClick={() => {
                            setJob(item);
                            setError("");
                          }}
                        >
                          {item.recipient} · {item.subject || "Project email"} ·{" "}
                          {item.status}
                        </button>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </section>
          </div>,
          document.body,
        )}
    </>
  );
}
