import React, { useEffect, useState } from "react";
import { api, send } from "./api";

export default function IngestionPanel({ project, refresh, onComplete }) {
  const [sources, setSources] = useState([]), [selected, setSelected] = useState([]),
    [engine, setEngine] = useState("sdk"), [jobs, setJobs] = useState([]),
    [error, setError] = useState(""), [submitting, setSubmitting] = useState(false);
  const active = jobs.some(j => ["queued", "running"].includes(j.status));
  useEffect(() => {
    let live = true;
    setSelected([]);
    api(`/repositories/${project}/documents`).then(v => { if (live) setSources(v); }).catch(e => setError(e.message));
    return () => { live = false; };
  }, [project, refresh]);
  useEffect(() => {
    let live = true, wasActive = false;
    async function poll() {
      try {
        const v = await api(`/repositories/${project}/enrichments`);
        if (!live) return;
        setJobs(v);
        const running = v.some(j => ["queued", "running"].includes(j.status));
        if (wasActive && !running) onComplete();
        wasActive = running;
      } catch(e) { if (live) setError(e.message); }
    }
    poll();
    const timer = setInterval(poll, 2000);
    return () => { live = false; clearInterval(timer); };
  }, [project]);
  async function extract(e) {
    e.preventDefault(); setSubmitting(true); setError("");
    try {
      const j = await send(`/repositories/${project}/enrichments`, {engine, sources:selected});
      setJobs(v => [...v,j]);
    } catch(e) { setError(e.message); } finally { setSubmitting(false); }
  }
  const latest = jobs.at(-1);
  return <details className="ingestion-panel">
    <summary>Document sources & semantic ingestion {active ? "· extracting…" : ""}</summary>
    <p>Upload Markdown, RST, PDF or Word (.docx) with Add document. Select up to eight source sections below to extract entities and relationships into FalkorDB.</p>
    <form onSubmit={extract}>
      <label>Extraction engine <select value={engine} onChange={e=>setEngine(e.target.value)} disabled={active}>
        <option value="sdk">FalkorDB GraphRAG SDK</option><option value="graphify">Graphify semantic pass</option>
      </select></label>
      <div className="source-selections">{sources.map(s => <label key={s.id}>
        <input type="checkbox" checked={selected.includes(s.id)} disabled={active}
          onChange={e=>setSelected(v=>e.target.checked ? [...v,s.id] : v.filter(id=>id!==s.id))}/>
        {s.path} · extracted/source lines {s.start}–{s.end}
      </label>)}</div>
      {!sources.length && <p>No document sections indexed yet.</p>}
      <p>Extraction sends selected text to the app’s configured Codex model and consumes account usage. Relationships remain advisory; citations retain their source. No embeddings are generated.</p>
      <button className="primary" disabled={active || submitting || !selected.length || selected.length>8}>Extract relationships</button>
    </form>
    {error && <p role="alert" className="failure">{error}</p>}
    {latest && <div role="status"><strong>{latest.stage}</strong>
      {latest.result && <p>{latest.result.engine}: {latest.result.nodes} entities, {latest.result.relationships} relationships indexed.</p>}
      {latest.error && <p className="failure">{latest.error}</p>}
    </div>}
  </details>;
}
