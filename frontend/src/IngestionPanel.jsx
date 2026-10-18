import React, { useEffect, useRef, useState } from "react";
import { api, send } from "./api";

export default function IngestionPanel({
  project,
  refresh,
  onComplete,
  onStatus,
}) {
  const [sources, setSources] = useState([]),
    [selected, setSelected] = useState([]),
    [engine, setEngine] = useState("graphify"),
    [jobs, setJobs] = useState([]),
    [error, setError] = useState(""),
    [submitting, setSubmitting] = useState(false);
  const callbacks = useRef({ onComplete, onStatus });
  callbacks.current = { onComplete, onStatus };
  const active = jobs.some((j) => ["queued", "running"].includes(j.status));
  useEffect(() => {
    let live = true;
    setSelected([]);
    api(`/repositories/${project}/documents`)
      .then((v) => {
        if (live) setSources(v);
      })
      .catch((e) => setError(e.message));
    return () => {
      live = false;
    };
  }, [project, refresh]);
  useEffect(() => {
    let live = true;
    const terminal = new Set();
    async function poll() {
      try {
        const v = await api(`/repositories/${project}/enrichments`);
        if (!live) return;
        setJobs(v);
        const running = v.some((j) => ["queued", "running"].includes(j.status));
        callbacks.current.onStatus?.(running);
        const finished = v.filter((j) =>
          ["complete", "failed"].includes(j.status),
        );
        if (finished.some((j) => !terminal.has(j.id))) {
          finished.forEach((j) => terminal.add(j.id));
          callbacks.current.onComplete?.();
        }
      } catch (e) {
        if (live) setError(e.message);
      }
    }
    poll();
    const timer = setInterval(poll, 2000);
    return () => {
      live = false;
      clearInterval(timer);
      callbacks.current.onStatus?.(false);
    };
  }, [project]);
  async function extract(e) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const j = await send(`/repositories/${project}/enrichments`, {
        engine,
        sources: selected,
      });
      setJobs((v) => [...v, j]);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }
  const latest = jobs.at(-1);
  const current = jobs.filter((j) => ["queued", "running"].includes(j.status));
  return (
    <div className="document-library">
      {(active ? current : latest ? [latest] : []).map((job) => (
        <div className="ingestion-status" role="status" key={job.id}>
          <strong>
            {active ? "Extraction" : "Latest extraction"} · {job.stage}
          </strong>
          {job.result && (
            <p>
              {job.result.nodes} entities · {job.result.relationships}{" "}
              relationships indexed
              {job.status === "failed" ? " before extraction stopped" : ""}.
            </p>
          )}
          {job.error && <p className="failure">{job.error}</p>}
        </div>
      ))}
      <details className="ingestion-panel">
        <summary>
          Document sources & extraction · {sources.length}
          {sources.length === 201 ? "+" : ""} listed sections{" "}
          {active ? "· extracting…" : ""}
        </summary>
        <p>
          Uploads are extracted automatically with Graphify. Select up to eight
          sections to retry extraction or compare engines. Text-based PDF, Word,
          Markdown and RST are supported.
        </p>
        <p className="action-note">
          Sections belong to the indexed repository snapshot. Extracted concepts
          and relationships are advisory; source citations remain available for
          inspection.
          {sources.length === 201 &&
            " This source picker is bounded; it does not establish complete document coverage."}
        </p>
        <form onSubmit={extract}>
          <label>
            Extraction engine{" "}
            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value)}
              disabled={active}
            >
              <option value="sdk">FalkorDB GraphRAG SDK</option>
              <option value="graphify">Graphify semantic pass</option>
            </select>
          </label>
          <div className="source-selections">
            {sources.map((s) => (
              <label key={s.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(s.id)}
                  disabled={active}
                  onChange={(e) =>
                    setSelected((v) =>
                      e.target.checked
                        ? [...v, s.id]
                        : v.filter((id) => id !== s.id),
                    )
                  }
                />
                {s.path} · extracted/source lines {s.start}–{s.end}
              </label>
            ))}
          </div>
          {!sources.length && <p>No document sections indexed yet.</p>}
          <p>
            Extraction sends selected text to the app’s configured Codex model
            and consumes account usage. Relationships retain their sources and
            remain advisory.
          </p>
          <button
            className="primary"
            disabled={
              active || submitting || !selected.length || selected.length > 8
            }
          >
            Extract relationships
          </button>
        </form>
        {error && (
          <p role="alert" className="failure">
            {error}
          </p>
        )}
      </details>
    </div>
  );
}
