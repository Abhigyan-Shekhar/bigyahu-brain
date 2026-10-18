import React, { useEffect, useRef, useState } from "react";
import { ReactFlow, Background, Controls, MarkerType } from "@xyflow/react";
import { evidencePath } from "./graphPresentation";

export default function Graph({
  graph,
  compact = false,
  focused = false,
  focusId,
  onExpand,
  onInspect,
  onExplain,
  viewportCache,
  uiCache,
  viewKey = "graph",
}) {
  const canvas = useRef(null);
  const flow = useRef(null);
  const fitFrame = useRef(null);
  function fitVisibleCanvas() {
    const bounds = canvas.current?.getBoundingClientRect();
    if (!bounds?.width || !bounds?.height) return;
    cancelAnimationFrame(fitFrame.current);
    fitFrame.current = requestAnimationFrame(() =>
      viewportCache?.current[viewKey]
        ? flow.current?.setViewport(viewportCache.current[viewKey])
        : flow.current?.fitView({
            padding: (onExpand && !focused) || compact ? 0.25 : 0.1,
          }),
    );
  }
  useEffect(() => {
    // A collapsed <details> has no usable viewport. Refit after its real canvas
    // dimensions become available, including in Personal and Team Brain panels.
    const observer = new ResizeObserver(fitVisibleCanvas);
    if (canvas.current) observer.observe(canvas.current);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(fitFrame.current);
    };
  }, []);
  const [zoom, setZoom] = useState(1);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [expandTarget, setExpandTarget] = useState(
    uiCache?.current[viewKey]?.expandTarget || "",
  );
  const [pathTarget, setPathTarget] = useState(
    uiCache?.current[viewKey]?.pathTarget || "",
  );
  const [pathOnly, setPathOnly] = useState(
    uiCache?.current[viewKey]?.pathOnly || false,
  );
  useEffect(() => {
    if (uiCache)
      uiCache.current[viewKey] = { expandTarget, pathTarget, pathOnly };
  }, [expandTarget, pathTarget, pathOnly, viewKey]);
  const path = pathOnly ? evidencePath(graph, expandTarget, pathTarget) : null;
  useEffect(() => setSelectedEdge(null), [graph]);
  const groups = {};
  const visibleIds = new Set();
  if (compact) {
    for (const edge of graph?.edges || []) {
      if (visibleIds.size >= 6) break;
      visibleIds.add(edge.source);
      visibleIds.add(edge.target);
    }
    if (!visibleIds.size)
      (graph?.nodes || []).slice(0, 6).forEach((n) => visibleIds.add(n.id));
  }
  const visibleNodes = (graph?.nodes || []).filter((n) =>
    path ? path.nodes.includes(n.id) : !compact || visibleIds.has(n.id),
  );
  const kinds = [...new Set(visibleNodes.map((n) => n.labels?.[0] || "Node"))];
  const kindColumns = {};
  let nextColumn = 0;
  for (const kind of kinds) {
    kindColumns[kind] = nextColumn;
    nextColumn += Math.ceil(
      visibleNodes.filter((n) => (n.labels?.[0] || "Node") === kind).length / 8,
    );
  }
  const nodes = visibleNodes.map((n, nodeIndex) => {
    const kind = n.labels?.[0] || "Node";
    const key = kinds.indexOf(kind);
    const i = groups[key] || 0;
    groups[key] = i + 1;
    return {
      id: n.id,
      displayLabel: n.label,
      sourcePosition: "right",
      targetPosition: "left",
      position: path
        ? { x: path.nodes.indexOf(n.id) * 280, y: 0 }
        : compact
          ? { x: (nodeIndex % 2) * 180, y: Math.floor(nodeIndex / 2) * 95 }
          : !onExpand || focused
            ? { x: (nodeIndex % 3) * 260, y: Math.floor(nodeIndex / 3) * 110 }
            : {
                x: (kindColumns[kind] + Math.floor(i / 8)) * 260,
                y: (i % 8) * 95,
              },
      data: {
        label: (
          <>
            <small>{kind}</small>
            <span title={n.id}>
              {zoom >= 0.55 ||
              compact ||
              visibleNodes.length <= 20 ||
              n.labels?.includes("Cluster")
                ? n.label.split("/").slice(-2).join("/")
                : ""}
            </span>
          </>
        ),
      },
      style: {
        width: compact ? 150 : 220,
        ...(n.id === focusId
          ? {
              background: "#e0eee1",
              borderColor: "#547f5b",
              boxShadow: "0 0 0 2px #547f5b",
            }
          : {}),
      },
    };
  });
  const ids = new Set(nodes.map((n) => n.id));
  const edges = (graph?.edges || [])
    .map((e, i) => ({ ...e, recordedIndex: i }))
    .filter(
      (e) =>
        ids.has(e.source) &&
        ids.has(e.target) &&
        (!path || path.edges.includes(e.recordedIndex)),
    )
    .map((e) => ({
      ...e,
      id: String(e.recordedIndex),
      label:
        zoom >= 0.55 || compact || visibleNodes.length <= 20
          ? e.relation
          : undefined,
      data: e,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: {
        stroke: "#8b80bd",
        opacity: zoom < 0.35 && visibleNodes.length > 30 ? 0 : 1,
      },
      labelStyle: { fontSize: compact ? 11 : 12 },
    }));
  return (
    <div className={"graph " + (compact ? "compact" : "")}>
      {!compact && (
        <div className="graph-toolbar" aria-label="Graph controls">
          {onExpand && !compact && (
            <div className="graph-node-picker">
              <select
                aria-label="Start node or node to expand"
                value={expandTarget}
                onChange={(e) => {
                  setExpandTarget(e.target.value);
                  setPathOnly(false);
                }}
              >
                <option value="">Choose a node…</option>
                {(graph?.nodes || []).map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label}
                  </option>
                ))}
              </select>
              {onInspect && (
                <button
                  disabled={!expandTarget}
                  onClick={() =>
                    onInspect({
                      kind: "node",
                      node: graph.nodes.find((n) => n.id === expandTarget),
                    })
                  }
                >
                  Inspect entity
                </button>
              )}
              <button
                disabled={!expandTarget}
                onClick={() => onExpand(expandTarget)}
              >
                Expand neighbors
              </button>
            </div>
          )}
          {edges.length > 0 && !compact && (
            <select
              className="graph-edge-picker"
              aria-label="Inspect relationship"
              value={
                edges.find(
                  (e) => e.data.recordedIndex === selectedEdge?.recordedIndex,
                )?.id ?? ""
              }
              onChange={(event) => {
                const edge = edges.find(
                  (e) => e.id === event.target.value,
                )?.data;
                if (edge) {
                  if (onInspect) onInspect({ kind: "edge", edge });
                  else setSelectedEdge(edge);
                }
              }}
            >
              <option value="">Inspect a relationship…</option>
              {edges.map((edge) => (
                <option key={edge.id} value={edge.id}>
                  {nodes.find((n) => n.id === edge.source)?.displayLabel} →{" "}
                  {edge.data.relation} →{" "}
                  {nodes.find((n) => n.id === edge.target)?.displayLabel}
                </option>
              ))}
            </select>
          )}
          {onExpand && (
            <div className="graph-path-controls">
              <select
                aria-label="Evidence path destination"
                value={pathTarget}
                onChange={(e) => {
                  setPathTarget(e.target.value);
                  setPathOnly(false);
                }}
              >
                <option value="">Choose path destination…</option>
                {(graph?.nodes || []).map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.label}
                  </option>
                ))}
              </select>
              <button
                disabled={!expandTarget || !pathTarget}
                onClick={() => {
                  setSelectedEdge(null);
                  setPathOnly(true);
                }}
              >
                Focus evidence path
              </button>
              {pathOnly && (
                <button onClick={() => setPathOnly(false)}>
                  Show all loaded nodes
                </button>
              )}
              {pathOnly && (
                <small role="status">
                  {path
                    ? `${path.nodes.length} nodes · ${path.edges.length} stored relationships. Arrows retain recorded direction; connection does not prove causality.`
                    : "No connecting path in the loaded graph. Load or expand more evidence."}
                </small>
              )}
              {path && onInspect && (
                <button
                  onClick={() =>
                    onInspect({
                      kind: "path",
                      nodes: path.nodes,
                      edges: path.edges.map((i) => graph.edges[i]),
                    })
                  }
                >
                  Inspect path
                </button>
              )}
              {path && onExplain && (
                <button
                  onClick={() =>
                    onExplain({
                      kind: "path",
                      nodes: path.nodes,
                      edges: path.edges.map((i) => graph.edges[i]),
                    })
                  }
                >
                  Explain path in chat
                </button>
              )}
            </div>
          )}
        </div>
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
      {zoom < 0.35 && visibleNodes.length > 30 && (
        <p className="graph-zoom-hint">
          {visibleNodes.length} loaded entities · {kinds.join(", ")}. Zoom in
          for individual labels and relationships, or select an entity in the
          toolbar.
        </p>
      )}
      <div className="graph-canvas" ref={canvas}>
        <ReactFlow
          onInit={(instance) => {
            flow.current = instance;
            fitVisibleCanvas();
          }}
          key={nodes.map((n) => n.id).join("|")}
          nodes={nodes}
          edges={edges}
          onNodeDoubleClick={(_, node) => onExpand?.(node.id)}
          onNodeClick={(_, node) =>
            onInspect?.({
              kind: "node",
              node: visibleNodes.find((n) => n.id === node.id),
            })
          }
          onEdgeClick={(_, edge) => {
            if (onInspect) onInspect({ kind: "edge", edge: edge.data });
            else setSelectedEdge(edge.data);
          }}
          onMoveEnd={(_, viewport) => {
            setZoom(viewport.zoom);
            if (viewportCache && canvas.current?.getBoundingClientRect().width)
              viewportCache.current[viewKey] = viewport;
          }}
          zoomOnScroll={false}
          preventScrolling={false}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          fitView
          fitViewOptions={{
            padding: (onExpand && !focused) || compact ? 0.25 : 0.1,
          }}
          minZoom={0.02}
          maxZoom={1.5}
          deleteKeyCode={null}
          proOptions={{ hideAttribution: false }}
        >
          <Background color="#dcd9e5" gap={22} />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}
