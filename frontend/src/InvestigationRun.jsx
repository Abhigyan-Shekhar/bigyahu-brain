import React, { useEffect, useState } from "react";
import { watchResource } from "./api";
import FindingAlerts from "./FindingAlerts";
import ActivityStream from "./ActivityStream";
import { elapsedLabel } from "./actionPresentation";
export default function InvestigationRun({
  run,
  onEvidence,
  onInvestigation,
  onPlan,
}) {
  const [turn, setTurn] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    setTurn(null);
    return watchResource(
      `/turns/${run.id}/events`,
      `/repositories/${run.project}/runs/${run.id}`,
      (item) => {
        setTurn(item.investigation || item);
        setError("");
      },
      (e) => setError(e.message),
    );
  }, [run.id, run.project]);
  return (
    <>
      <header className="investigation-run-heading">
        <div>
          <span className="eyebrow">READ-ONLY INVESTIGATION</span>
          <h3>
            {turn?.status === "complete"
              ? "Investigation results"
              : "Following the evidence"}
          </h3>
          <details className="investigation-question">
            <summary>View original question</summary>
            <p>{run.question}</p>
          </details>
        </div>
        <button onClick={() => onInvestigation(run)}>
          Back to conversation
        </button>
      </header>
      {error && (
        <p role="alert" className="failure">
          {error}
        </p>
      )}
      {turn ? (
        <>
          {["queued", "running"].includes(turn.status) ? (
            <ActivityStream turn={turn} />
          ) : (
            <details className="completed-activity">
              <summary>
                Run details{" "}
                <span>
                  {elapsedLabel(turn.progress?.elapsed_seconds)} ·{" "}
                  {turn.progress?.completed_count ?? 0} tool actions
                </span>
              </summary>
              <ActivityStream turn={turn} />
            </details>
          )}
          <FindingAlerts
            turn={turn}
            onEvidence={(id) => onEvidence(turn.id, id, "turns", run)}
            onPlan={() => onPlan(run)}
          />
          {turn.claims
            ?.filter((claim) => !claim.finding)
            .map((claim, i) => (
              <section className="discovery-card" key={i}>
                <p>{claim.text}</p>
                {claim.support.map((s) => (
                  <button
                    key={s.evidence_id}
                    onClick={() =>
                      onEvidence(turn.id, s.evidence_id, "turns", run)
                    }
                  >
                    {s.title}
                  </button>
                ))}
              </section>
            ))}
          {turn.limitations?.length > 0 && (
            <details className="result-limitations">
              <summary>Coverage and limitations</summary>
              {turn.limitations.map((l, i) => (
                <p key={i}>{l}</p>
              ))}
            </details>
          )}
          {turn.status === "complete" &&
            !turn.claims?.some((claim) => claim.finding) && (
              <button className="primary" onClick={() => onPlan(run)}>
                Propose a fix in Ask Brain
              </button>
            )}
        </>
      ) : error ? null : (
        <p role="status">Loading investigation…</p>
      )}
    </>
  );
}
