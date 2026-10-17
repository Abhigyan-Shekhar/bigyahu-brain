import React, { useEffect, useRef, useState } from "react";
import { api, send } from "./api";

export default function TeamBrain({ project, renderGraph }) {
  const base = `/repositories/${project}`;
  const [teams, setTeams] = useState([]), [selected, setSelected] = useState(""), [principal, setPrincipal] = useState("");
  const [info, setInfo] = useState(null), [items, setItems] = useState([]), [graph, setGraph] = useState(null), [member, setMember] = useState("");
  const [detail, setDetail] = useState(null), [reason, setReason] = useState(""), [error, setError] = useState(""), [notice, setNotice] = useState(""), [working, setWorking] = useState(false);
  const [name, setName] = useState(""), [newMember, setNewMember] = useState(""), [role, setRole] = useState("reader"), [memberReason, setMemberReason] = useState("");
  const [privateItems, setPrivateItems] = useState([]), [shareId, setShareId] = useState(""), [preview, setPreview] = useState(null), [truncated, setTruncated] = useState(false);
  const viewKey = useRef("");
  viewKey.current = selected + "|" + member;
  const teamBase = `${base}/teams/${encodeURIComponent(selected)}`;
  async function loadTeams() {
    const [list, notes] = await Promise.all([api(`${base}/teams`), api(`${base}/memory`)]);
    setTeams(list.items); setPrincipal(list.principal); setPrivateItems(notes.items.filter(m => m.state === "accepted"));
    setSelected(s => list.items.some(t => t.id === s) ? s : list.items[0]?.id || "");
    if (list.truncated) setNotice("Only the first 100 authorized teams are shown.");
  }
  async function load(filter = member) {
    if (!selected) return;
    const key = selected + "|" + filter;
    const suffix = filter ? `?member=${encodeURIComponent(filter)}` : "";
    const [list, view] = await Promise.all([
      api(`${teamBase}/memories${suffix}`),
      api(`${teamBase}/graph${suffix}`).catch(e => ({status:"unavailable", warnings:[e.message], graph:{nodes:[], edges:[]}}))
    ]);
    if (viewKey.current !== key) return;
    setInfo(list.team); setItems(list.items); setTruncated(list.truncated); setGraph(view);
  }
  useEffect(() => { loadTeams().catch(e => setError(e.message)); }, [project]);
  useEffect(() => { setDetail(null); setPreview(null); setReason(""); load().catch(e => setError(e.message)); }, [selected, member]);
  async function perform(fn, resetMember = false) {
    setWorking(true); setError(""); setNotice("");
    try { const r = await fn(); await loadTeams(); if(resetMember) setMember(""); await load(resetMember ? "" : member); setNotice(r.projection?.notice || "Saved."); return r; }
    catch(e) { setError(e.message); return null; }
    finally { setWorking(false); }
  }
  async function create(e) {
    e.preventDefault(); const r = await perform(() => send(`${base}/teams`, {name}));
    if (r) { setName(""); setMember(""); setSelected(r.id); setNotice("Team created. You are its local creator and reviewer. " + (r.projection?.notice || "")); }
  }
  async function inspect(item) {
    setError(""); setReason("");
    const key = viewKey.current;
    try { const value = await api(`${teamBase}/memories/${encodeURIComponent(item.uid)}`); if(viewKey.current === key) setDetail(value); }
    catch(e) { setError(e.message); }
  }
  async function review(action) {
    const r = await perform(() => send(`${teamBase}/memories/${encodeURIComponent(detail.uid)}/review`, {expected_hash:detail.hash, expected_state:detail.state, action, reason}));
    if (r) { await inspect(detail); setNotice((action === "rollback" ? "Team acceptance revoked. The shared record is excluded from chat." : `Team memory ${action === "accept" ? "accepted" : "rejected"}.`) + " " + (r.projection?.notice || "")); }
  }
  async function changeMember(e) {
    e.preventDefault(); const current = info.members.find(m => m.principal === newMember)?.role || "";
    const r = await perform(() => send(`${teamBase}/members`, {principal:newMember, role, expected_role:current, reason:memberReason}), true);
    if(r) { setMemberReason(""); setMember(""); setNotice("Team membership updated. Reads recheck current catalog access. " + (r.projection?.notice || "")); }
  }
  async function share() {
    const r = await perform(() => send(`${teamBase}/share`, {uid:preview.uid, expected_hash:preview.hash}));
    if(r) { setPreview(null); setMember(""); setNotice(`Selected memory ${r.state === "accepted" ? "was already accepted in this team" : "proposed to the team; separate review is required"}. ${r.projection?.notice || ""}`); }
  }
  return <section className="personal-brain team-brain">
    <div className="page-heading"><div><span className="eyebrow">TEAM BRAIN</span><h2>Share what helps the team.</h2></div></div>
    <p>Local operator: <strong>{principal}</strong>. Select a member to inspect their permitted shared contributions. Their private memories stay private. Team acceptance remains advisory evidence.</p>
    {error && <p className="failure" role="alert">{error}</p>}{notice && <p className="coverage" role="status">{notice}</p>}
    <details className="memory-create"><summary>Create a local team</summary><form onSubmit={create}>
      <label htmlFor="team-name">Team identifier</label><input id="team-name" required pattern="[A-Za-z0-9_-]{1,64}" maxLength={64} value={name} onChange={e => setName(e.target.value)} />
      <p>This creates a repository-scoped team and makes the configured local operator its reviewer. Member identities are catalog principals, not app login accounts.</p>
      <button className="primary" disabled={working || !name}>Create team</button>
    </form></details>
    <label htmlFor="team-select">Authorized team</label><select id="team-select" value={selected} onChange={e => {setMember(""); setInfo(null); setSelected(e.target.value);}}>
      <option value="">Choose a team</option>{teams.map(t => <option key={t.id} value={t.id}>{t.id} · {t.role}</option>)}
    </select>
    {!teams.length && <p>No authorized teams yet. Create one to start sharing selected reviewed memories.</p>}
    {selected && info && <>
      <div className="team-members"><h3>Members · shared contributions</h3><button disabled={working} aria-pressed={!member} onClick={() => setMember("")}>All members</button>
        {info.members.map(m => <button key={m.principal} disabled={working} aria-pressed={member === m.principal} onClick={() => setMember(m.principal)}>{m.principal}<small>{m.role}</small></button>)}
      </div>
      {info.can_administer && <details className="memory-create"><summary>Manage team membership</summary><form onSubmit={changeMember}>
        <p>Grant only the required role: readers see accepted evidence, writers can submit proposals, reviewers can review them. Removing membership blocks subsequent team reads. This does not create login accounts.</p>
        <label htmlFor="team-principal">Principal</label><input id="team-principal" required pattern="[A-Za-z0-9_-]{1,64}" maxLength={64} value={newMember} onChange={e => setNewMember(e.target.value)} />
        <label htmlFor="team-role">Role</label><select id="team-role" value={role} onChange={e => setRole(e.target.value)}><option value="reader">Reader</option><option value="writer">Writer</option><option value="reviewer">Reviewer</option><option value="revoke">Revoke membership</option></select>
        <label htmlFor="membership-reason">Membership reason</label><textarea id="membership-reason" required maxLength={1000} value={memberReason} onChange={e => setMemberReason(e.target.value)} />
        <button disabled={working || !newMember || !memberReason.trim()}>Apply membership change</button>
      </form></details>}
      {info.role !== "reader" && <details className="memory-create"><summary>Share an accepted personal memory</summary>
        <p>Only the selected memory text, author, expiry and original citation references are shared. The private conversation and coding-report envelope are excluded. The team receives a proposal for separate review.</p>
        <label htmlFor="share-memory">Accepted personal memory</label><select id="share-memory" value={shareId} onChange={e => {setShareId(e.target.value); setPreview(null);}}>
          <option value="">Choose a memory</option>{privateItems.map(m => <option key={m.uid} value={m.uid}>{m.text.slice(0,140)}</option>)}
        </select><button disabled={working || !shareId} onClick={() => setPreview(privateItems.find(m => m.uid === shareId))}>Preview sharing</button>
        {preview && <div className="share-preview"><h4>Selected memory → {selected}</h4><p>{preview.text}</p><p>Author: {principal} · Expiry: {preview.expires || "none"}</p><pre>{JSON.stringify(preview.sources,null,2)}</pre><button className="primary" disabled={working} onClick={share}>Propose selected memory to team</button></div>}
      </details>}
      <div className="memory-layout"><div><h3>{member ? `${member} · shared memories` : "Team memories"}</h3>
        {truncated && <p>Showing the latest 100 visible memories.</p>}{!items.length && <p>No visible shared contributions in this view.</p>}
        <div className="memory-list">{items.map(m => <button key={m.uid} className={detail?.uid === m.uid ? "selected" : ""} onClick={() => inspect(m)}><span className={`memory-state ${m.state}`}>{m.state}</span><span>{m.text}</span><small>Shared by {m.author}</small></button>)}</div>
      </div>{detail ? <article className="memory-inspector"><span className="eyebrow">REVIEW SHARED MEMORY</span><h3>{detail.state}</h3><p>{detail.text}</p>
        <h4>Selected shared source</h4>{detail.source_error ? <p className="failure">{detail.source_error}</p> : <><p>Shared by {detail.source.author}. Only this selected text and its citation references were copied.</p><pre>{JSON.stringify(detail.source.sources,null,2)}</pre></>}
        {info.role === "reviewer" && ["proposed","accepted"].includes(detail.state) && <div className="memory-review"><label htmlFor="team-review-reason">Review reason</label><textarea id="team-review-reason" maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} />
          {detail.state === "proposed" ? <><button disabled={working || !reason.trim() || !!detail.source_error} onClick={() => review("accept")}>Accept team memory</button><button disabled={working || !reason.trim()} onClick={() => review("reject")}>Reject team memory</button></> : <button disabled={working || !reason.trim()} onClick={() => review("rollback")}>Revoke team acceptance</button>}
        </div>}<details><summary>Team review history</summary><pre>{JSON.stringify(detail.reviews,null,2)}</pre></details>
      </article> : <p>Select a shared memory to inspect its source and reviews.</p>}</div>
      <section className="private-graph"><h3>{member ? `${member} · permitted shared graph` : "Team knowledge graph"}</h3>
        {info.role === "reviewer" && <button disabled={working} onClick={() => perform(() => send(`${teamBase}/refresh`,{}))}>Refresh team graph</button>}
        {graph?.status !== "ok" ? <p>{graph?.warnings?.join(" · ") || "Graph unavailable"}</p> : <>{graph.graph.truncated && <p>Showing a bounded slice: up to 150 nodes and 300 relationships.</p>}{renderGraph(graph.graph)}</>}
      </section>
    </>}
  </section>;
}
