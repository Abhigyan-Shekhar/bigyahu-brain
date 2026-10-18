import React from "react";
import { Check, LoaderCircle, CircleAlert, Activity } from "lucide-react";
import { elapsedLabel } from "./actionPresentation";
import { toolLabels } from "./investigationPresentation";
export default function ActivityStream({ turn }) {
  const progress = turn.progress;
  const live = ["running", "queued"].includes(turn.status);
  const events = progress?.completed_tools || [];
  return (
    <section
      className={`activity-stream activity-hero ${live ? "activity-live" : ""}`}
      aria-label="Observable agent activity"
    >
      <header>
        <span className="activity-symbol">
          <Activity size={20} />
        </span>
        <div>
          <span className="eyebrow">
            {live ? "AGENT IS WORKING" : "RECORDED INVESTIGATION"}
          </span>
          <h3>{turn.stage || turn.status.replaceAll("_", " ")}</h3>
        </div>
        <span className={`activity-state ${turn.status}`}>
          {turn.status.replaceAll("_", " ")}
        </span>
      </header>
      <div className="activity-now" role="status">
        {live && progress?.current_tool ? (
          <>
            <LoaderCircle size={17} className="spin" />
            <strong>
              {toolLabels[progress.current_tool] || progress.current_tool}
            </strong>
            <code>{progress.current_tool}</code>
          </>
        ) : (
          <>
            <span className={live ? "live-event-dot" : "event-dot"} />
            <span>
              {live
                ? progress?.activity_phase === "review" ||
                  turn.activity_phase === "review"
                  ? "Reviewing the proposal against its cited evidence"
                  : turn.phase === "execution"
                    ? "Following the current execution stage"
                    : "Waiting for the next recorded tool event"
                : "Activity retained from this run"}
            </span>
          </>
        )}
      </div>
      {progress && (
        <div className="activity-facts">
          <span>
            {progress.trace_bounded ? "At least " : ""}
            <strong>{progress.completed_count}</strong> recorded tool actions
          </span>
          {Number.isFinite(progress.elapsed_seconds) && (
            <span>{elapsedLabel(progress.elapsed_seconds)}</span>
          )}
          {turn.editor_timeout_seconds && turn.activity_phase === "editing" && (
            <span>
              Editing attempt {turn.editor_attempt} · {Math.floor(turn.editor_timeout_seconds / 60)} minute limit
            </span>
          )}
        </div>
      )}
      {progress?.stages?.length > 0 && (
        <dl className="stage-timings" aria-label="Stage timings">
          {progress.stages.map((stage, index) => (
            <div key={index} className={stage.active ? "timing-active" : ""}>
              <dt>
                {{
                  retrieval: "Investigation",
                  review: "Evidence review",
                  validation: "Source checks",
                  preparing: "Prepare workspace",
                  editing: "Editing",
                  baseline_tests: "Baseline tests",
                  patched_tests: "Patched tests",
                  verification: "Patch verification",
                }[stage.name] || stage.name}
              </dt>
              <dd>
                {Number.isFinite(stage.seconds)
                  ? `${Math.floor(stage.seconds)}s`
                  : "—"}
                {stage.active ? " · active" : ""}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {(progress?.retrieval || progress?.reused_evidence_count > 0) && (
        <div className="retrieval-budget">
          {progress.retrieval && (
            <span>
              {progress.retrieval.used}/{progress.retrieval.limit} retrieval
              executions · {progress.retrieval.context_used}/
              {progress.retrieval.context_limit} context searches
              {progress.retrieval.blocked > 0
                ? ` · ${progress.retrieval.blocked} extra calls blocked`
                : ""}
            </span>
          )}
          {progress.reused_evidence_count > 0 && (
            <span>
              {progress.reused_evidence_count} evidence records revalidated and
              reused
            </span>
          )}
        </div>
      )}
      {events.length > 0 && (
        <ol className="activity-events">
          {events.slice(-5).map((item, i) => (
            <li
              key={`${progress.completed_count - events.length + i}:${item.tool}`}
            >
              <span className={`activity-event-icon ${item.status}`}>
                {item.status === "completed" ? (
                  <Check size={13} />
                ) : (
                  <CircleAlert size={13} />
                )}
              </span>
              <div>
                <strong>{toolLabels[item.tool] || item.tool}</strong>
                <small>{item.tool}</small>
              </div>
              <span className={`tool-event ${item.status}`}>{item.status}</span>
            </li>
          ))}
        </ol>
      )}
      {!events.length && (
        <p className="activity-waiting">
          Tool actions will appear here when the backend records them.
        </p>
      )}
      {turn.error && (
        <p className="failure" role="alert">
          {turn.error}
        </p>
      )}
      <small className="activity-provenance">
        Live lifecycle stages and recorded tool events. No simulated work or
        estimated progress.
      </small>
    </section>
  );
}
