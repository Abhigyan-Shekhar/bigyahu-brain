// Extractive presentation: keep original wording and leave the full record available.
export function conciseText(text = "", limit = 220) {
  const value = text.trim();
  const sentence = value.match(/^.*?[.!?](?=\s|$)/s)?.[0] || value;
  if (sentence.length <= limit) return sentence;
  const end = sentence.lastIndexOf(" ", limit);
  return sentence.slice(0, end > limit / 2 ? end : limit) + "…";
}
export function evidenceSources(turn) {
  return [
    ...new Map(
      (turn?.claims || [])
        .flatMap((c) => c.support || [])
        .map((s) => [s.evidence_id, s]),
    ).values(),
  ];
}
export const toolLabels = {
  get_context: "Retrieving company context",
  check_change: "Tracing graph relationships",
  find_owner: "Checking code ownership",
  trace_decision: "Tracing a recorded decision",
  search_code: "Finding relevant code",
  read_code: "Inspecting source code",
  search_history: "Searching repository history",
  memory_search: "Retrieving reviewed lessons",
  memory_graph: "Inspecting memory connections",
  read_file: "Reading an approved file",
  write_file: "Editing an approved file",
};

// Add only direct, current graph links whose symbol labels occur in the stored
// investigation. This is navigation context, not an expansion of citation proof.
export function sourceNeighborhood(proof, adjacent, claimText) {
  const file = proof.graph.nodes.find((n) => n.labels?.includes("File"));
  if (
    !file ||
    (adjacent.revision &&
      proof.revision &&
      adjacent.revision !== proof.revision)
  )
    return proof.graph;
  const matches = (adjacent.nodes || []).filter(
    (n) => n.labels?.includes("Symbol") && claimText.includes(n.label),
  );
  const symbols = matches
    .filter(
      (n) =>
        !matches.some(
          (other) => other.id !== n.id && other.label.startsWith(n.label + "."),
        ),
    )
    .sort((a, b) => b.label.length - a.label.length || a.id.localeCompare(b.id))
    .slice(0, 3);
  if (!symbols.length) return proof.graph;
  const ids = new Set([file.id, ...symbols.map((n) => n.id)]);
  const edges = (adjacent.edges || []).filter(
    (e) =>
      ids.has(e.source) &&
      ids.has(e.target) &&
      (e.source === file.id || e.target === file.id),
  );
  if (!edges.length) return proof.graph;
  const connected = new Set(edges.flatMap((e) => [e.source, e.target]));
  return {
    nodes: [file, ...symbols].filter((n) => connected.has(n.id)),
    edges,
    root: file.id,
    context_notice:
      "Current indexed connections around a checked source. Symbol links are navigation context; the original citation remains separately inspectable.",
  };
}
