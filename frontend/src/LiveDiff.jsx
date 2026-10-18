import React, { useState } from "react";
import { GitCompareArrows, FileCode2 } from "lucide-react";

export function diffRows(patch) {
  let oldLine = null,
    newLine = null;
  return patch.split("\n").map((text) => {
    const hunk = text.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
    if (hunk) {
      oldLine = Number(hunk[1]);
      newLine = Number(hunk[2]);
      return { text, kind: "hunk" };
    }
    if (/^(---|\+\+\+|diff |index |new file|deleted file)/.test(text))
      return { text, kind: "meta" };
    if (text.startsWith("+"))
      return {
        text,
        kind: "added",
        newLine: newLine === null ? null : newLine++,
      };
    if (text.startsWith("-"))
      return {
        text,
        kind: "removed",
        oldLine: oldLine === null ? null : oldLine++,
      };
    if (text.startsWith(" "))
      return {
        text,
        kind: "context",
        oldLine: oldLine === null ? null : oldLine++,
        newLine: newLine === null ? null : newLine++,
      };
    return { text, kind: "meta" };
  });
}

export default function LiveDiff({ action }) {
  const [selected, setSelected] = useState(null);
  const files = action.live_changes?.files || [];
  const approved = action.plan?.files || [];
  const file = files.find((item) => item.path === selected) || files[0];
  const editing =
    action.status === "running" && action.activity_phase === "editing";
  const rows = file ? diffRows(file.diff) : [];
  return (
    <section className="live-diff" aria-label="Live file changes">
      <header className="live-diff-heading">
        <div>
          <span className="eyebrow">ISOLATED WORKSPACE</span>
          <h3>
            <GitCompareArrows size={18} aria-hidden="true" />
            {editing ? "Agent file changes" : "Recorded file changes"}
          </h3>
        </div>
        <span role="status">
          {files.length} / {approved.length} files written
        </span>
      </header>
      <p className="live-diff-note">
        {action.status === "running"
          ? "Updates after each successful file write. These edits are provisional until testing and patch verification finish."
          : "Recorded successful writes. Inspect the verification report before applying this patch."}
      </p>
      <div
        className="live-diff-files"
        role="group"
        aria-label="Select changed file"
      >
        {approved.map((path) => {
          const change = files.find((item) => item.path === path);
          return (
            <button
              key={path}
              disabled={!change}
              aria-pressed={file?.path === path}
              onClick={() => setSelected(path)}
            >
              <FileCode2 size={13} aria-hidden="true" />
              <span>{path}</span>
              {change ? (
                <small>
                  <b className="diff-plus">+{change.additions}</b>{" "}
                  <b className="diff-minus">−{change.deletions}</b>
                </small>
              ) : (
                <small>Pending</small>
              )}
            </button>
          );
        })}
      </div>
      {file ? (
        <>
          <div className="change-explanation">
            <strong>Agent explanation</strong>
            <p>
              {file.explanation ||
                "No explanation was recorded for this write. Review the approved rationale below."}
            </p>
          </div>
          <details className="live-diff-rationale">
            <summary>Approved plan rationale</summary>
            <p>{action.plan.summary}</p>
            {action.plan.steps
              .filter((step) => step.includes(file.path))
              .map((step, i) => (
                <p key={i}>{step}</p>
              ))}
          </details>
          <div
            className="diff-code"
            role="region"
            aria-label={`Changes to ${file.path}`}
            tabIndex={0}
          >
            {file.diff ? (
              rows.slice(0, 800).map((row, index) => (
                <div className={`diff-line diff-${row.kind}`} key={index}>
                  <span className="diff-number" aria-hidden="true">
                    {row.oldLine ?? ""}
                  </span>
                  <span className="diff-number" aria-hidden="true">
                    {row.newLine ?? ""}
                  </span>
                  <code>{row.text || " "}</code>
                </div>
              ))
            ) : (
              <p>No remaining difference from the editor’s starting file.</p>
            )}
          </div>
          {(file.truncated ||
            rows.length > 800 ||
            action.live_changes?.bounded) && (
            <p className="coverage">
              Preview is bounded. The final downloadable patch remains the
              complete review artifact within the action’s patch limits.
            </p>
          )}
        </>
      ) : (
        <p className="live-diff-empty" role="status">
          Waiting for the first successful write to an approved file. Reads do
          not create a diff.
        </p>
      )}
    </section>
  );
}
