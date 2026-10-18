import React, { useEffect, useState } from "react";
import { api } from "./api";
import ActionPanel from "./ActionPanel";
import InvestigationRun from "./InvestigationRun";

export default function AgentRuns({
  project,
  selected,
  onSelect,
  onInvestigation,
  onEvidence,
  onReviewMemory,
}) {
  const [bounded, setBounded] = useState(false);
  const [browseRuns, setBrowseRuns] = useState(
    () => matchMedia("(min-width: 1051px)").matches,
  );
  useEffect(() => {
    const query = matchMedia("(min-width: 1051px)");
    const resize = () => setBrowseRuns(query.matches);
    query.addEventListener("change", resize);
    return () => query.removeEventListener("change", resize);
  }, []);
  const [runs, setRuns] = useState([]),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setRuns([]);
    const refresh = () =>
      api(`/repositories/${project}/actions`)
        .then((r) => {
          if (active) {
            setRuns([...r.items, ...(r.investigations || [])]);
            setBounded(!!r.truncated || !!r.investigations_truncated);
            setError("");
          }
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    refresh();
    const timer = setInterval(refresh, 1500);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [project]);
  const [resolved, setResolved] = useState(null);
  const listed = runs.some((r) => r.id === selected);
  useEffect(() => {
    if (!selected || listed) return;
    let live = true;
    setResolved({ project, id: selected, loading: true });
    api(`/repositories/${project}/runs/${selected}`)
      .then((value) => {
        if (live) setResolved({ project, id: selected, value });
      })
      .catch((e) => {
        if (live) setResolved({ project, id: selected, error: e.message });
      });
    return () => {
      live = false;
    };
  }, [project, selected, listed]);
  const direct =
    resolved?.project === project && resolved?.id === selected
      ? resolved
      : null;
  const run =
    runs.find((r) => r.id === selected) ||
    direct?.value ||
    (!selected
      ? runs.find((r) =>
          ["queued", "running", "awaiting_approval"].includes(r.status),
        ) ||
        runs.filter((r) => r.run_kind !== "investigation").at(-1) ||
        runs[0]
      : null);
  return (
    <div className="runs-workspace">
      <aside className="run-list">
        <details
          open={browseRuns}
          onToggle={(e) => setBrowseRuns(e.currentTarget.open)}
        >
          <summary>
            Investigations & fixes <small>{runs.length} runs</small>
          </summary>
          <p>
            Follow the investigation, review the change, and compare the test
            outcome.
          </p>
          {error && (
            <p role="alert" className="failure">
              {error}
            </p>
          )}
          {bounded && (
            <p className="coverage">
              Showing the latest 20 fix runs and 20 investigations. Older runs
              remain available from their conversations and saved lessons.
            </p>
          )}
          {!runs.length && (
            <p>
              No fix runs yet. Investigate in Ask Brain, then choose Plan a
              change.
            </p>
          )}
          {[...runs.filter((r) => r.run_kind !== "investigation")]
            .reverse()
            .concat(runs.filter((r) => r.run_kind === "investigation"))
            .map((r) => (
              <button
                className={run?.id === r.id ? "selected" : ""}
                key={r.id}
                onClick={() => onSelect(r.id)}
              >
                <span className={`run-status ${r.status}`}>
                  {r.run_kind === "investigation"
                    ? "Investigation · "
                    : "Fix · "}
                  {r.status === "complete"
                    ? r.run_kind === "investigation"
                      ? "Finished"
                      : "Execution finished"
                    : r.status.replaceAll("_", " ")}
                </span>
                <strong title={r.objective}>
                  {r.title || r.question || r.objective}
                </strong>
                <small>{r.stage}</small>
                {r.run_kind !== "investigation" && r.status === "complete" && (
                  <span className="run-result">
                    {r.tests_passed ? "Tests passed" : "Tests need review"} ·{" "}
                    {r.regression_demonstrated
                      ? "Regression demonstrated"
                      : "Fix unverified"}
                  </span>
                )}
              </button>
            ))}
        </details>
      </aside>
      <div className="run-review">
        {run ? (
          run.run_kind === "investigation" ? (
            <InvestigationRun
              key={run.id}
              run={{ ...run, project }}
              onEvidence={onEvidence}
              onInvestigation={onInvestigation}
              onPlan={onInvestigation}
            />
          ) : (
            <>
              <div className="run-origin">
                <details>
                  <summary>Original investigation</summary>
                  <p>{run.question}</p>
                </details>
                <button onClick={() => onInvestigation(run)}>
                  Return to investigation
                </button>
              </div>
              <ActionPanel
                key={run.id}
                actionId={run.id}
                turn={{ id: run.turn, question: run.question }}
                project={project}
                onInvestigation={() => onInvestigation(run)}
                onEvidence={(id, evidence) =>
                  onEvidence(id, evidence, "actions", run)
                }
                onReviewMemory={onReviewMemory}
                onAction={(a) => onSelect(a.id)}
              />
            </>
          )
        ) : selected ? (
          direct?.error ? (
            <p role="alert" className="failure">
              Unable to open the selected run: {direct.error}
            </p>
          ) : (
            <p role="status">Loading the selected run…</p>
          )
        ) : (
          <p>Select a run or begin with an investigation.</p>
        )}
      </div>
    </div>
  );
}
