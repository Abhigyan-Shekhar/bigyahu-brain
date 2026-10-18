import React from "react";
import { elapsedLabel } from "./actionPresentation";
export default function ActivityStream({ turn }) {
  const progress = turn.progress;
  return (
    <section className="activity-stream" aria-label="Observable agent activity">
      <div>
        <span className={`run-status ${turn.status}`}>
          {turn.status.replaceAll("_", " ")}
        </span>
        <strong>{turn.stage}</strong>
      </div>
      {progress && (
        <>
          <p>
            {elapsedLabel(progress.elapsed_seconds)} ·{" "}
            {progress.trace_bounded ? "At least " : ""}
            {progress.completed_count} finished tool actions
          </p>
          {progress.current_tool && (
            <p role="status">
              Current tool: <code>{progress.current_tool}</code>
            </p>
          )}
          <ol>
            {progress.completed_tools.slice(-5).map((item, i) => (
              <li key={i}>
                <code>{item.tool}</code>
                <span className={`tool-event ${item.status}`}>
                  {item.status}
                </span>
              </li>
            ))}
          </ol>
        </>
      )}
      {turn.error && (
        <p className="failure" role="alert">
          {turn.error}
        </p>
      )}
      <small>
        Recorded tool events and lifecycle stages only. No private model
        reasoning or estimated percentage.
      </small>
    </section>
  );
}
