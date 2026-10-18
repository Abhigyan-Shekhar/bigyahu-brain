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
