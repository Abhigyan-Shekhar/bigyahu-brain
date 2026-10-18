import React, { useState } from "react";
import { ShieldAlert, FileText, ArrowRight, MapPin } from "lucide-react";
import ProblemLocation from "./ProblemLocation";

const rank = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
export default function FindingAlerts({ turn, onEvidence, onPlan }) {
  const [selection, setSelection] = useState({ turn: turn.id, value: "all" });
  if (turn.status !== "complete") return null;
  const findings = (turn.claims || [])
    .filter((claim) => claim.finding)
    .sort((a, b) => rank[a.finding.severity] - rank[b.finding.severity]);
  if (!findings.length) return null;
  const filter = selection.turn === turn.id ? selection.value : "all";
  const urgent = findings.some((c) =>
    ["critical", "high"].includes(c.finding.severity),
  );
  const visible = findings.filter(
    (claim) => filter === "all" || claim.finding.severity === filter,
  );
  const severities = Object.keys(rank).filter((severity) =>
    findings.some((c) => c.finding.severity === severity),
  );
  return (
    <section className="finding-alerts" aria-label="Reviewed findings">
      <header className="findings-heading">
        <div>
          <span className="findings-kicker">
            <ShieldAlert size={14} aria-hidden="true" /> SOURCE REVIEW COMPLETE
          </span>
          <h3>
            {findings.length} {findings.length === 1 ? "finding" : "findings"}{" "}
            to review
          </h3>
          <p role={urgent ? "alert" : "status"}>
            {severities
              .map(
                (severity) =>
                  `${findings.filter((c) => c.finding.severity === severity).length} ${severity}`,
              )
              .join(" · ")}
            <span className="findings-review-note">
              {" "}
              · Model-assessed severity
            </span>
          </p>
        </div>
        {onPlan && (
          <button className="findings-plan-button" onClick={onPlan}>
            Review fix workflow <ArrowRight size={15} aria-hidden="true" />
          </button>
        )}
      </header>
      <div
        className="finding-filters"
        role="group"
        aria-label="Filter findings by severity"
      >
        {["all", ...severities].map((severity) => (
          <button
            key={severity}
            aria-pressed={filter === severity}
            onClick={() => setSelection({ turn: turn.id, value: severity })}
          >
            {severity === "all" ? "All findings" : severity}
            <span>
              {severity === "all"
                ? findings.length
                : findings.filter((c) => c.finding.severity === severity)
                    .length}
            </span>
          </button>
        ))}
      </div>
      <div className="finding-list" aria-live="polite" aria-atomic="false">
        {visible.map((claim) => {
          const finding = claim.finding;
          const sources = [
            ...new Map(
              claim.support.map((source) => [source.evidence_id, source]),
            ).values(),
          ];
          return (
            <article
              className={`finding-alert severity-${finding.severity}`}
              key={`${finding.title}:${sources[0]?.evidence_id}`}
            >
              <header className="finding-meta">
                <span className="finding-severity">
                  <span aria-hidden="true" />
                  {finding.severity}
                </span>
                <span className="finding-category">{finding.category}</span>
                {finding.location && (
                  <span className="finding-location">
                    <MapPin size={12} aria-hidden="true" />
                    <code>
                      {finding.location.path}:{finding.location.line}
                    </code>
                  </span>
                )}
              </header>
              <h4>{finding.title}</h4>
              <p className="finding-impact">{claim.text}</p>
              <ProblemLocation location={finding.location} sources={sources} onEvidence={onEvidence} />
              <div className="finding-recommendation">
                <strong>Recommended fix</strong>
                <p>{finding.recommendation}</p>
              </div>
              {onEvidence && (
                <footer className="finding-sources">
                  <span>Evidence</span>
                  {sources.map((source) => (
                    <button
                      key={source.evidence_id}
                      onClick={() => onEvidence(source.evidence_id)}
                    >
                      <FileText size={13} aria-hidden="true" />
                      {source.title}
                      <ArrowRight size={12} aria-hidden="true" />
                    </button>
                  ))}
                </footer>
              )}
            </article>
          );
        })}
      </div>
      <p className="findings-disclaimer">
        Source provenance checked and reviewed by a fallible model. Inspect the
        cited evidence; coverage may be incomplete.
      </p>
    </section>
  );
}
