import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ReactFlow, Background, Controls, MarkerType } from "@xyflow/react";
import {
  BrainCircuit,
  Network,
  MessageSquare,
  Plus,
  ArrowUp,
  ArrowUpRight,
  FileText,
  GitBranch,
  Check,
  LoaderCircle,
  X,
  BookOpen,
  ChevronRight,
  PanelRightClose,
  CircleAlert,
} from "lucide-react";
import "@xyflow/react/dist/style.css";
import "./style.css";
import { api, send } from "./api";
import ActionPanel from "./ActionPanel";
import IngestionPanel from "./IngestionPanel";
import PersonalBrain from "./PersonalBrain";
import TeamBrain from "./TeamBrain";

const fragment = location.hash.slice(1);
if (fragment) {
  sessionStorage.setItem("company-brain-token", fragment);
  history.replaceState(null, "", location.pathname);
}
function Graph({ graph, compact = false, onExpand }) {
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [expandTarget, setExpandTarget] = useState("");
  useEffect(() => setSelectedEdge(null), [graph]);
  const groups = {};
  const nodes = (graph?.nodes || []).map((n) => {
    const kind = n.labels?.[0] || "Node";
    const col = [
      "Project",
      "File",
      "Symbol",
      "Document",
      "Source",
      "Commit",
      "PR",
      "Issue",
      "Person",
      "Team",
    ].indexOf(kind);
    const key = col < 0 ? 10 : col;
    const i = groups[key] || 0;
    groups[key] = i + 1;
    return {
      id: n.id,
      displayLabel: n.label,
      sourcePosition: "right",
      targetPosition: "left",
      position: { x: key * 260, y: i * 95 },
      data: {
        label: (
          <>
            <small>{kind}</small>
            <span title={n.id}>{n.label.split("/").slice(-2).join("/")}</span>
          </>
        ),
      },
      style: { width: 220 },
    };
  });
  const ids = new Set(nodes.map((n) => n.id));
  const edges = (graph?.edges || [])
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e, i) => ({
      ...e,
      id: String(i),
      label: e.relation,
      data: e,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: { stroke: "#8b80bd" },
      labelStyle: { fontSize: 10 },
    }));
  return (
    <div className={"graph " + (compact ? "compact" : "")}>
      {onExpand && (
        <div className="graph-node-picker">
          <select
            aria-label="Node to expand"
            value={expandTarget}
            onChange={(e) => setExpandTarget(e.target.value)}
          >
            <option value="">Choose a node…</option>
            {nodes.map((n) => (
              <option key={n.id} value={n.id}>
                {n.displayLabel}
              </option>
            ))}
          </select>
          <button
            disabled={!expandTarget}
            onClick={() => onExpand(expandTarget)}
          >
            Expand neighbors
          </button>
        </div>
      )}
      {edges.length > 0 && (
        <select
          className="graph-edge-picker"
          aria-label="Inspect relationship"
          value={edges.find((e) => e.data === selectedEdge)?.id ?? ""}
          onChange={(event) =>
            setSelectedEdge(
              edges.find((e) => e.id === event.target.value)?.data ?? null,
            )
          }
        >
          <option value="">Inspect a relationship…</option>
          {edges.map((edge) => (
            <option key={edge.id} value={edge.id}>
              {nodes.find((n) => n.id === edge.source)?.displayLabel} →{" "}
              {edge.label} →{" "}
              {nodes.find((n) => n.id === edge.target)?.displayLabel}
            </option>
          ))}
        </select>
      )}
      {selectedEdge && (
        <aside className="graph-edge-detail">
          <button
            onClick={() => setSelectedEdge(null)}
            aria-label="Close relationship details"
          >
            ×
          </button>
          <strong>{selectedEdge.relation}</strong>
          <p>
            Stored type: {selectedEdge.edge_type || selectedEdge.relation}
            {selectedEdge.confidence ? ` · ${selectedEdge.confidence}` : ""}
          </p>
          {selectedEdge.quote && <blockquote>{selectedEdge.quote}</blockquote>}
          {selectedEdge.source_uid && (
            <small>Source: {selectedEdge.source_uid}</small>
          )}
        </aside>
      )}
      <ReactFlow
        key={nodes.map((n) => n.id).join("|")}
        nodes={nodes}
        edges={edges}
        onNodeDoubleClick={(_, node) => onExpand?.(node.id)}
        onEdgeClick={(_, edge) => setSelectedEdge(edge.data)}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        fitView
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.02}
        maxZoom={1.5}
        deleteKeyCode={null}
        proOptions={{ hideAttribution: false }}
      >
        <Background color="#dcd9e5" gap={22} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
