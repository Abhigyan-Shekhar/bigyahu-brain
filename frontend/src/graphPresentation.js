import dagre from "@dagrejs/dagre";

// Shortest recorded connection. Traversal is undirected; rendered arrows retain
// their stored direction. A connection is navigation context, not causal proof.
export function evidencePath(graph, from, to) {
  if (!from || !to) return null;
  const ids = new Set((graph?.nodes || []).map((n) => n.id));
  if (!ids.has(from) || !ids.has(to)) return null;
  const queue = [{ id: from, nodes: [from], edges: [] }];
  const seen = new Set([from]);
  for (let i = 0; i < queue.length; i++) {
    const item = queue[i];
    if (item.id === to) return item;
    (graph.edges || []).forEach((edge, index) => {
      const next =
        edge.source === item.id
          ? edge.target
          : edge.target === item.id
            ? edge.source
            : null;
      if (next && ids.has(next) && !seen.has(next)) {
        seen.add(next);
        queue.push({
          id: next,
          nodes: [...item.nodes, next],
          edges: [...item.edges, index],
        });
      }
    });
  }
  return null;
}

// Aggregate only relationships returned by the repository-scoped overview.
// No inferred or decorative links are introduced into the graph.
export function clusterGraph(overview, grouping) {
  const nodeId = (key) => `cluster:${grouping}:${key}`;
  const groups = overview?.groups || [];
  const keys = new Set(groups.map((g) => g.key));
  const links = overview?.relationships || [];
  return {
    nodes: groups.map((g) => ({
      id: nodeId(g.key),
      label: g.key,
      labels: ["Cluster"],
      clusterKey: g.key,
      count: g.count,
      internalCount: links
        .filter((e) => e.source === g.key && e.target === g.key)
        .reduce((n, e) => n + e.count, 0),
    })),
    edges: links
      .filter(
        (e) =>
          e.source !== e.target && keys.has(e.source) && keys.has(e.target),
      )
      .map((e) => ({
        source: nodeId(e.source),
        target: nodeId(e.target),
        relation: `${e.relation} · ${e.count.toLocaleString()}`,
        count: e.count,
        edge_type: e.relation,
        aggregate: true,
      })),
  };
}

// Rendering remains React Flow's job; Dagre supplies directed positions.
export function nodeDimensions(node, compact = false) {
  return node.labels?.includes("Cluster")
    ? { width: 150, height: 120 }
    : { width: compact ? 160 : 220, height: compact ? 80 : 90 };
}

export function connectedLayout(nodes, edges, compact = false) {
  if (!nodes.length) return new Map();
  const layout = new dagre.graphlib.Graph({ multigraph: true });
  layout.setGraph({
    rankdir: "LR",
    nodesep: 45,
    ranksep: 105,
    edgesep: 25,
    marginx: 20,
    marginy: 20,
  });
  layout.setDefaultEdgeLabel(() => ({}));
  const ids = new Set(nodes.map((n) => n.id));
  [...nodes]
    .sort((a, b) => a.id.localeCompare(b.id))
    .forEach((n) => layout.setNode(n.id, nodeDimensions(n, compact)));
  edges.forEach((e, i) => {
    if (ids.has(e.source) && ids.has(e.target))
      layout.setEdge(e.source, e.target, {}, String(i));
  });
  dagre.layout(layout);
  return new Map(
    nodes.map((n) => {
      const point = layout.node(n.id),
        size = nodeDimensions(n, compact);
      return [
        n.id,
        { x: point.x - size.width / 2, y: point.y - size.height / 2 },
      ];
    }),
  );
}

// A bounded one-hop view keeps hubs from turning the canvas into a hairball.
// Edges are always selected from the original graph, preserving their direction.
export function neighborhood(graph, preferred, limit = 12) {
  const nodes = graph?.nodes || [],
    edges = graph?.edges || [];
  const degree = new Map(nodes.map((n) => [n.id, 0]));
  edges.forEach((e) => {
    if (degree.has(e.source) && degree.has(e.target)) {
      degree.set(e.source, degree.get(e.source) + 1);
      degree.set(e.target, degree.get(e.target) + 1);
    }
  });
  const ordered = [...nodes].sort((a, b) => {
    const preference = (n) =>
      /Symbol|CodeEntity/.test(n.labels?.[0] || "")
        ? 3
        : /File/.test(n.labels?.[0] || "")
          ? 2
          : /Document/.test(n.labels?.[0] || "")
            ? 1
            : 0;
    return (
      Number(degree.get(b.id) > 0) - Number(degree.get(a.id) > 0) ||
      preference(b) - preference(a) ||
      degree.get(b.id) - degree.get(a.id) ||
      a.id.localeCompare(b.id)
    );
  });
  const root = nodes.find((n) => n.id === preferred) || ordered[0];
  if (!root) return { nodes: [], edges: [], root: null };
  const neighbors = new Set();
  edges.forEach((e) => {
    if (e.source === root.id) neighbors.add(e.target);
    if (e.target === root.id) neighbors.add(e.source);
  });
  const visible = [
    root,
    ...ordered.filter((n) => n.id !== root.id && neighbors.has(n.id)),
  ].slice(0, limit);
  const ids = new Set(visible.map((n) => n.id));
  return {
    nodes: visible,
    edges: edges.filter((e) => ids.has(e.source) && ids.has(e.target)),
    root: root.id,
  };
}

export function entityAppearance(node) {
  const type = node.clusterKey || node.labels?.[0] || "Entity";
  if (/Symbol|CodeEntity/.test(type))
    return { type, shape: "diamond", tone: "code", icon: "code" };
  if (/File/.test(type))
    return { type, shape: "square", tone: "file", icon: "file" };
  if (/Source|Document|Section/.test(type))
    return { type, shape: "document", tone: "evidence", icon: "document" };
  if (/Commit|PR|Issue/.test(type))
    return { type, shape: "hexagon", tone: "history", icon: "history" };
  if (/Memory|Decision|Concept/.test(type))
    return { type, shape: "diamond", tone: "memory", icon: "memory" };
  return { type, shape: "circle", tone: "entity", icon: "entity" };
}
