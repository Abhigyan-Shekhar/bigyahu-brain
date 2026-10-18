import React from "react";
import EvidenceChain from "./EvidenceChain";
import { evidenceSources } from "./investigationPresentation";
import {
  Network,
  ArrowUpRight,
  Check,
  Activity,
  BrainCircuit,
} from "lucide-react";

export default function InvestigationContext({
  turn,
  project,
  graph,
  onEvidence,
  onGraph,
  onRun,
  onMemory,
  onExpandEvidence,
}) {
  const active = ["running", "queued"].includes(turn?.status);
  const sources = evidenceSources(turn);
  return (
    <div className="investigation-context">
      <span className="eyebrow">
        {active
          ? "FOLLOW THE INVESTIGATION"
          : turn
            ? "CONNECTED EVIDENCE"
            : "YOUR NEXT STEP"}
      </span>
      <h3>
        {active
          ? "The brain is tracing the issue."
          : turn?.status === "failed"
            ? "Investigation stopped."
            : sources.length
              ? "Every finding has a source."
              : "Start with the problem."}
      </h3>
      <p>
        {active
          ? "Tool activity appears in the conversation as evidence is gathered. Open the run to inspect progress."
          : turn?.status === "failed"
            ? "Review the error in the conversation before retrying."
            : sources.length
              ? `${sources.length} citation records support this investigation. Open one to inspect its provenance and graph path.`
              : "Describe what happened and what you expected. The brain connects code, history, and reviewed lessons."}
      </p>
      {active && (
        <button className="context-action" onClick={() => onRun(turn.id)}>
          <Activity size={15} /> View live run <ArrowUpRight size={14} />
        </button>
      )}
      {turn?.status === "complete" && sources[0] && (
        <EvidenceChain
          project={project}
          key={turn.id}
          turn={turn}
          source={sources[0]}
          onExpand={onExpandEvidence}
        />
      )}
      {sources.slice(0, 5).map((s) => (
        <button
          className="context-source"
          key={s.evidence_id}
          onClick={() => onEvidence(turn.id, s.evidence_id)}
        >
          <Check size={14} />
          <span>
            {s.title.split("/").slice(-2).join("/")}
            <small>{s.nodes?.length || 0} cited graph entities</small>
          </span>
          <ArrowUpRight size={13} />
        </button>
      ))}
      {sources.length > 5 && (
        <small>
          All {sources.length} sources are available alongside the findings.
        </small>
      )}
      <div className="context-section-label">CONTINUE WITH CONTEXT</div>
      <button className="context-action" onClick={onGraph}>
        <Network size={16} /> Explore connections <ArrowUpRight size={14} />
      </button>
      {turn?.status === "complete" && (
        <button className="context-action" onClick={() => onRun(turn.id)}>
          <Activity size={16} /> Review investigation <ArrowUpRight size={14} />
        </button>
      )}
      <button className="context-action" onClick={onMemory}>
        <BrainCircuit size={16} /> Review what is remembered{" "}
        <ArrowUpRight size={14} />
      </button>
      <div className="context-storage">
        <strong>Knowledge stored in FalkorDB</strong>
        <p>
          React Flow renders the graph. Select a connection to inspect the
          stored evidence.
        </p>
      </div>
    </div>
  );
}
