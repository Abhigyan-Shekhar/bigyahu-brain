import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";

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
  Activity,
} from "lucide-react";
import "@xyflow/react/dist/style.css";
import "./style.css";
import { api, send } from "./api";
const AgentRuns = React.lazy(() => import("./AgentRuns"));
import FixLauncher from "./FixLauncher";
const GraphInspector = React.lazy(() => import("./GraphInspector"));
import ActivityStream from "./ActivityStream";
import { selectionContext, graphQuestion } from "./workspaceContext";
import Graph from "./GraphViewer";
import { clusterGraph } from "./graphPresentation";
import InvestigationContext from "./InvestigationContext";
import InvestigationSummary from "./InvestigationSummary";
import { sourceNeighborhood } from "./investigationPresentation";
import IngestionPanel from "./IngestionPanel";
import PersonalBrain from "./PersonalBrain";
import TeamBrain from "./TeamBrain";

const fragment = location.hash.slice(1);
if (fragment) {
  sessionStorage.setItem("company-brain-token", fragment);
  history.replaceState(null, "", location.pathname);
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
    [historyRequired, setHistoryRequired] = useState(false),
    [expansion, setExpansion] = useState(null),
    [ingesting, setIngesting] = useState(false);
  const [memoryTab, setMemoryTab] = useState("personal");
  const [runId, setRunId] = useState(null);
  const [graphMode, setGraphMode] = useState("overview");
  const [graphScope, setGraphScope] = useState("index");
  const [grouping, setGrouping] = useState("type");
  const [overview, setOverview] = useState(null);
  const [graphRefresh, setGraphRefresh] = useState(0);
  const [clusterFilter, setClusterFilter] = useState({});
  const [graphSelection, setGraphSelection] = useState(null);
  const [graphInspection, setGraphInspection] = useState(null);
  const [graphInspectLoading, setGraphInspectLoading] = useState(false);
  const [graphContext, setGraphContext] = useState(null);
  const [graphOrigin, setGraphOrigin] = useState(null);
  const graphViewport = useRef({});
  const graphPreferences = useRef({});
  const pendingTurn = useRef(null);
  const pendingGraphReveal = useRef(false);
  useEffect(() => {
    if (mode !== "graph" || !pendingGraphReveal.current) return;
    pendingGraphReveal.current = false;
    document
      .querySelector(".graph-workspace .graph")
      ?.scrollIntoView({ block: "start" });
  }, [mode, graphMode, graph]);
  const inspectRequest = useRef(0);
  const evidenceRequest = useRef(0);
  useEffect(() => {
    setRunId(null);
    setGraphSelection(null);
    setGraphInspection(null);
    setGraphContext(null);
    setOverview(null);
    setGraphMode("overview");
    setGraphScope("index");
    setClusterFilter({});
    setGraphOrigin(null);
    ++inspectRequest.current;
    ++evidenceRequest.current;
  }, [project]);
  useEffect(() => {
    if (!project || repos.find((r) => r.id === project)?.status !== "ready")
      return;
    let live = true;
    api(`/repositories/${project}/graph/overview?grouping=${grouping}`)
      .then((r) => {
        if (live) setOverview(r);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [
    project,
    grouping,
    graphRefresh,
    mode,
    repos.find((r) => r.id === project)?.status,
  ]);
  useEffect(() => {
    if (mode !== "chat" || !pendingTurn.current) return;
    const target = document.getElementById(
      `investigation-${pendingTurn.current}`,
    );
    if (target) {
      target.scrollIntoView({ block: "start" });
      target.focus({ preventScroll: true });
      pendingTurn.current = null;
    }
  }, [mode, turns]);
  function returnToInvestigation(run) {
    if (run.session) setSession(run.session);
    pendingTurn.current = run.turn;
    setMode("chat");
  }
  function openRun(id) {
    setRunId(id);
    setGraphSelection(null);
    setSelected(null);
    setMode("runs");
  }
  function explainSelection(selection) {
    setGraphContext(
      selectionContext(selection, graph?.revision || selected?.revision),
    );
    setQuestion(
      (q) =>
        q ||
        "Explain this selected graph context. Check its sources and distinguish facts from interpretations.",
    );
    setMode("chat");
    requestAnimationFrame(() => document.getElementById("question")?.focus());
  }
  async function inspectGraph(selection) {
    if (selection.node?.labels?.includes("Cluster")) {
      const key = selection.node.clusterKey;
      const filters =
        grouping === "type"
          ? { kind: key, context: true }
          : { folder: key, context: true };
      setClusterFilter(filters);
      setFilter("");
      setGraphMode("explore");
      setGraphSelection(null);
      await loadGraph("", 0, filters);
      pendingGraphReveal.current = true;
      return;
    }
    const request = ++inspectRequest.current;
    setGraphSelection(selection);
    setGraphInspection(null);
    setGraphInspectLoading(false);
    if (selection.kind !== "node") return;
    if (selection.node.id.startsWith("memory:")) {
      setGraphInspection({
        source_notice:
          "Native memory topology from the checked evidence view. Use Memory to inspect its authorized source and review state.",
      });
      return;
    }
    setGraphInspectLoading(true);
    try {
      const detail = await api(
        `/repositories/${project}/graph/node?uid=${encodeURIComponent(selection.node.id)}`,
      );
      if (request === inspectRequest.current) setGraphInspection(detail);
    } catch (e) {
      if (request === inspectRequest.current)
        setGraphInspection({ error: e.message });
    } finally {
      if (request === inspectRequest.current) setGraphInspectLoading(false);
    }
  }
  function inspectGraphUid(uid) {
    const node = overviewGraph.nodes.find((n) => n.id === uid) ||
      graph?.nodes?.find((n) => n.id === uid) ||
      selected?.graph?.nodes?.find((n) => n.id === uid) || {
        id: uid,
        label: uid,
        labels: [],
      };
    inspectGraph({ kind: "node", node });
  }
  function exploreEvidence(evidence, turn = null) {
    ++graphRequest.current;
    setGraph({
      ...evidence.graph,
      revision: evidence.revision,
      counts: graph?.counts,
      entity_counts: graph?.entity_counts,
    });
    setGraphScope("evidence");
    setGraphMode("focused");
    setGraphOrigin(turn ? { session, turn } : graphOrigin);
    setMode("graph");
    setGraphSelection(null);
    setExpansion(null);
    pendingGraphReveal.current = true;
  }
  async function openMemorySource(source) {
    if (source.kind === "lesson") {
      openRun(JSON.parse(source.text).action);
      return;
    }
    if (source.session && source.turn) {
      if (!sessions.some((s) => s.id === source.session)) {
        setError("Originating conversation is not in the current repository.");
        return;
      }
      returnToInvestigation({ session: source.session, turn: source.turn });
    }
  }
  const overviewGraph = clusterGraph(overview, grouping);
  const repo = repos.find((r) => r.id === project),
    busy = turns.some((t) => ["running", "queued"].includes(t.status));
  const entityCounts = graph?.entity_counts;
  const countEntity = (kind) =>
    entityCounts?.find((c) => c.kind === kind)?.count ?? 0;
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
    setSessions([]);
    setSession(null);
    setSelected(null);
    setGraph(null);
    if (!project) return;
    let active = true;
    api(`/repositories/${project}/sessions`)
      .then((s) => {
        if (!active) return;
        setSessions(s);
        setSession(s.at(-1)?.id || null);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
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
      setGraph({ ...graph, ...extra, nodes, edges });
      setExpansion(extra);
    } catch (e) {
      if (request === graphRequest.current && project === activeProject.current)
        setError(e.message);
    }
  }
  async function focusNode(uid) {
    const request = ++graphRequest.current;
    setMode("graph");
    setGraphMode("focused");
    setGraphScope("neighborhood");
    setFilter("");
    try {
      const next = await api(
        `/repositories/${project}/graph/neighbors?uid=${encodeURIComponent(uid)}`,
      );
      if (
        request === graphRequest.current &&
        project === activeProject.current
      ) {
        setGraph((previous) => ({
          ...next,
          counts: previous?.counts,
          entity_counts: previous?.entity_counts,
          revision: next.revision || previous?.revision,
        }));
        setExpansion(next);
      }
    } catch (e) {
      setError(e.message);
    }
  }
  async function loadGraph(q = filter, offset = 0, filters = clusterFilter) {
    const request = ++graphRequest.current;
    try {
      setExpansion(null);
      const next = await api(
        `/repositories/${project}/graph?query=${encodeURIComponent(q)}&offset=${offset}&kind=${encodeURIComponent(filters.kind || "")}&folder=${encodeURIComponent(filters.folder || "")}&context_neighbors=${!!filters.context}`,
      );
      if (
        request === graphRequest.current &&
        project === activeProject.current
      ) {
        setGraph(next);
        setGraphScope("index");
      }
    } catch (e) {
      if (request === graphRequest.current && project === activeProject.current)
        setError(e.message);
    }
  }
  useEffect(() => {
    if (repo?.status === "ready") loadGraph("", 0, {});
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
      setMode("chat");
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
    setGraphContext(null);
    setMode("chat");
    return chat.id;
  }
  async function ask(e) {
    e.preventDefault();
    if (!question.trim() || busy || ingesting) return;
    setError("");
    try {
      const id = session || (await newChat());
      const submitted = graphQuestion(question, graphContext);
      const turn = await send(`/sessions/${id}/turns`, { question: submitted });
      setGraphContext(null);
      setTurns((t) => [...t, turn]);
      setQuestion("");
    } catch (e) {
      setError(e.message);
    }
  }
  async function reviewTurnFix(turn) {
    const scope = project;
    try {
      const actions = await api(`/turns/${turn.id}/actions`);
      if (scope !== activeProject.current) return;
      if (actions.length) openRun(actions.at(-1).id);
      else
        document
          .getElementById(`fix-${turn.id}`)
          ?.scrollIntoView({ block: "center" });
    } catch (e) {
      if (scope === activeProject.current) setError(e.message);
    }
  }
  async function revealTurnEvidence(turn) {
    const first = turn.claims?.[0]?.support?.[0];
    if (!first) return;
    const scope = project;
    try {
      const proof = await api(
        `/turns/${turn.id}/evidence/${first.evidence_id}`,
      );
      if (scope !== activeProject.current) return;
      let connection = proof.graph;
      const file = proof.graph.nodes.find((n) => n.labels?.includes("File"));
      if (file) {
        try {
          const adjacent = await api(
            `/repositories/${scope}/graph/neighbors?uid=${encodeURIComponent(file.id)}`,
          );
          connection = sourceNeighborhood(
            proof,
            adjacent,
            turn.claims.map((c) => c.text).join("\n"),
          );
        } catch {
          /* The original checked citation remains usable without added context. */
        }
      }
      if (scope !== activeProject.current) return;
      setSelected(null);
      exploreEvidence({ ...proof, graph: connection }, turn.id);
    } catch (e) {
      setError(e.message);
    }
  }
  async function citation(turn, id, kind = "turns", origin = null) {
    setGraphOrigin(
      origin || (kind === "turns" ? { session, turn } : graphOrigin),
    );
    setGraphSelection(null);
    const request = ++evidenceRequest.current;
    setLoadingEvidence(true);
    setSelected(null);
    try {
      const proof = await api(`/${kind}/${turn}/evidence/${id}`);
      if (request !== evidenceRequest.current) return;
      setSelected(proof);
      if (matchMedia("(max-width:680px)").matches)
        requestAnimationFrame(() =>
          document
            .querySelector(".evidence-panel")
            ?.scrollIntoView({ behavior: "smooth", block: "start" }),
        );
    } catch (e) {
      if (request === evidenceRequest.current) setError(e.message);
    } finally {
      if (request === evidenceRequest.current) setLoadingEvidence(false);
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
      setIngesting(true);
      await loadGraph();
      setGraphRefresh((n) => n + 1);
      setError("");
      setUploadNotice(
        `${result.filename}: ${result.sections} source sections saved.`,
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
          <MessageSquare size={17} /> Ask Brain
        </button>
        <button
          className={"nav " + (mode === "graph" ? "active" : "")}
          onClick={() => setMode("graph")}
        >
          <Network size={17} /> Explore Graph
          {overview && (
            <span className="count" title="Total indexed entities">
              {overview.total_nodes.toLocaleString()}
            </span>
          )}
        </button>
        <button
          className={"nav " + (mode === "runs" ? "active" : "")}
          onClick={() => {
            setGraphSelection(null);
            setSelected(null);
            setMode("runs");
          }}
        >
          <Activity size={17} /> Agent Runs
        </button>
        <button
          className={"nav " + (mode === "memory" ? "active" : "")}
          onClick={() => setMode("memory")}
        >
          <BrainCircuit size={17} /> Memory
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
                setMode("chat");
                setSelected(null);
              }}
            >
              <MessageSquare size={14} />
              {s.title}
            </button>
          ))}
        </div>
        <details className="workspace-settings">
          <summary>Workspace settings</summary>
          <dl>
            <dt>Connected model</dt>
            <dd>{model || "Loading…"}</dd>
            <dt>Workspace access</dt>
            <dd>Local operator</dd>
          </dl>
          <p>
            Model and workspace configuration are set when starting the local
            application.
          </p>
        </details>
        <div className="graph-stack">
          <Network size={16} />
          <span>
            <strong>FalkorDB</strong>
            <small>Graph storage · React Flow rendering</small>
          </span>
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
            <span className="dot ready" /> Graphify → FalkorDB → cited answers
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
              Investigate your code.
              <br />
              Fix with context.
            </h1>
            <p>
              Connect code, history, documents and reviewed team knowledge.
              Investigate an issue, inspect its evidence, and approve an
              isolated fix with an explicit test report.
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
                Investigate with evidence
              </span>
              <span>
                <BookOpen />
                Review isolated fixes
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
        ) : mode === "memory" ? (
          <div className="memory-workspace">
            <nav className="workspace-tabs" aria-label="Memory scopes">
              <button
                aria-pressed={memoryTab === "personal"}
                onClick={() => setMemoryTab("personal")}
              >
                Personal
              </button>
              <button
                aria-pressed={memoryTab === "team"}
                onClick={() => setMemoryTab("team")}
              >
                Team & management
              </button>
            </nav>
            <div hidden={memoryTab !== "personal"}>
              <PersonalBrain
                key={project}
                project={project}
                turns={turns}
                session={session}
                onOpenSource={openMemorySource}
                renderGraph={(g) => <Graph graph={g} />}
              />
            </div>
            <div hidden={memoryTab !== "team"}>
              <TeamBrain
                key={project}
                project={project}
                renderGraph={(g) => <Graph graph={g} />}
              />
            </div>
          </div>
        ) : (
          <div
            className={
              "work-area " +
              (mode === "graph"
                ? "graph-workspace"
                : mode === "runs"
                  ? "runs-area"
                  : "") +
              (graphSelection || selected ? " inspector-open" : "")
            }
          >
            <section
              className={
                "conversation " +
                (turns.length && mode === "chat" ? "has-turns" : "")
              }
            >
              <div className="page-heading">
                <div>
                  <span className="eyebrow">
                    {mode === "chat"
                      ? "ASK COMPANY BRAIN"
                      : "EXPLORE YOUR CONTEXT"}
                  </span>
                  <h2>
                    {mode === "chat"
                      ? "From an issue to an evidence-backed fix."
                      : mode === "runs"
                        ? "Agent runs"
                        : "Explore your knowledge graph"}
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
                    disabled={uploading || busy || ingesting}
                    onChange={upload}
                  />
                </label>
              </div>
              {uploadNotice && (
                <div className="coverage" role="status">
                  {uploadNotice}
                </div>
              )}
              <details className="coverage-details">
                <summary>
                  Knowledge coverage · indexed snapshot ·{" "}
                  {repo.github_coverage?.mode === "not_requested"
                    ? "GitHub history not requested"
                    : repo.github_coverage?.imported != null
                      ? "GitHub history partial sample"
                      : "GitHub history unverified"}
                </summary>
                <dl className="coverage-summary">
                  <div>
                    <dt>Repository code snapshot</dt>
                    <dd>
                      {repo.revision
                        ? `Revision ${repo.revision.slice(0, 8)} · manual refresh`
                        : "Revision unavailable"}
                    </dd>
                  </div>
                  <div>
                    <dt>GitHub history</dt>
                    <dd>
                      {repo.github_coverage?.mode === "not_requested"
                        ? "Not requested"
                        : repo.github_coverage?.imported != null
                          ? `${repo.github_coverage.imported} complete work items in a partial selected sample · older history not covered`
                          : "Coverage unavailable or unverified"}
                    </dd>
                  </div>
                  <div>
                    <dt>Document sections</dt>
                    <dd>
                      {entityCounts
                        ? `${countEntity("RepositorySection")} repository · ${countEntity("UploadedSection")} uploaded`
                        : "Counts unavailable"}
                    </dd>
                  </div>
                  <div>
                    <dt>Extracted entities</dt>
                    <dd>
                      {entityCounts
                        ? `${countEntity("CodeEntity")} structural code entities · ${countEntity("ExtractedConcept")} advisory concepts`
                        : "Counts unavailable"}
                    </dd>
                  </div>
                  <div>
                    <dt>Reviewed memory scopes</dt>
                    <dd>
                      Accepted Personal Brain and authorized Team Brain records
                      in this repository; unreviewed records excluded from agent
                      retrieval.
                    </dd>
                  </div>
                </dl>
                {repo.graphify && (
                  <p>
                    Graphify: {repo.graphify.files} files ·{" "}
                    {repo.graphify.nodes} extracted nodes ·{" "}
                    {repo.graphify.relationships} relationships
                  </p>
                )}
                {repo.warnings?.map((w, i) => (
                  <div className="coverage" key={i}>
                    {w}
                  </div>
                ))}
              </details>
              {mode === "graph" ? (
                <>
                  <nav className="workspace-tabs" aria-label="Graph views">
                    <button
                      aria-pressed={graphMode === "overview"}
                      onClick={() => setGraphMode("overview")}
                    >
                      Entire graph
                    </button>
                    <button
                      aria-pressed={graphMode !== "overview"}
                      onClick={() =>
                        setGraphMode(
                          graphScope !== "index" ? "focused" : "explore",
                        )
                      }
                    >
                      {graphScope !== "index"
                        ? "Evidence graph"
                        : "Explore loaded entities"}
                    </button>
                    {graphOrigin && (
                      <button
                        onClick={() => returnToInvestigation(graphOrigin)}
                      >
                        Return to investigation
                      </button>
                    )}
                  </nav>
                  {graphMode === "overview" && (
                    <>
                      <div className="graph-summary">
                        <label>
                          Group entire index by{" "}
                          <select
                            aria-label="Group entire index by"
                            value={grouping}
                            onChange={(e) => setGrouping(e.target.value)}
                          >
                            <option value="type">Entity type</option>
                            <option value="folder">Top-level folder</option>
                          </select>
                        </label>
                        <p>
                          {overview?.total_nodes ?? "Loading"} indexed entities
                          · {overview?.groups.length || 0} knowledge clusters ·
                          Select a cluster to explore.
                        </p>
                        {overview?.relationships_truncated && (
                          <p className="coverage">
                            Showing the 200 largest relationship groups. Drill
                            into a cluster for detailed connections.
                          </p>
                        )}
                        {overview?.truncated && (
                          <p className="coverage">
                            First {overview.group_limit} groups shown. Search
                            and filters remain available across the index.
                          </p>
                        )}
                      </div>
                    </>
                  )}
                  {graphMode === "focused" && (
                    <p className="coverage">
                      Focused neighborhood / checked evidence slice. Expand
                      neighbors for another hop.{" "}
                      <button onClick={() => setGraphMode("overview")}>
                        View entire graph
                      </button>
                    </p>
                  )}
                  <details
                    className="graph-query-tools"
                    open={graphMode === "overview"}
                  >
                    <summary>Search index & loaded context</summary>
                    <form
                      className="graph-filter"
                      onSubmit={(e) => {
                        e.preventDefault();
                        setGraphMode("explore");
                        loadGraph();
                      }}
                    >
                      <input
                        aria-label="Filter graph"
                        placeholder="Filter files, symbols, or documents…"
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                      />
                      <button>
                        {clusterFilter.kind || clusterFilter.folder
                          ? "Search within cluster"
                          : "Search index"}
                      </button>
                      {(clusterFilter.kind || clusterFilter.folder) && (
                        <button
                          type="button"
                          onClick={() => {
                            setClusterFilter({});
                            setGraphMode("explore");
                            loadGraph(filter, 0, {});
                          }}
                        >
                          Search entire index
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setFilter("");
                          setClusterFilter({});
                          setGraphMode("explore");
                          loadGraph("", 0, {});
                        }}
                      >
                        Clear filters
                      </button>
                    </form>
                    <div
                      className="graph-meta"
                      hidden={graphMode === "overview"}
                    >
                      {graphMode === "overview"
                        ? "Cluster overview; detailed slice retained: "
                        : "Loaded slice: "}
                      {graph?.nodes.length || 0} nodes ·{" "}
                      {graph?.edges.length || 0} recorded relationships
                      {graph?.truncated
                        ? " · Bounded slice; filter to explore more"
                        : ""}
                    </div>
                    {graph?.paging_bound_reached && (
                      <p className="coverage">
                        Page limit reached. Narrow the search or cluster to
                        discover additional indexed entities.
                      </p>
                    )}
                    {graphMode !== "overview" && (
                      <p className="graph-instruction">
                        Select a node for its inspector; double-click or expand
                        to load another hop. At low zoom, labels are hidden to
                        keep the canvas readable.
                      </p>
                    )}
                    {expansion?.next_offset != null && (
                      <button
                        onClick={() =>
                          expandNode(expansion.root, expansion.next_offset)
                        }
                      >
                        More neighbors
                      </button>
                    )}
                    {graphMode !== "overview" &&
                      graphScope === "index" &&
                      graph?.offset != null && (
                        <div className="graph-pages">
                          <button
                            disabled={!graph?.offset}
                            onClick={() =>
                              loadGraph(filter, Math.max(0, graph.offset - 100))
                            }
                          >
                            Previous nodes
                          </button>
                          <button
                            disabled={graph?.next_offset == null}
                            onClick={() => loadGraph(filter, graph.next_offset)}
                          >
                            Next nodes
                          </button>
                        </div>
                      )}
                    {(clusterFilter.kind || clusterFilter.folder) &&
                      graphMode !== "overview" && (
                        <p className="coverage">
                          Active cluster:{" "}
                          {clusterFilter.kind || clusterFilter.folder}
                          <label>
                            <input
                              type="checkbox"
                              checked={!!clusterFilter.context}
                              onChange={(e) => {
                                const next = {
                                  ...clusterFilter,
                                  context: e.target.checked,
                                };
                                setClusterFilter(next);
                                loadGraph(filter, 0, next);
                              }}
                            />
                            Show cross-cluster relationships
                          </label>
                          {graph?.context_count > 0 && (
                            <span>
                              {" "}
                              · {graph.context_count} directly connected context
                              entities (up to 50).{" "}
                            </span>
                          )}
                          {graph?.context_truncated && (
                            <span>
                              {" "}
                              More neighbors available; expand a node to
                              explore.{" "}
                            </span>
                          )}
                          <button
                            onClick={() =>
                              explainSelection({
                                kind: "cluster",
                                grouping: clusterFilter.kind
                                  ? "type"
                                  : "folder",
                                key: clusterFilter.kind || clusterFilter.folder,
                              })
                            }
                          >
                            Explain cluster in chat
                          </button>
                        </p>
                      )}
                  </details>
                  <Graph
                    key={`${project}:${graphMode}:${JSON.stringify(clusterFilter)}:${graph?.offset || 0}`}
                    viewKey={`${project}:${graphMode}:${JSON.stringify(clusterFilter)}:${graph?.offset || 0}`}
                    focused={graphMode === "focused"}
                    focusId={graph?.root || graphSelection?.node?.id}
                    viewportCache={graphViewport}
                    uiCache={graphPreferences}
                    graph={graphMode === "overview" ? overviewGraph : graph}
                    onExpand={graphMode === "overview" ? undefined : expandNode}
                    onInspect={inspectGraph}
                    onExplain={explainSelection}
                  />
                  <p className="graph-caption">
                    {graphMode === "overview"
                      ? "Overview arrows aggregate stored FalkorDB relationships; internal links stay within clusters. Open a cluster to explore its entities."
                      : "Directed links come from FalkorDB. The focused view uses loaded connections; expand a node to fetch more, or show all loaded entities. A graph connection is navigation context, not proof of causality."}
                  </p>
                </>
              ) : mode === "runs" ? (
                <React.Suspense
                  fallback={<p role="status">Loading Agent Runs…</p>}
                >
                  <AgentRuns
                    project={project}
                    selected={runId}
                    onSelect={(id) => {
                      setRunId(id);
                      setSelected(null);
                      setGraphSelection(null);
                      document
                        .querySelector(".runs-area .conversation")
                        ?.scrollTo({ top: 0 });
                    }}
                    onInvestigation={returnToInvestigation}
                    onEvidence={(id, evidence, kind, origin) =>
                      citation(id, evidence, kind, origin)
                    }
                    onReviewMemory={() => {
                      setMemoryTab("personal");
                      setMode("memory");
                    }}
                  />
                </React.Suspense>
              ) : (
                <>
                  <div className="thread" aria-live="polite">
                    {!turns.length ? (
                      <div className="empty-chat">
                        <div className="context-mark">
                          <BrainCircuit size={30} />
                        </div>
                        <h3>Start an investigation.</h3>
                        <p>
                          Trace an issue, inspect the evidence, then review a
                          proposed fix.
                          <br />
                          Every published claim includes a checked source.
                        </p>
                        <div className="suggestions">
                          {[
                            [
                              "Investigate a bug",
                              "Investigate this bug: [describe the observed behavior and expected result]. Find the relevant code, history and reviewed lessons; cite evidence and identify coverage gaps.",
                            ],
                            [
                              "Explain a decision",
                              "Explain this engineering decision: [describe the behavior or decision]. Trace its code, documents, history and reviewed knowledge; distinguish requirements from advisory lessons.",
                            ],
                            [
                              "Plan a change",
                              "Investigate this change: [describe the intended outcome]. Identify affected files, preservation requirements and test coverage so I can use Plan a change to review a cited fix before isolated execution.",
                            ],
                          ].map(([label, q]) => (
                            <button
                              key={label}
                              onClick={() => {
                                setQuestion(q);
                                document.getElementById("question")?.focus();
                              }}
                            >
                              {label}
                              <ArrowUpRight size={16} />
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : (
                      turns.map((t) => (
                        <article
                          className="turn workflow-target"
                          key={t.id}
                          id={`investigation-${t.id}`}
                          tabIndex={-1}
                        >
                          <div className="question">
                            <span className="avatar">YOU</span>
                            <p>{t.question}</p>
                          </div>
                          <div className="answer">
                            <BrainCircuit size={21} />
                            <div>
                              {["running", "queued"].includes(t.status) ? (
                                <>
                                  <ActivityStream turn={t} />
                                  <button onClick={() => openRun(t.id)}>
                                    View live investigation
                                  </button>
                                </>
                              ) : t.status === "failed" ? (
                                <p className="failure">{t.error}</p>
                              ) : (
                                <>
                                  <div className="answer-label">
                                    COMPANY BRAIN{" "}
                                    <button onClick={() => openRun(t.id)}>
                                      Open investigation run
                                    </button>
                                    {t.claims?.length > 0 && (
                                      <span>
                                        <Check size={12} /> Source checked
                                      </span>
                                    )}
                                    {t.claims?.length > 0 && (
                                      <button
                                        className="fix-jump"
                                        onClick={() =>
                                          document
                                            .getElementById(`fix-${t.id}`)
                                            ?.scrollIntoView({ block: "start" })
                                        }
                                      >
                                        Review fix workflow ↓
                                      </button>
                                    )}
                                  </div>
                                  <InvestigationSummary
                                    turn={t}
                                    onGraph={() => revealTurnEvidence(t)}
                                    onReview={() => reviewTurnFix(t)}
                                  />
                                  {t.claims?.map((c, i) => (
                                    <details
                                      className={
                                        "claim " +
                                        (i === 0 ? "primary-diagnosis" : "")
                                      }
                                      key={`${t.id}:${i}`}
                                    >
                                      <summary>
                                        {i === 0
                                          ? "Detailed diagnosis & source paths"
                                          : `Finding ${i + 1} · ${c.text.slice(0, 90)}${c.text.length > 90 ? "…" : ""}`}
                                      </summary>
                                      {i === 0 && (
                                        <span className="diagnosis-label">
                                          WHAT THE BRAIN FOUND
                                        </span>
                                      )}
                                      <p>{c.text}</p>
                                      <button
                                        className="evidence-graph-link"
                                        onClick={async () => {
                                          try {
                                            const scope = project;
                                            const proof = await api(
                                              `/turns/${t.id}/evidence/${c.support[0].evidence_id}`,
                                            );
                                            if (scope !== activeProject.current)
                                              return;
                                            setSelected(proof);
                                            exploreEvidence(proof, t.id);
                                          } catch (e) {
                                            setError(e.message);
                                          }
                                        }}
                                      >
                                        Explore evidence graph
                                      </button>
                                      <div className="quoted-support">
                                        {c.support.map((support, j) => (
                                          <details key={j}>
                                            <summary>
                                              Evidence {j + 1} ·{" "}
                                              {support.nodes?.length || 0} graph
                                              nodes
                                            </summary>
                                            <blockquote>
                                              {support.quote}
                                            </blockquote>
                                            {support.nodes?.map((n) => (
                                              <button
                                                className="node-reference"
                                                key={n.id}
                                                title={n.id}
                                                onClick={() => {
                                                  focusNode(n.id);
                                                }}
                                              >
                                                <Network size={12} />
                                                {n.label}
                                                <small>{n.id}</small>
                                              </button>
                                            ))}
                                          </details>
                                        ))}
                                      </div>
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
                                    </details>
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
                                  <details className="investigation-audit">
                                    <summary>
                                      Investigation details & source review
                                    </summary>
                                    <div className="tools">
                                      {t.tools?.length || 0} tool calls ·{" "}
                                      {t.model} · Source provenance checked
                                      {t.relevance_review &&
                                        " · Citation relevance model-reviewed"}
                                    </div>
                                  </details>
                                  <FixLauncher turn={t} onRun={openRun} />
                                </>
                              )}
                            </div>
                          </div>
                        </article>
                      ))
                    )}
                  </div>
                  {graphContext && (
                    <div className="context-chip">
                      <strong>Graph context attached</strong>
                      <span>
                        {graphContext.selection.kind} ·{" "}
                        {graphContext.selection.label ||
                          graphContext.selection.key ||
                          graphContext.selection.edge?.relation ||
                          "recorded path"}
                      </span>
                      <button onClick={() => setMode("graph")}>
                        Return to graph
                      </button>
                      <button onClick={() => setGraphContext(null)}>
                        Clear context
                      </button>
                    </div>
                  )}
                  <form className="composer" onSubmit={ask}>
                    <label htmlFor="question" className="sr-only">
                      Ask Company Brain
                    </label>
                    <textarea
                      id="question"
                      placeholder="Ask a question, explore a past approach, or describe a change…"
                      rows={1}
                      value={question}
                      disabled={busy || ingesting}
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
                          {ingesting
                            ? "Building document graph…"
                            : busy
                              ? "Investigating…"
                              : "Code · documents · available history"}
                        </small>
                      </span>
                      <button
                        className="submit"
                        aria-label="Send question"
                        disabled={busy || ingesting || !question.trim()}
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
                  <Network size={16} />{" "}
                  {graphSelection
                    ? "Context inspector"
                    : selected
                      ? "Cited evidence"
                      : busy
                        ? "Live investigation"
                        : mode === "runs"
                          ? "Run context"
                          : "Investigation context"}
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
              {graphSelection ? (
                <React.Suspense
                  fallback={<p role="status">Loading entity inspector…</p>}
                >
                  <GraphInspector
                    selection={graphSelection}
                    linkedEvidence={selected}
                    detail={graphInspection}
                    loading={graphInspectLoading}
                    graph={
                      mode === "graph" && graphMode === "overview"
                        ? overviewGraph
                        : graph
                    }
                    onClose={() => setGraphSelection(null)}
                    onNode={inspectGraphUid}
                    onExpand={expandNode}
                    onFocus={focusNode}
                    onSource={(proof) => {
                      setSelected(proof);
                      setGraphSelection(null);
                    }}
                    onExplain={explainSelection}
                  />
                </React.Suspense>
              ) : loadingEvidence ? (
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
                  <div
                    className={`source-text ${selected.kind === "code" ? "code-source" : ""}`}
                  >
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
                  <ol
                    className="evidence-paths"
                    aria-label="Recorded evidence links"
                  >
                    {selected.graph.edges.slice(0, 8).map((edge, i) => {
                      const label = (id) =>
                        selected.graph.nodes.find((n) => n.id === id)?.label ||
                        id;
                      return (
                        <li key={i}>
                          <button onClick={() => focusNode(edge.source)}>
                            {label(edge.source)}
                          </button>
                          <span>→ {edge.relation} →</span>
                          <button onClick={() => focusNode(edge.target)}>
                            {label(edge.target)}
                          </button>
                        </li>
                      );
                    })}
                  </ol>
                  {selected.graph.edges.length > 8 && (
                    <p className="proof-note">
                      Showing 8 of {selected.graph.edges.length} links. Select a
                      node to explore its neighbors.
                    </p>
                  )}
                  <button
                    className="primary"
                    onClick={() => exploreEvidence(selected)}
                  >
                    Explore focused evidence graph
                  </button>
                  <Graph
                    graph={selected.graph}
                    compact
                    onInspect={inspectGraph}
                  />
                  <div className="proof-note">
                    These nodes and relationships come from FalkorDB. A source
                    match verifies provenance; it does not prove an
                    interpretation.
                  </div>
                </>
              ) : mode === "chat" ? (
                <InvestigationContext
                  project={project}
                  turn={turns.at(-1)}
                  graph={graph}
                  onEvidence={(turn, id) => citation(turn, id)}
                  onGraph={() => setMode("graph")}
                  onRun={openRun}
                  onMemory={() => {
                    setMemoryTab("personal");
                    setMode("memory");
                  }}
                  onExpandEvidence={(proof, turnId, connection) => {
                    setSelected(null);
                    exploreEvidence(
                      { ...proof, graph: connection || proof.graph },
                      turnId,
                    );
                  }}
                />
              ) : (
                <div className="knowledge-overview">
                  <div className="knowledge-heading">
                    <strong>Company knowledge graph</strong>
                    <button
                      onClick={() =>
                        setMode(mode === "graph" ? "chat" : "graph")
                      }
                    >
                      {mode === "graph" ? "Return to chat" : "Explore graph"}
                      <ArrowUpRight size={14} />
                    </button>
                  </div>
                  <p>Code, documents, and recorded history in FalkorDB.</p>
                  <div className="knowledge-counts">
                    {graph?.entity_counts
                      ?.filter((c) =>
                        [
                          "File",
                          "Symbol",
                          "CodeEntity",
                          "RepositorySection",
                          "UploadedSection",
                          "ExtractedConcept",
                          "Source",
                        ].includes(c.kind),
                      )
                      .map((c) => (
                        <span key={c.kind}>
                          <strong>{c.count}</strong>
                          {
                            {
                              File: "Files",
                              Symbol: "Symbols",
                              CodeEntity: "Code entities",
                              RepositorySection: "Repository sections",
                              UploadedSection: "Uploaded sections",
                              ExtractedConcept: "Extracted concepts",
                              Source: "Evidence sources",
                            }[c.kind]
                          }
                        </span>
                      ))}
                  </div>
                  <Graph
                    key={mode}
                    graph={graph}
                    compact
                    onExpand={expandNode}
                  />
                  <p className="graph-caption">
                    Graph preview · {graph?.nodes.length || 0} nodes in this
                    page
                    {graph?.truncated ? " · paged view" : ""}. Open the explorer
                    to search and page through the graph.
                  </p>
                  <div className="source-tip">
                    <FileText size={18} />
                    <div>
                      <strong>Add your company context</strong>
                      <p>
                        Upload design notes, file instructions, and previous
                        approaches with Add document. Graphify extracts
                        relationships automatically.
                      </p>
                    </div>
                  </div>
                </div>
              )}
              <div hidden={!!selected || !!graphSelection || mode !== "chat"}>
                <IngestionPanel
                  key={project}
                  project={project}
                  refresh={uploadNotice}
                  onComplete={() => {
                    setGraphRefresh((n) => n + 1);
                    loadGraph("");
                  }}
                  onStatus={setIngesting}
                />
              </div>
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
              Graphify code extraction · Python call analysis · FalkorDB storage
              <br />
              Up to 20 recently updated work items, with complete children for
              each imported item. Older history is not covered.
              <br />
              Public repositories only. Graphify supports up to 500 code files /
              10 MB per repository; unsupported languages are outside extraction
              coverage.
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
