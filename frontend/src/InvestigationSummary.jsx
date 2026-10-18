import React from "react";
import { BrainCircuit, Network, ArrowRight, Check } from "lucide-react";
import { conciseText, evidenceSources } from "./investigationPresentation";
export default function InvestigationSummary({ turn, onGraph, onReview }) {
  const sources = evidenceSources(turn);
  if (!turn.claims?.length) return null;
  return (
    <section className="investigation-lead" aria-label="Investigation summary">
      <div className="lead-status">
        <BrainCircuit size={18} />
        <span>Investigation complete</span>
      </div>
      <h3>{conciseText(turn.claims[0].text)}</h3>
      <div className="lead-evidence">
        <span>
          <Check size={13} />
          {sources.length} cited excerpts
        </span>
        <button onClick={onGraph}>
          <Network size={14} />
          Reveal the evidence connection
        </button>
      </div>
      <button className="lead-next" onClick={onReview}>
        Explore the fix workflow <ArrowRight size={16} />
      </button>
    </section>
  );
}
