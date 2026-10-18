import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export default function ApprovalDecision({
  action,
  busy,
  onApprove,
  onReject,
  onChanges,
  error,
}) {
  const [open, setOpen] = useState(false);
  const dialog = useRef(null),
    trigger = useRef(null);
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else if (wasOpen.current) trigger.current?.focus();
    wasOpen.current = open;
  }, [open]);
  const close = () => setOpen(false);
  async function decide(callback) {
    if (await callback()) close();
  }
  return (
    <div className="decision-callout">
      <span className="decision-kicker">YOUR DECISION</span>
      <h4>Ready for your review.</h4>
      <p>
        {action.plan?.files?.length || 0} files in scope · Review the exact plan
        and test commands before execution.
      </p>
      <button
        ref={trigger}
        className="decision-open"
        onClick={() => setOpen(true)}
      >
        Review approval / rejection ↗
      </button>
      {open &&
        createPortal(
          <dialog
            ref={dialog}
            className="decision-dialog"
            aria-labelledby="decision-title"
            onCancel={(event) => {
              event.preventDefault();
              close();
            }}
          >
            <header>
              <span className="decision-kicker">PLAN REVIEW</span>
              <button aria-label="Close plan decision" onClick={close}>
                ×
              </button>
            </header>
            <h2 id="decision-title">Give this plan the go-ahead?</h2>
            <p>{action.plan?.summary}</p>
            <h3>Files permitted to change</h3>
            <ul>
              {action.plan?.files?.map((file) => (
                <li key={file}>
                  <code>{file}</code>
                </li>
              ))}
            </ul>
            <h3>Tests you authorize</h3>
            {action.plan?.commands?.map((argv, index) => (
              <pre key={index}>{argv.join(" ")}</pre>
            ))}
            <p>
              Approval runs this plan’s edits and tests in a separate checkout.
            </p>
            {error && (
              <p role="alert" className="failure">
                {error}
              </p>
            )}
            <div className="decision-buttons">
              {onChanges && (
                <button disabled={busy} onClick={() => decide(onChanges)}>
                  Request changes
                </button>
              )}
              <button
                className="decision-reject"
                disabled={busy}
                onClick={() => decide(onReject)}
              >
                ✕ Reject plan
              </button>
              <button
                className="decision-approve"
                disabled={busy}
                onClick={() => decide(onApprove)}
              >
                ✓ Approve execution
              </button>
            </div>
          </dialog>,
          document.body,
        )}
    </div>
  );
}
