import React from "react";
export default function GraphInspector({
  selection,
  detail,
  graph,
  loading,
  onNode,
  onExpand,
  onFocus,
  linkedEvidence,
  onSource,
  onExplain,
  onClose,
}) {
  const label = (id) => graph?.nodes?.find((n) => n.id === id)?.label || id;
  const linkedPathSource =
    selection.kind === "path" &&
    linkedEvidence &&
    selection.nodes.every((id) =>
      linkedEvidence.graph.nodes.some((n) => n.id === id),
    ) &&
    selection.edges.every((e) =>
      linkedEvidence.graph.edges.some(
        (s) =>
          s.source === e.source &&
          s.target === e.target &&
          s.relation === e.relation,
      ),
    );
  const edge = selection.edge;
  return (
    <div className="graph-inspector">
      <div className="inspector-heading">
        <strong>
          {selection.kind === "path"
            ? "Recorded path"
            : edge
              ? "Recorded relationship"
              : selection.node?.labels?.join(" · ") || "Entity"}
        </strong>
        <button aria-label="Close graph inspector" onClick={onClose}>
          ×
        </button>
      </div>
      {edge ? (
        <>
          <h3>{edge.relation}</h3>
          {edge.aggregate && (
            <p>
              {edge.count.toLocaleString()} stored relationships aggregated
              between these clusters. Open either cluster to inspect individual
              entities and sources.
            </p>
          )}
          <button onClick={() => onNode(edge.source)}>
            {label(edge.source)}
          </button>
          <p>→ {edge.relation} →</p>
          <button onClick={() => onNode(edge.target)}>
            {label(edge.target)}
          </button>
          <p>Stored type: {edge.edge_type || edge.relation}</p>
          {edge.confidence && <p>Confidence: {edge.confidence}</p>}
          {edge.quote && <blockquote>{edge.quote}</blockquote>}
          {edge.source_uid && (
            <button onClick={() => onNode(edge.source_uid)}>
              Inspect supporting source
            </button>
          )}
        </>
      ) : selection.kind === "path" ? (
        <>
          <h3>Evidence path</h3>
          <p>
            Shortest recorded connection in the loaded slice. Arrows retain
            stored direction; a connection is not proof of causality.
          </p>
          {linkedPathSource && (
            <button onClick={() => onSource(linkedEvidence)}>
              Open checked source for this evidence slice
            </button>
          )}
          <ol>
            {selection.edges.map((e, i) => (
              <li key={i}>
                <button onClick={() => onNode(e.source)}>
                  {label(e.source)}
                </button>
                <strong> → {e.relation} → </strong>
                <button onClick={() => onNode(e.target)}>
                  {label(e.target)}
                </button>
                {e.quote && <blockquote>{e.quote}</blockquote>}
                {e.source_uid && (
                  <button onClick={() => onNode(e.source_uid)}>
                    Supporting source
                  </button>
                )}
              </li>
            ))}
          </ol>
        </>
      ) : (
        <>
          <h3>{selection.node?.label}</h3>
          <code>{selection.node?.id}</code>
          {loading && <p role="status">Checking current entity and source…</p>}
          {detail?.error && <p className="coverage">{detail.error}</p>}
          {detail?.revision && (
            <p>
              Indexed revision: <code>{detail.revision.slice(0, 12)}</code>
            </p>
          )}
          {detail?.properties && (
            <dl>
              {Object.entries(detail.properties)
                .filter(([, v]) => v != null)
                .map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{String(v)}</dd>
                  </div>
                ))}
            </dl>
          )}
          {detail?.evidence && (
            <>
              <p className="coverage">
                Source reopened and checked independently of the graph label.
              </p>
              <button onClick={() => onSource(detail.evidence)}>
                Open checked source
              </button>
              <pre>{detail.evidence.text}</pre>
            </>
          )}
          {detail?.source_notice && (
            <p className="coverage">{detail.source_notice}</p>
          )}
          {detail?.sources?.map((uid) => (
            <button key={uid} onClick={() => onNode(uid)}>
              Inspect source {uid.split(":").at(-1).slice(0, 12)}
            </button>
          ))}
          {detail?.sources_truncated && <p>First 10 attached sources shown.</p>}
          <h4>Loaded relationships</h4>
          <p>
            Expand neighbors for more; this list describes the loaded slice.
          </p>
          {(graph?.edges || [])
            .filter(
              (e) =>
                e.source === selection.node?.id ||
                e.target === selection.node?.id,
            )
            .slice(0, 15)
            .map((e, i) => (
              <p key={i}>
                <button
                  onClick={() =>
                    onNode(e.source === selection.node.id ? e.target : e.source)
                  }
                >
                  {e.relation} ·{" "}
                  {label(e.source === selection.node.id ? e.target : e.source)}
                </button>
              </p>
            ))}
          <button onClick={() => onFocus(selection.node.id)}>
            Focus neighborhood
          </button>
          <button onClick={() => onExpand(selection.node.id)}>
            Expand neighbors
          </button>
        </>
      )}
      {!edge?.aggregate && (
        <div className="inspector-actions">
          <button className="primary" onClick={() => onExplain(selection)}>
            Explain in chat
          </button>
          <p>
            Attaches this selection to the composer. You review it before
            sending.
          </p>
        </div>
      )}
    </div>
  );
}
