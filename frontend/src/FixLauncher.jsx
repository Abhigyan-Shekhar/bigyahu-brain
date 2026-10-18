import React, { useEffect, useState } from "react";
import { api, send } from "./api";
export default function FixLauncher({ turn, onRun }) {
  const [latest, setLatest] = useState(null),
    [editing, setEditing] = useState(false),
    [objective, setObjective] = useState(turn.question),
    [working, setWorking] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    api(`/turns/${turn.id}/actions`)
      .then((items) => {
        if (live) setLatest(items.at(-1));
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [turn.id]);
  async function plan(e) {
    e.preventDefault();
    setWorking(true);
    setError("");
    try {
      const run = await send(`/turns/${turn.id}/actions`, {
        question: objective,
      });
      setLatest(run);
      setEditing(false);
      onRun(run.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  }
  return (
    <section className="fix-launcher workflow-target" id={`fix-${turn.id}`}>
      <div>
        <strong>From investigation to a fix</strong>
        <p>
          {latest
            ? `${latest.status.replaceAll("_", " ")} · ${latest.stage}`
            : "Prepare a cited plan, then review files and tests before approving isolated editing."}
        </p>
      </div>
      {latest && (
        <button onClick={() => onRun(latest.id)}>Open linked agent run</button>
      )}
      <button disabled={working} onClick={() => setEditing(!editing)}>
        {editing
          ? "Close planner"
          : latest
            ? "Plan another change"
            : "Propose a fix"}
      </button>
      {error && (
        <p role="alert" className="failure">
          {error}
        </p>
      )}
      {editing && (
        <form onSubmit={plan}>
          <label htmlFor={`fix-objective-${turn.id}`}>Fix objective</label>
          <textarea
            id={`fix-objective-${turn.id}`}
            required
            maxLength={8000}
            rows={3}
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
          />
          <p>
            Planning is read-only. Agent Runs will show the evidence, scope and
            exact test commands for fresh human approval.
          </p>
          <button className="primary" disabled={working || !objective.trim()}>
            {working ? "Creating linked run…" : "Prepare cited plan"}
          </button>
        </form>
      )}
    </section>
  );
}
