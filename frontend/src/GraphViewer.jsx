import React, { useEffect, useRef, useState, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  getViewportForBounds,
} from "@xyflow/react";
import {
  evidencePath,
  connectedLayout,
  neighborhood,
  nodeDimensions,
  entityAppearance,
} from "./graphPresentation";
import { knowledgeNodeTypes } from "./KnowledgeNode";

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
  const fitted = useRef(false);
  const fitAttempts = useRef(0);
  function fitVisibleCanvas() {
    const bounds = canvas.current?.getBoundingClientRect();
    if (
      !canvas.current?.checkVisibility() ||
      fitted.current ||
      !bounds?.width ||
      !bounds?.height
    )
      return;
    cancelAnimationFrame(fitFrame.current);
    fitFrame.current = requestAnimationFrame(async () => {
      const visible = canvas.current?.getBoundingClientRect();
      if (
        !canvas.current?.checkVisibility() ||
        fitted.current ||
        !flow.current ||
        !visible?.width ||
        !visible?.height
      )
        return;
      const instance = flow.current;
      const measuredNodes = instance.getNodes();
      if (
        !measuredNodes.length ||
        measuredNodes.some(
          (n) =>
            !instance.getInternalNode(n.id)?.measured?.width ||
            !instance.getInternalNode(n.id)?.measured?.height,
        )
      ) {
        if (++fitAttempts.current < 60) fitVisibleCanvas();
        return;
      }
      const target =
        viewportCache?.current[
          `${viewKey}:${pathOnly ? "path" : "graph"}:${visibleKey}`
        ] ||
        getViewportForBounds(
          instance.getNodesBounds(measuredNodes),
          visible.width,
          visible.height,
          0.02,
          1.5,
          (onExpand && !focused) || compact ? 0.25 : 0.1,
        );
      const result = await instance.setViewport(target);
      if (result) fitted.current = true;
    });
  }
  useEffect(() => {
    // A collapsed <details> has no usable viewport. Refit after its real canvas
    // dimensions first become available. Later resizes preserve pan and zoom;
    // the existing Fit View control remains the explicit way to reset them.
    const observer = new ResizeObserver(fitVisibleCanvas);
    if (canvas.current) observer.observe(canvas.current);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(fitFrame.current);
    };
  }, []);
  const [zoom, setZoom] = useState(1);
  const [selectedEdge, setSelectedEdge] = useState(null);
  const [hoveredEdge, setHoveredEdge] = useState(null);
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
  const [showAll, setShowAll] = useState(false);
  const [neighborhoodRoot, setNeighborhoodRoot] = useState(expandTarget);
  const path = pathOnly ? evidencePath(graph, expandTarget, pathTarget) : null;
  const clustered = graph?.nodes?.some((n) => n.labels?.includes("Cluster"));
  const local = useMemo(
    () => neighborhood(graph, neighborhoodRoot || focusId || graph?.root, 6),
    [graph, neighborhoodRoot, compact],
  );
  const bounded =
    !clustered &&
    !showAll &&
    !path &&
    (graph?.nodes?.length || 0) > (compact ? 6 : 16);
  const visibleNodes = (graph?.nodes || []).filter((n) =>
    path
      ? path.nodes.includes(n.id)
      : !bounded || local.nodes.some((v) => v.id === n.id),
  );
  const kinds = [...new Set(visibleNodes.map((n) => n.labels?.[0] || "Node"))];
  const visibleKey = visibleNodes.map((n) => n.id).join("|");
  useEffect(() => {
    setSelectedEdge(null);
    setHoveredEdge(null);
  }, [graph, visibleKey]);
  const layout = useMemo(
    () => connectedLayout(visibleNodes, graph?.edges || [], compact),
    [graph, visibleKey, compact],
  );
  const emphasized =
    selectedEdge ||
    (hoveredEdge != null
      ? { ...graph?.edges[hoveredEdge], recordedIndex: hoveredEdge }
      : null);
  const highlightedIds = emphasized
    ? new Set([emphasized.source, emphasized.target])
    : new Set([focusId || (bounded ? local.root : null)]);
  const nodes = visibleNodes.map((n) => ({
    id: n.id,
    type: "knowledge",
    displayLabel: n.label,
    ...nodeDimensions(n, compact),
    position: path
      ? { x: path.nodes.indexOf(n.id) * 325, y: 0 }
      : layout.get(n.id),
    data: {
      label: n.label.split("/").slice(-2).join("/"),
      fullLabel: n.label,
      onActivate: () => onInspect?.({ kind: "node", node: n }),
      appearance: entityAppearance(n),
      cluster: n.labels?.includes("Cluster"),
      count: n.count,
      emphasized: highlightedIds.has(n.id),
    },
    style: { opacity: emphasized && !highlightedIds.has(n.id) ? 0.4 : 1 },
  }));
  const evidenceFocus = focused && !!graph?.context_notice;
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
        zoom >= 0.85 ||
        compact ||
        (graph?.edges.length || 0) <= 8 ||
        hoveredEdge === e.recordedIndex ||
        selectedEdge?.recordedIndex === e.recordedIndex
          ? e.relation
          : undefined,
      data: e,
      markerEnd: { type: MarkerType.ArrowClosed },
      style: {
        stroke:
          selectedEdge?.recordedIndex === e.recordedIndex ||
          hoveredEdge === e.recordedIndex ||
          path ||
          evidenceFocus
            ? "#7650a5"
            : "#a4b6ac",
        strokeWidth:
          selectedEdge?.recordedIndex === e.recordedIndex ||
          hoveredEdge === e.recordedIndex ||
          path ||
          evidenceFocus
            ? 2.5
            : 1.2,
        opacity: emphasized
          ? emphasized.recordedIndex === e.recordedIndex
            ? 1
            : 0.15
          : evidenceFocus
            ? 1
            : 0.55,
      },
      labelStyle: { fontSize: compact ? 10 : 11, fill: "#655579" },
      labelBgStyle: { fill: "#fcfdfb", fillOpacity: 0.94 },
      labelBgPadding: [7, 4],
      type: "default",
      interactionWidth: 22,
    }));
  return (
    <div className={"graph " + (compact ? "compact" : "")}>
      {!compact && (
        <div className="graph-canvas-heading">
          <span>
            <strong>
              {visibleNodes.some((n) => n.labels?.includes("Cluster"))
                ? "Knowledge network"
                : graph?.context_notice
                  ? "Relevant evidence connection"
                  : path
                    ? "Evidence path"
                    : "Connected entities"}
            </strong>
            <small>
              {nodes.length}{" "}
              {visibleNodes.some((n) => n.labels?.includes("Cluster"))
                ? "clusters"
                : "loaded nodes"}{" "}
              · {edges.length}{" "}
              {visibleNodes.some((n) => n.labels?.includes("Cluster"))
                ? "relationship groups"
                : "recorded relationships"}
            </small>
          </span>
          <span className="graph-renderer">FalkorDB → React Flow</span>
        </div>
      )}
      {!compact && graph?.context_notice && (
        <p className="graph-type-hint">{graph.context_notice}</p>
      )}
      {!compact && bounded && (
        <div className="neighborhood-summary">
          <span>
            <strong>Focused neighborhood</strong> ·{" "}
            {visibleNodes.find((n) => n.id === local.root)?.label}{" "}
            <small>
              {visibleNodes.length} of {graph.nodes.length} loaded entities ·
              direct connections only
            </small>
          </span>
          <button onClick={() => setShowAll(true)}>
            Show all {graph.nodes.length} loaded
          </button>
        </div>
      )}
      {!compact && showAll && !clustered && (
        <div className="neighborhood-summary">
          <span>All loaded entities · zoom or choose a node to focus</span>
          <button onClick={() => setShowAll(false)}>
            Return to neighborhood
          </button>
        </div>
      )}
      {!compact && (
        <div className="graph-legend">
          <span className="tone-code">◇ Code</span>
          <span className="tone-file">□ Files</span>
          <span className="tone-evidence">▤ Evidence</span>
          <span className="tone-history">⬡ History</span>
          <small>
            Positions: Dagre · Graph: FalkorDB · Rendering: React Flow
          </small>
        </div>
      )}
      {!compact && (
        <div className="graph-toolbar" aria-label="Graph controls">
          {onExpand && !compact && (
            <div className="graph-node-picker">
              <select
                aria-label="Start node or node to expand"
                value={expandTarget}
                onChange={(e) => {
                  setExpandTarget(e.target.value);
                  setNeighborhoodRoot(e.target.value);
                  setShowAll(false);
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
                  setSelectedEdge(edge);
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
            <details className="graph-path-disclosure">
              <summary>Find an evidence path</summary>
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
            </details>
          )}
        </div>
      )}
      {!compact && (graph?.edges.length || 0) > 8 && zoom < 0.85 && (
        <p className="graph-type-hint">
          Hover or select a connection to reveal its type. Zoom in for all
          relationship labels.
        </p>
      )}
      {selectedEdge && !onInspect && (
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
        {!nodes.length && (
          <div className="graph-empty" role="status">
            No entities in this view. Search the index or choose another
            cluster.
          </div>
        )}
        <ReactFlow
          onInit={(instance) => {
            flow.current = instance;
            fitted.current = false;
            fitAttempts.current = 0;
            fitVisibleCanvas();
          }}
          key={`${pathOnly ? "path" : "graph"}:${visibleKey}`}
          nodeTypes={knowledgeNodeTypes}
          nodes={nodes}
          edges={edges}
          onMoveStart={(event) => {
            if (event) fitted.current = true;
          }}
          onNodeDoubleClick={(_, node) => onExpand?.(node.id)}
          onNodeClick={(_, node) =>
            onInspect?.({
              kind: "node",
              node: visibleNodes.find((n) => n.id === node.id),
            })
          }
          onEdgeMouseEnter={(_, edge) =>
            setHoveredEdge(edge.data.recordedIndex)
          }
          onEdgeMouseLeave={() => setHoveredEdge(null)}
          onEdgeClick={(_, edge) => {
            setSelectedEdge(edge.data);
            if (onInspect) onInspect({ kind: "edge", edge: edge.data });
            else setSelectedEdge(edge.data);
          }}
          onMoveEnd={(_, viewport) => {
            setZoom(viewport.zoom);
            if (viewportCache && canvas.current?.getBoundingClientRect().width)
              viewportCache.current[
                `${viewKey}:${pathOnly ? "path" : "graph"}:${visibleKey}`
              ] = viewport;
          }}
          zoomOnScroll={false}
          preventScrolling={false}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable
          minZoom={0.02}
          maxZoom={1.5}
          deleteKeyCode={null}
          proOptions={{ hideAttribution: false }}
        >
          <Background color="#dcd9e5" gap={22} />
          <Controls showInteractive={false} />
          {!compact && (
            <MiniMap
              pannable
              zoomable
              style={{ width: 120, height: 85 }}
              maskColor="rgba(245,248,244,.7)"
              nodeColor="#9db5a5"
            />
          )}
        </ReactFlow>
      </div>
    </div>
  );
}
