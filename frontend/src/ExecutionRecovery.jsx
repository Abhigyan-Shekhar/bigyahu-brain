import React from "react";

export default function ExecutionRecovery({ action, submitting, onResume }) {
  if (action.status !== "failed" || action.phase !== "execution" ||
      action.failure_kind !== "editor_timeout" || !action.recovery?.available) return null;
  return (
    <div className="execution-recovery">
      <p>
        Resume the preserved edits under the same approved files and commands.
        The editor must finish before baseline and patched tests run. This does
        not accept the partial patch as complete.
      </p>
      <button className="primary" disabled={submitting} onClick={onResume}>
        Resume editing
      </button>
    </div>
  );
}
