import React from "react";

export default function ProblemLocation({
  location,
  sources = [],
  onEvidence,
}) {
  if (!location?.path)
    return (
      <p className="problem-location-unknown">
        Code location not supplied by the finding.
      </p>
    );
  const parts = location.path.split("/").filter(Boolean);
  return (
    <figure className="problem-map">
      <figcaption>Where the problem is</figcaption>
      <ol aria-label="Code location flow">
        <li>
          <small>01 · ROOT</small>
          <strong>Repository</strong>
        </li>
        {parts.map((part, index) => (
          <li key={index}>
            <small>
              {String(index + 2).padStart(2, "0")} ·{" "}
              {index === parts.length - 1 ? "FILE" : "FOLDER"}
            </small>
            <code>{part}</code>
          </li>
        ))}
        <li className="problem-map-target">
          <small>PROBLEM LOCATION</small>
          <strong>
            {Number.isFinite(location.line)
              ? `Line ${location.line}`
              : "Line unknown"}
          </strong>
        </li>
      </ol>
      {!!sources.length && (
        <details>
          <summary>Read the cited evidence here</summary>
          {sources.map((source) => (
            <blockquote key={source.evidence_id}>
              {source.quote || "No excerpt supplied."}
              {onEvidence && (
                <button onClick={() => onEvidence(source.evidence_id)}>
                  Inspect checked source · {source.title}
                </button>
              )}
            </blockquote>
          ))}
        </details>
      )}
      <small>
        Recorded file location; arrows show containment, not execution order.
      </small>
    </figure>
  );
}
