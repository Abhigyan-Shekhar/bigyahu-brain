import React, { useEffect, useState } from "react";
import { api } from "./api";
import ActivityStream from "./ActivityStream";
export default function InvestigationRun({
  run,
  onEvidence,
  onInvestigation,
  onPlan,
}) {
  const [turn, setTurn] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    const refresh = () =>
      api(`/sessions/${run.session}/turns`)
        .then((items) => {
          if (live) setTurn(items.find((t) => t.id === run.turn));
        })
        .catch((e) => {
          if (live) setError(e.message);
        });
    refresh();
    const timer = setInterval(refresh, 1500);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [run.id]);
  return (
    <>
      <div className="run-origin">
        <strong>Read-only investigation</strong>
        <h3>{run.question}</h3>
        <button onClick={() => onInvestigation(run)}>
          Return to conversation
        </button>
      </div>
      {error && (
        <p role="alert" className="failure">
          {error}
        </p>
      )}
      {turn ? (
        <>
          <ActivityStream turn={turn} />
          {turn.claims?.map((claim, i) => (
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
            <details>
              <summary>Coverage and limitations</summary>
              {turn.limitations.map((l, i) => (
                <p key={i}>{l}</p>
              ))}
            </details>
          )}
          {turn.status === "complete" && (
            <button className="primary" onClick={() => onPlan(run)}>
              Propose a fix in Ask Brain
            </button>
          )}
        </>
      ) : (
        <p role="status">Loading investigation…</p>
      )}
    </>
  );
}
