import React, { useState } from "react";
import WorkTimeline, { Timestamp } from "./WorkTimeline";
import { deadlineGroup, deadlineLayout } from "./deadlinePresentation";

export default function DeadlineBoard({ data, onNode }) {
  const [depth, setDepth] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [tilt, setTilt] = useState(12);
  const [selected, setSelected] = useState(null);
  const layout = deadlineLayout(data.items);
  const width = Math.round(800 * zoom);
  const position = (fraction) => 72 + (width - 220) * fraction;
  const active = data.items.find((item) => item.uid === selected);
  return (
    <div className={`deadline-visual ${depth ? "has-depth" : ""}`}>
      <div className="deadline-view-controls" aria-label="Adjust deadline view">
        <div role="group" aria-label="Timeline dimension">
          <button aria-pressed={!depth} onClick={() => setDepth(false)}>
            2D timeline
          </button>
          <button aria-pressed={depth} onClick={() => setDepth(true)}>
            3D depth
          </button>
        </div>
        <label>
          Zoom{" "}
          <input
            type="range"
            min="0.75"
            max="2.5"
            step="0.05"
            value={zoom}
            onChange={(event) => setZoom(Number(event.target.value))}
          />
          <output>{Math.round(zoom * 100)}%</output>
        </label>
        <label>
          Angle{" "}
          <input
            type="range"
            min="0"
            max="24"
            value={tilt}
            disabled={!depth}
            onChange={(event) => setTilt(Number(event.target.value))}
          />
          <output>{depth ? tilt : 0}°</output>
        </label>
        <button
          onClick={() => {
            setDepth(false);
            setZoom(1);
            setTilt(12);
          }}
        >
          Reset view
        </button>
      </div>
      <p className="deadline-board-help">
        Select a deadline to inspect its decisions below. Scroll to pan; drag
        the bottom corner to resize this view. View controls do not change due
        dates.
      </p>
      <div
        className="deadline-board-viewport"
        tabIndex={0}
        aria-label="Scrollable deadline timeline"
        style={{ "--deadline-angle": `${depth ? tilt : 0}deg` }}
      >
        <div
          className="deadline-board-space"
          style={{
            width,
            minHeight: Math.max(240, layout.dated.length * 82 + 90),
          }}
        >
          <div className="deadline-board-grid">
            {layout.dated.length > 0 && (
              <div className="deadline-axis">
                <Timestamp value={new Date(layout.start).toISOString()} />
                <span>→</span>
                <Timestamp value={new Date(layout.end).toISOString()} />
              </div>
            )}
            {layout.nowFraction !== null && (
              <div
                className="deadline-now"
                style={{ left: position(layout.nowFraction) }}
              >
                <span>NOW</span>
              </div>
            )}
            {layout.dated.map(({ item, fraction }, index) => (
              <div
                key={item.uid}
                className="deadline-track"
                style={{ top: 62 + index * 82 }}
              >
                <button
                  className={`deadline-node deadline-${deadlineGroup(item)}`}
                  style={{ left: position(fraction) }}
                  aria-pressed={selected === item.uid}
                  onClick={() => setSelected(item.uid)}
                >
                  <span>
                    {item.kind} · {item.status || "Unknown"}
                  </span>
                  <strong>{item.title}</strong>
                  <Timestamp value={item.due_at} />
                </button>
              </div>
            ))}
            {!layout.dated.length && (
              <p className="deadline-board-empty">
                No dated work in this filter. Undated items appear below.
              </p>
            )}
          </div>
        </div>
      </div>
      {!!layout.undated.length && (
        <section className="deadline-undated">
          <h4>Unscheduled · {layout.undated.length}</h4>
          {layout.undated.map((item) => (
            <button
              key={item.uid}
              aria-pressed={selected === item.uid}
              onClick={() => setSelected(item.uid)}
            >
              {item.kind} · {item.title}
            </button>
          ))}
        </section>
      )}
      {active && (
        <section
          className="deadline-selection"
          aria-label="Selected deadline details"
        >
          <h3>Decision trail</h3>
          <WorkTimeline data={{ items: [active] }} onNode={onNode} />
        </section>
      )}
      {data.truncated && (
        <p>First {data.limits.work_items} work items shown.</p>
      )}
      {data.decisions_truncated && (
        <p>
          Decision links limited to {data.limits.decision_links}; inspect the
          full index for additional history.
        </p>
      )}
    </div>
  );
}