function App() {
  const [repos, setRepos] = useState([]),
    [project, setProject] = useState(null),
    [sessions, setSessions] = useState([]),
    [session, setSession] = useState(null),
    [turns, setTurns] = useState([]),
    [mode, setMode] = useState("chat"),
    [graph, setGraph] = useState(null),
    [filter, setFilter] = useState(""),
    [question, setQuestion] = useState(""),
    [error, setError] = useState(""),
    [adding, setAdding] = useState(false),
    [url, setUrl] = useState(""),
    [connecting, setConnecting] = useState(false),
    [selected, setSelected] = useState(null),
    [loadingEvidence, setLoadingEvidence] = useState(false),
    [model, setModel] = useState(""),
    [uploading, setUploading] = useState(false),
    [uploadNotice, setUploadNotice] = useState(""),
    [historyRequired, setHistoryRequired] = useState(true),
    [expansion, setExpansion] = useState(null);
  const repo = repos.find((r) => r.id === project),
    busy = turns.some((t) => ["running", "queued"].includes(t.status));
  async function refresh() {
    try {
      const values = await api("/repositories");
      setRepos(values);
      setProject((p) => p || values.at(-1)?.id || null);
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    refresh();
    api("/status")
      .then((s) => setModel(s.model))
      .catch((e) => setError(e.message));
    const id = setInterval(refresh, 2000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    setTurns([]);
    setSession(null);
    setSelected(null);
    setGraph(null);
    if (!project) return;
    api(`/repositories/${project}/sessions`)
      .then((s) => {
        setSessions(s);
        setSession(s.at(-1)?.id || null);
      })
      .catch((e) => setError(e.message));
  }, [project]);
  useEffect(() => {
    if (!session) return;
    let active = true;
    const refreshTurns = () =>
      api(`/sessions/${session}/turns`)
        .then((t) => {
          if (active) setTurns(t);
        })
        .catch((e) => setError(e.message));
    refreshTurns();
    const id = setInterval(refreshTurns, 1500);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, [session]);
  const graphRequest = useRef(0);
  const activeProject = useRef(project);
  activeProject.current = project;
  async function expandNode(uid, offset = 0) {
    const request = ++graphRequest.current;
    try {
      const extra = await api(
        `/repositories/${project}/graph/neighbors?uid=${encodeURIComponent(uid)}&offset=${offset}`,
      );
      if (request !== graphRequest.current || project !== activeProject.current)
        return;
      const nodes = [
        ...new Map(
          [...(graph?.nodes || []), ...extra.nodes].map((n) => [n.id, n]),
        ).values(),
      ];
      const edges = [
        ...new Map(
          [...(graph?.edges || []), ...extra.edges].map((e) => [
            JSON.stringify(e),
            e,
          ]),
        ).values(),
      ];
      if (nodes.length > 300 || edges.length > 600)
        throw new Error(
          "View limit reached; filter to start another investigation.",
        );
      setGraph({ ...extra, nodes, edges });
      setExpansion(extra);
    } catch (e) {
      if (request === graphRequest.current && project === activeProject.current)
        setError(e.message);
    }
  }
  async function loadGraph(q = filter) {
    const request = ++graphRequest.current;
    try {
      setExpansion(null);
      const next = await api(
        `/repositories/${project}/graph?query=${encodeURIComponent(q)}`,
      );
      if (request === graphRequest.current && project === activeProject.current)
        setGraph(next);
    } catch (e) {
      if (request === graphRequest.current && project === activeProject.current)
        setError(e.message);
    }
  }
  useEffect(() => {
    if (repo?.status === "ready") loadGraph("");
  }, [project, repo?.status]);
  async function connect(e) {
    e.preventDefault();
    setConnecting(true);
    setError("");
    try {
      const value = await send("/repositories", {
        url,
        history: true,
        history_required: historyRequired,
      });
      setRepos((v) => [...v, value]);
      setProject(value.id);
      setAdding(false);
      setUrl("");
    } catch (e) {
      setError(e.message);
    } finally {
      setConnecting(false);
    }
  }
  async function newChat() {
    const chat = await send(`/repositories/${project}/sessions`, {});
    setSessions((s) => [...s, chat]);
    setSession(chat.id);
    setTurns([]);
    setSelected(null);
    return chat.id;
  }
  async function ask(e) {
    e.preventDefault();
    if (!question.trim() || busy) return;
    setError("");
    try {
      const id = session || (await newChat());
      const turn = await send(`/sessions/${id}/turns`, { question });
      setTurns((t) => [...t, turn]);
      setQuestion("");
    } catch (e) {
      setError(e.message);
    }
  }
  async function citation(turn, id, kind = "turns") {
    setLoadingEvidence(true);
    setSelected(null);
    try {
      setSelected(await api(`/${kind}/${turn}/evidence/${id}`));
      if (matchMedia("(max-width:680px)").matches)
        requestAnimationFrame(() =>
          document
            .querySelector(".evidence-panel")
            ?.scrollIntoView({ behavior: "smooth", block: "start" }),
        );
    } catch (e) {
      setError(e.message);
    } finally {
      setLoadingEvidence(false);
    }
  }
  async function upload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const binary = /\.(pdf|docx)$/i.test(file.name);
      if (file.size > (binary ? 1400000 : 500000))
        throw Error(
          binary
            ? "Choose a PDF/DOCX under 1.4 MB"
            : "Choose a text document under 500 KB",
        );
      const bytes = new Uint8Array(await file.arrayBuffer());
      let payload;
      if (binary) {
        let encoded = "";
        for (let i = 0; i < bytes.length; i += 8192)
          encoded += String.fromCharCode(...bytes.subarray(i, i + 8192));
        payload = { data_base64: btoa(encoded) };
      } else
        payload = {
          text: new TextDecoder("utf-8", { fatal: true }).decode(bytes),
        };
      const result = await send(`/repositories/${project}/documents`, {
        filename: file.name,
        ...payload,
      });
      setSelected(null);
      await loadGraph();
      setError("");
      setUploadNotice(
        `${result.filename}: ${result.sections} source-backed sections indexed.`,
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="/" onClick={(e) => e.preventDefault()}>
          <span className="brand-icon">
            <BrainCircuit size={24} />
          </span>
          <span>
            Company Brain<small>CONTEXT FOR BETTER WORK</small>
          </span>
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <button
          className={"nav " + (mode === "chat" ? "active" : "")}
          onClick={() => setMode("chat")}
        >
          <MessageSquare size={17} /> Conversations
        </button>
        <button
          className={"nav " + (mode === "graph" ? "active" : "")}
          onClick={() => setMode("graph")}
        >
          <Network size={17} /> Company graph
          {graph && <span className="count">{graph.nodes.length}</span>}
        </button>
        <button
          className={"nav " + (mode === "memory" ? "active" : "")}
          onClick={() => setMode("memory")}
        >
          <BrainCircuit size={17} /> Personal Brain
        </button>
        <button
          className={"nav " + (mode === "team" ? "active" : "")}
          onClick={() => setMode("team")}
        >
          <Network size={17} /> Team Brain
        </button>
        <div className="section-label">
          CONNECTED SOURCES
          <button
            aria-label="Connect repository"
            onClick={() => setAdding(true)}
          >
            <Plus size={16} />
          </button>
        </div>
        <div className="repo-list">
          {repos.map((r) => (
            <button
              key={r.id}
              className={"repo " + (r.id === project ? "selected" : "")}
              onClick={() => setProject(r.id)}
            >
              <GitBranch size={16} />
              <span>
                {r.name.split("/").at(-1)}
                <small>{r.status === "ready" ? "Indexed" : r.stage}</small>
              </span>
              <span className={"dot " + r.status} />
            </button>
          ))}
        </div>
        <button className="add-source" onClick={() => setAdding(true)}>
          <Plus size={15} /> Connect repository
        </button>
        <div className="section-label">
          CONVERSATIONS
          <button
            aria-label="New conversation"
            disabled={repo?.status !== "ready"}
            onClick={() => newChat().catch((e) => setError(e.message))}
          >
            <Plus size={16} />
          </button>
        </div>
        <div className="sessions">
          {sessions.map((s) => (
            <button
              key={s.id}
              className={session === s.id ? "current" : ""}
              onClick={() => {
                setSession(s.id);
                setSelected(null);
              }}
            >
              <MessageSquare size={14} />
              {s.title}
            </button>
          ))}
        </div>
        <div className="operator">
          <span className="avatar">LO</span>
          <span>
            Local operator<small>Private workspace</small>
          </span>
          <span className="dot ready" />
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace</span>
            <ChevronRight size={14} />
            <strong>{repo?.name || "Get started"}</strong>
          </div>
          <div className="mobile-sources">
            <select
              aria-label="Selected repository"
              value={project || ""}
              onChange={(e) => setProject(e.target.value)}
            >
              <option value="" disabled>
                Choose repository
              </option>
              {repos.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
            <button aria-label="Connect source" onClick={() => setAdding(true)}>
              <Plus size={16} />
            </button>
          </div>
          <span className="read-only">
            <span className="dot ready" /> Read-only chat · approved actions
          </span>
        </header>
        {error && (
          <div className="error" role="alert">
            <CircleAlert size={16} />
            {error}
            <button aria-label="Dismiss error" onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}
        {!repo ? (
          <div className="welcome">
            <span className="eyebrow">A SHARED UNDERSTANDING</span>
            <h1>
              Your code has a history.
              <br />
              Put it to work.
            </h1>
            <p>
              Connect a repository to explore the code, recover its context, and
              ask questions with sources you can inspect.
            </p>
            <button className="primary" onClick={() => setAdding(true)}>
              <Plus size={17} /> Connect your first repository
            </button>
            <div className="welcome-steps">
              <span>
                <GitBranch />
                Index code & history
              </span>
              <span>
                <MessageSquare />
                Ask in your own words
              </span>
              <span>
                <BookOpen />
                Follow the evidence
              </span>
            </div>
          </div>
        ) : repo.status !== "ready" ? (
          <div className="welcome indexing">
            <span className="brand-icon">
              {repo.status === "failed" ? (
                <CircleAlert />
              ) : (
                <LoaderCircle className="spin" />
              )}
            </span>
            <h1>
              {repo.status === "failed"
                ? "Indexing stopped"
                : "Building your company context"}
            </h1>
            <p>{repo.error || repo.stage}</p>
            <small>
              Code and documents are read as data. Repository scripts are never
              executed during indexing.
            </small>
            {repo.status === "failed" && (
              <button className="primary" onClick={() => setAdding(true)}>
                Connect a source
              </button>
            )}
          </div>
        ) : mode === "team" ? (
          <TeamBrain
            key={project}
            project={project}
            renderGraph={(g) => <Graph graph={g} />}
          />
        ) : mode === "memory" ? (
          <PersonalBrain
            key={project}
            project={project}
            turns={turns}
            session={session}
            renderGraph={(g) => <Graph graph={g} />}
          />
        ) : (
          <div className="work-area">
            <section className="conversation">
              <div className="page-heading">
                <div>
                  <span className="eyebrow">
                    {mode === "chat"
                      ? "ASK COMPANY BRAIN"
                      : "EXPLORE YOUR CONTEXT"}
                  </span>
                  <h2>
                    {mode === "chat"
                      ? "Understand the why."
                      : "The company graph"}
                  </h2>
                  {mode === "chat" && (
                    <button
                      className="new-chat-inline"
                      disabled={busy}
                      onClick={() =>
                        newChat().catch((e) => setError(e.message))
                      }
                    >
                      New conversation
                    </button>
                  )}
                </div>
                <label className="upload-button">
                  {uploading ? (
                    <LoaderCircle size={16} className="spin" />
                  ) : (
                    <Plus size={16} />
                  )}{" "}
                  Add document
                  <input
                    type="file"
                    accept=".md,.rst,.pdf,.docx"
                    disabled={uploading || busy}
                    onChange={upload}
                  />
                </label>
              </div>
              <IngestionPanel
                key={project}
                project={project}
                refresh={uploadNotice}
                onComplete={loadGraph}
              />
              {uploadNotice && (
                <div className="coverage" role="status">
                  {uploadNotice}
                </div>
              )}
              {repo.warnings?.map((w, i) => (
                <div className="coverage" key={i}>
                  {w}
                </div>
              ))}
              {mode === "graph" ? (
                <>
                  <form
                    className="graph-filter"
                    onSubmit={(e) => {
                      e.preventDefault();
                      loadGraph();
                    }}
                  >
                    <input
                      aria-label="Filter graph"
                      placeholder="Filter files, symbols, or documents…"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    />
                    <button>Filter graph</button>
                  </form>
                  <div className="graph-meta">
                    {graph?.nodes.length || 0} nodes ·{" "}
                    {graph?.edges.length || 0} recorded relationships
                    {graph?.truncated
                      ? " · Bounded slice; filter to explore more"
                      : ""}
                  </div>
                  <p>
                    Double-click a node to explore its callers, changes and
                    supporting evidence.
                  </p>
                  {expansion?.next_offset != null && (
                    <button
                      onClick={() =>
                        expandNode(expansion.root, expansion.next_offset)
                      }
                    >
                      More neighbors
                    </button>
                  )}
                  <Graph key={project} graph={graph} onExpand={expandNode} />
                </>
              ) : (
                <>
                  <div className="thread" aria-live="polite">
                    {!turns.length ? (
                      <div className="empty-chat">
                        <div className="context-mark">
                          <BrainCircuit size={30} />
                        </div>
                        <h3>Start with a question.</h3>
                        <p>
                          Investigate the repository and its decisions.
                          <br />
                          Every published claim includes a checked source.
                        </p>
                        <div className="suggestions">
                          {[
                            "What does this project do, and where should I start?",
                            "How is the code organized?",
                            "What evidence explains the most recent changes?",
                          ].map((q) => (
                            <button key={q} onClick={() => setQuestion(q)}>
                              {q}
                              <ArrowUpRight size={16} />
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : (
                      turns.map((t) => (
                        <article className="turn" key={t.id}>
                          <div className="question">
                            <span className="avatar">YOU</span>
                            <p>{t.question}</p>
                          </div>
                          <div className="answer">
                            <BrainCircuit size={21} />
                            <div>
                              {["running", "queued"].includes(t.status) ? (
                                <p className="pending">
                                  <LoaderCircle size={15} className="spin" />
                                  {t.stage}…
                                </p>
                              ) : t.status === "failed" ? (
                                <p className="failure">{t.error}</p>
                              ) : (
                                <>
                                  <div className="answer-label">
                                    COMPANY BRAIN{" "}
                                    <span>
                                      <Check size={12} /> Source checked
                                    </span>
                                  </div>
                                  {t.claims?.map((c, i) => (
                                    <div className="claim" key={i}>
                                      <p>{c.text}</p>
                                      <div className="citations">
                                        {[
                                          ...new Map(
                                            c.support.map((s) => [
                                              s.evidence_id,
                                              s,
                                            ]),
                                          ).values(),
                                        ].map((s, j) => (
                                          <button
                                            key={j}
                                            onClick={() =>
                                              citation(t.id, s.evidence_id)
                                            }
                                          >
                                            <FileText size={13} />
                                            {s.title
                                              .split("/")
                                              .slice(-2)
                                              .join("/")}
                                            <ArrowUpRight size={12} />
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  ))}
                                  {!t.claims?.length && (
                                    <p>
                                      I don’t have enough verified evidence to
                                      answer this yet.
                                    </p>
                                  )}
                                  {t.limitations?.length > 0 && (
                                    <details className="limitations">
                                      <summary>
                                        Evidence gaps & limitations
                                      </summary>
                                      {t.limitations.map((s, i) => (
                                        <p key={i}>{s}</p>
                                      ))}
                                    </details>
                                  )}
                                  <div className="tools">
                                    {t.tools?.length || 0} tool calls ·{" "}
                                    {t.model} · Source provenance checked
                                    {t.relevance_review &&
                                      " · Citation relevance model-reviewed"}
                                  </div>
                                  <ActionPanel
                                    turn={t}
                                    project={project}
                                    onReviewMemory={() => setMode("memory")}
                                    onEvidence={(id, evidence) =>
                                      citation(id, evidence, "actions")
                                    }
                                  />
                                </>
                              )}
                            </div>
                          </div>
                        </article>
                      ))
                    )}
                  </div>
                  <form className="composer" onSubmit={ask}>
                    <label htmlFor="question" className="sr-only">
                      Ask Company Brain
                    </label>
                    <textarea
                      id="question"
                      placeholder="Ask about the code, a decision, or a bug…"
                      rows={2}
                      value={question}
                      disabled={busy}
                      onChange={(e) => setQuestion(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          ask(e);
                        }
                      }}
                    />
                    <div className="composer-bottom">
                      <span>
                        <span className="scope-pill">
                          <Network size={12} /> Company
                        </span>
                        <small>
                          {busy
                            ? "Investigating…"
                            : "Code · documents · available history"}
                        </small>
                      </span>
                      <button
                        className="submit"
                        aria-label="Send question"
                        disabled={busy || !question.trim()}
                      >
                        <ArrowUp size={18} />
                      </button>
                    </div>
                  </form>
                  <p className="composer-note">
                    Interpretations are model-generated. Inspect the cited
                    sources before acting.
                  </p>
                </>
              )}
            </section>
            <aside className="evidence-panel">
              <div className="inspector-heading">
                <span>
                  <BookOpen size={16} /> Evidence inspector
                </span>
                {selected && (
                  <button
                    aria-label="Close citation"
                    onClick={() => setSelected(null)}
                  >
                    <PanelRightClose size={16} />
                  </button>
                )}
              </div>
              {loadingEvidence ? (
                <div className="evidence-empty">
                  <LoaderCircle className="spin" />
                  Rechecking source…
                </div>
              ) : selected ? (
                <>
                  <div className="evidence-title">
                    <span className="eyebrow">CHECKED SOURCE</span>
                    <h3>{selected.title}</h3>
                    <span className="verified">
                      <Check size={13} />
                      {selected.verification ===
                      "recorded_snapshot_and_native_graph"
                        ? "Recorded historical snapshot"
                        : selected.verification ===
                            "accepted_imported_memory_and_native_graph"
                          ? "Reviewed import · file integrity and graph checked · origin unauthenticated"
                          : selected.verification ===
                              "accepted_team_memory_and_native_graph"
                            ? "Accepted team memory · source and access checked"
                            : selected.verification ===
                                "accepted_private_memory_and_native_graph"
                              ? "Accepted private memory · source and graph checked"
                              : selected.verification ===
                                  "original_file_digest_and_extraction_snapshot"
                                ? "Original file and extracted text verified"
                                : "Original bytes match index"}
                    </span>
                  </div>
                  <div className="source-text">
                    <pre>{selected.text}</pre>
                  </div>
                  <a
                    className="source-link"
                    href={
                      selected.uri.startsWith("https://github.com/")
                        ? selected.uri
                        : undefined
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {selected.uri.startsWith("https://")
                      ? "Open original source"
                      : "Immutable local document"}
                    <ArrowUpRight size={15} />
                  </a>
                  <div className="proof-heading">
                    NATIVE EVIDENCE PATH
                    <small>
                      {selected.graph.edges.length} recorded relationships
                    </small>
                  </div>
                  <Graph graph={selected.graph} compact />
                  <div className="proof-note">
                    These nodes and relationships come from FalkorDB. A source
                    match verifies provenance; it does not prove an
                    interpretation.
                  </div>
                </>
              ) : (
                <div className="evidence-empty">
                  <span className="evidence-icon">
                    <Network size={28} />
                  </span>
                  <h3>Follow a claim to its source.</h3>
                  <p>
                    Click a citation in the conversation to inspect the original
                    text and its recorded graph path.
                  </p>
                  <div className="evidence-guide">
                    <span>
                      <span>01</span>Check the original source
                    </span>
                    <span>
                      <span>02</span>Inspect the graph relationship
                    </span>
                    <span>
                      <span>03</span>Decide what the evidence supports
                    </span>
                  </div>
                </div>
              )}
            </aside>
          </div>
        )}
      </main>
      {adding && (
        <div className="modal-backdrop">
          <form
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Connect a repository"
            onSubmit={connect}
          >
            <button
              className="modal-close"
              type="button"
              aria-label="Close connect dialog"
              onClick={() => setAdding(false)}
            >
              <X size={20} />
            </button>
            <span className="brand-icon">
              <GitBranch />
            </span>
            <h2>Connect a repository</h2>
            <p>
              Bring code, documents, and available GitHub history into one
              evidence-backed workspace.
            </p>
            <label htmlFor="repository-url">Public GitHub repository URL</label>
            <input
              id="repository-url"
              required
              type="url"
              autoFocus
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <label>
              <input
                type="checkbox"
                checked={historyRequired}
                onChange={(e) => setHistoryRequired(e.target.checked)}
              />{" "}
              Require a partial GitHub issue/PR sample; stop indexing if
              acquisition fails
            </label>
            <div className="modal-note">
              Python symbol indexing · Markdown & RST documents
              <br />
              Up to 20 recently updated work items, with complete children for
              each imported item. Older history is not covered.
              <br />
              Public repositories only. GitHub CLI authentication is required.
            </div>
            <button className="primary" disabled={connecting}>
              {connecting ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Plus size={16} />
              )}{" "}
              Connect & index
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);
