import React, { useEffect, useState } from "react";
import { api } from "./api";
import WorkTimeline from "./WorkTimeline";
import { deadlineGroup } from "./deadlinePresentation";
import DeadlineBoard from "./DeadlineBoard";

export default function DeadlinePanel({ project, onNode }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("all");
  const [refresh, setRefresh] = useState(0);
  const [view, setView] = useState("timeline");
  useEffect(() => {
    let live = true;
    setData(null);
    setError("");
    api(`/repositories/${project}/deadlines`)
      .then((value) => {
        if (live) setData(value);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [project, refresh]);
  return (
    <section className="deadline-panel">
      <p>
        Milestone deadlines and timestamped decisions from indexed GitHub issues
        and PRs. Times use your local timezone.
      </p>
      <div className="deadline-tabs" aria-label="Deadline filters">
        {[
          ["all", "All"],
          ["upcoming", "Upcoming"],
          ["overdue", "Overdue"],
          ["undated", "No deadline"],
        ].map(([value, label]) => (
          <button
            key={value}
            aria-pressed={tab === value}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
        <button onClick={() => setRefresh((value) => value + 1)}>
          Refresh
        </button>
      </div>
      <div
        className="deadline-display-tabs"
        role="group"
        aria-label="Deadline presentation"
      >
        <button
          aria-pressed={view === "timeline"}
          onClick={() => setView("timeline")}
        >
          Interactive timeline
        </button>
        <button aria-pressed={view === "list"} onClick={() => setView("list")}>
          Decision list
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading indexed deadlines…</p>}
      {data &&
        React.createElement(
          view === "timeline" ? DeadlineBoard : WorkTimeline,
          {
            data: {
              ...data,
              items: data.items.filter(
                (item) => tab === "all" || deadlineGroup(item) === tab,
              ),
            },
            onNode,
          },
        )}
      <p>
        Refresh reads the current index. Sync GitHub to acquire new changes.
        Proposed decisions remain advisory.
      </p>
    </section>
  );
}
