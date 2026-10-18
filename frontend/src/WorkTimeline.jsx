import React from "react";

export function Timestamp({ value }) {
  if (!value) return <>Unknown</>;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? <>Unknown</> : (
    <time dateTime={value} title={date.toISOString()}>{date.toLocaleString()}</time>
  );
}

export default function WorkTimeline({ data, onNode }) {
  return <div className="work-timeline">
    {!data?.items?.length && <p>No linked indexed issues or PRs.</p>}
    {data?.items?.map((item) => <article key={item.uid}>
      <h4><button onClick={() => onNode(item.uid)}>{item.kind} · {item.title}</button></h4>
      <p>{item.status || "Unknown status"} · Due: <Timestamp value={item.due_at} /></p>
      {item.deadline_basis && <small>Deadline from GitHub milestone</small>}
      <p>Last updated: <Timestamp value={item.updated_at} /></p>
      {/^https:\/\//.test(item.url || "") && <a href={item.url} target="_blank" rel="noreferrer">Open on GitHub</a>}
      {item.decisions.length ? item.decisions.map((decision) => <div className="decision-entry" key={`${decision.uid}:${decision.source_uid}`}>
        <button onClick={() => onNode(decision.uid)}>{decision.text}</button>
        <p>{decision.status} · Recorded: <Timestamp value={decision.created_at} /></p>
        {decision.approved_at && <p>Approved by {decision.approved_by || "Unknown"} · <Timestamp value={decision.approved_at} /></p>}
        <button onClick={() => onNode(decision.source_uid)}>Inspect decision source</button>
      </div>) : <p>No indexed decisions linked to this work item.</p>}
      <small>Snapshot: <Timestamp value={item.snapshot_at} /></small>
    </article>)}
    {data?.truncated && <p>First {data.limits.work_items} work items shown.</p>}
    {data?.decisions_truncated && <p>Decision links limited to {data.limits.decision_links}; some work items may have additional decisions.</p>}
  </div>;
}
