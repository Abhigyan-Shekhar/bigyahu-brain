import React, { useEffect, useState } from "react";
import { Network, ArrowUpRight, LoaderCircle } from "lucide-react";
import { api } from "./api";
import { sourceNeighborhood } from "./investigationPresentation";
export default function EvidenceChain({ turn, source, project, onExpand }) {
  const [proof, setProof] = useState(null),
    [error, setError] = useState("");
  const [connection, setConnection] = useState(null);
  useEffect(() => {
    let live = true;
    setProof(null);
    setConnection(null);
    setError("");
    if (source)
      (async () => {
        try {
          const checked = await api(
            `/turns/${turn.id}/evidence/${source.evidence_id}`,
          );
          let graph = checked.graph;
          const file = graph.nodes.find((n) => n.labels?.includes("File"));
          if (file) {
            try {
              const adjacent = await api(
                `/repositories/${project}/graph/neighbors?uid=${encodeURIComponent(file.id)}`,
              );
              graph = sourceNeighborhood(
                checked,
                adjacent,
                (turn.claims || []).map((c) => c.text).join("\n"),
              );
            } catch {
              /* Keep the independently checked source if context is unavailable. */
            }
          }
          if (live) {
            setProof(checked);
            setConnection(graph);
          }
        } catch (e) {
          if (live) setError(e.message);
        }
      })();
    return () => {
      live = false;
    };
  }, [project, turn.id, source?.evidence_id]);
  if (!source) return null;
  const edges = connection?.edges || [];
  const label = (id) => connection.nodes.find((n) => n.id === id)?.label || id;
  return (
    <section
      className="evidence-chain"
      aria-label="Checked evidence connections"
    >
      <div className="context-section-label">RELEVANT CONNECTION</div>
      <strong className="chain-source-title">{source.title}</strong>
      {!proof && !error && (
        <p role="status">
          <LoaderCircle size={14} className="spin" /> Rechecking source
          connections…
        </p>
      )}
      {error && (
        <p className="failure" role="alert">
          {error}
        </p>
      )}
      {proof && (
        <>
          {edges.slice(0, 3).map((e, i) => (
            <div className="chain-link" key={i}>
              <span>{label(e.source)}</span>
              <small>↓ {e.relation}</small>
              <span>{label(e.target)}</span>
            </div>
          ))}
          {!edges.length && (
            <p>This source has no stored relationships in its checked view.</p>
          )}
          {edges.length > 3 && (
            <small>{edges.length - 3} more connections in the explorer.</small>
          )}
          <button
            className="context-action"
            onClick={() => onExpand(proof, turn.id, connection)}
          >
            <Network size={15} />
            Expand evidence graph
            <ArrowUpRight size={14} />
          </button>
          <small>
            Stored FalkorDB links, shown in their recorded direction.{" "}
            {connection?.context_notice &&
              "Current indexed context; citation inspected separately."}
          </small>
        </>
      )}
    </section>
  );
}
