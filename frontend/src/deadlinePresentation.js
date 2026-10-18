export function deadlineGroup(item, now = Date.now()) {
  const due = Date.parse(item.due_at);
  if (!Number.isFinite(due)) return "undated";
  if (["closed", "merged", "closed_unmerged"].includes(item.status))
    return "completed";
  return due < now ? "overdue" : "upcoming";
}

export function deadlineLayout(items, now = Date.now()) {
  const dated = items
    .filter((item) => Number.isFinite(Date.parse(item.due_at)))
    .sort(
      (a, b) =>
        Date.parse(a.due_at) - Date.parse(b.due_at) ||
        a.uid.localeCompare(b.uid),
    );
  const undated = items.filter(
    (item) => !Number.isFinite(Date.parse(item.due_at)),
  );
  if (!dated.length)
    return { dated: [], undated, start: now, end: now, nowFraction: null };
  const start = Date.parse(dated[0].due_at) - 86400000;
  const end = Date.parse(dated.at(-1).due_at) + 86400000;
  return {
    start,
    end,
    undated,
    nowFraction:
      now >= start && now <= end ? (now - start) / (end - start) : null,
    dated: dated.map((item) => ({
      item,
      fraction: (Date.parse(item.due_at) - start) / (end - start),
    })),
  };
}
