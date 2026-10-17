import React, { useEffect, useState } from "react";
import { api, send } from "./api";

function SourceRecord({ source }) {
  if (source.kind === "lesson") {
    const report = JSON.parse(source.text);
    return (
      <div className="lesson-source">
        <p>
          <strong>Coding objective</strong>
          <br />
          {report.objective}
        </p>
        <p>Changed files: {report.changed_files.join(", ")}</p>
        {report.tests.map((t, i) => (
          <p key={i}>
            <strong>{t.passed ? "Passed" : "Failed"}</strong> ·{" "}
            {t.tests_reported} reported cases · exit {t.exit_code}
            <br />
            <code>{t.argv.join(" ")}</code>
          </p>
        ))}
        <details>
          <summary>Source audit details</summary>
          <pre>{JSON.stringify(report, null, 2)}</pre>
        </details>
      </div>
    );
  }
  return (
    <pre>
      {source.kind === "note" ? JSON.parse(source.text).text : source.text}
    </pre>
  );
}

export default function PersonalBrain({
  project,
  turns,
  session,
  renderGraph,
}) {
  const [items, setItems] = useState([]),
    [graph, setGraph] = useState(null),
    [detail, setDetail] = useState(null),
    [note, setNote] = useState(""),
    [reason, setReason] = useState(""),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [working, setWorking] = useState(false),
    [selected, setSelected] = useState([]),
    [preview, setPreview] = useState(null),
    [semantic, setSemantic] = useState(false),
    [imports, setImports] = useState([]),
    [relationships, setRelationships] = useState([]),
    [truncated, setTruncated] = useState(false),
    [companyEnabled, setCompanyEnabled] = useState(false),
    [repositories, setRepositories] = useState([]),
    [origin, setOrigin] = useState(""),
    [transferItems, setTransferItems] = useState([]),
    [transferSelected, setTransferSelected] = useState([]),
    [transferPreview, setTransferPreview] = useState(null);
  async function load() {
    const [records, view, jobs] = await Promise.all([
      api(`/repositories/${project}/memory`),
      api(`/repositories/${project}/memory/graph`).catch((e) => ({
        status: "unavailable",
        warnings: [e.message],
        graph: { nodes: [], edges: [] },
      })),
      api(`/repositories/${project}/memory/imports`),
    ]);
    setCompanyEnabled(!!records.company_enabled);
    setItems(records.items);
    setTruncated(records.truncated);
    setRelationships(records.relationships || []);
    setGraph(view);
    setImports(jobs);
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [project]);
  useEffect(() => {
    api("/repositories")
      .then(setRepositories)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    setTransferItems([]);
    setTransferSelected([]);
    setTransferPreview(null);
    if (origin)
      api(`/repositories/${origin}/memory`)
        .then((r) =>
          setTransferItems(r.items.filter((i) => i.state === "accepted")),
        )
        .catch((e) => setError(e.message));
  }, [origin]);
  async function prepareTransfer() {
    const r = await perform(() =>
      send(`/repositories/${project}/memory/transfers/preview`, {
        origin,
        records: transferSelected,
      }),
    );
    if (r) setTransferPreview(r);
  }
  async function confirmTransfer() {
    const r = await perform(() =>
      send(`/repositories/${project}/memory/transfers`, {
        origin,
        records: transferSelected,
        consent_digest: transferPreview.consent_digest,
      }),
    );
    if (r) {
      setTransferPreview(null);
      setTransferSelected([]);
      setNotice(
        "Selected memories copied as destination proposals. Review them separately; source acceptance is not transferred.",
      );
    }
  }
  const activeImport = imports.some((j) =>
    ["queued", "running"].includes(j.status),
  );
  useEffect(() => {
    if (!activeImport) return;
    const timer = setInterval(
      () => load().catch((e) => setError(e.message)),
      2000,
    );
    return () => clearInterval(timer);
  }, [activeImport, project]);
  async function inspect(item) {
    setError("");
    setReason("");
    try {
      setDetail(
        await api(
          `/repositories/${project}/memory/records/${encodeURIComponent(item.uid)}`,
        ),
      );
    } catch (e) {
      setError(e.message);
    }
  }
  async function perform(fn) {
    setWorking(true);
    setError("");
    setNotice("");
    try {
      const r = await fn();
      if (r.projection?.status === "unavailable")
        setNotice(r.projection.notice);
      if (r.status === "unavailable") setNotice(r.notice);
      if (r.projections)
        setNotice(
          Object.entries(r.projections)
            .filter(([, v]) => v.status !== "ok")
            .map(([brain, v]) => brain + ": " + v.notice)
            .join("; ") ||
            "Company evidence setting saved and authorized projections refreshed.",
        );
      await load();
      return r;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setWorking(false);
    }
  }
  async function add(e) {
    e.preventDefault();
    const r = await perform(() =>
      send(`/repositories/${project}/memory`, { text: note }),
    );
    if (r) {
      setNote("");
      setNotice(
        "Memory proposed. Review its source before accepting it. " +
          (r.projection?.notice || ""),
      );
    }
  }
  async function review(action) {
    const r = await perform(() =>
      send(
        `/repositories/${project}/memory/records/${encodeURIComponent(detail.uid)}/review`,
        {
          expected_hash: detail.hash,
          expected_state: detail.state,
          action,
          reason,
        },
      ),
    );
    if (r) {
      await inspect(detail);
      setNotice(
        (action === "rollback"
          ? "Acceptance revoked. This memory is excluded from agent retrieval."
          : `Memory ${action === "accept" ? "accepted" : "rejected"}.`) +
          " " +
          (r.projection?.notice || ""),
      );
    }
  }
  async function prepare(e) {
    e.preventDefault();
    setError("");
    try {
      setPreview(
        await send(`/repositories/${project}/memory/preview`, {
          session,
          turns: selected,
        }),
      );
    } catch (e) {
      setError(e.message);
    }
  }
  async function importTurns() {
    const r = await perform(() =>
      send(`/repositories/${project}/memory/imports`, {
        session,
        turns: selected,
        consent_digest: preview.consent_digest,
        semantic,
      }),
    );
    if (r) {
      setPreview(null);
      setSelected([]);
      setNotice(
        "Selected-turn extraction queued. New memories remain proposals.",
      );
    }
  }
  return (
    <section className="personal-brain">
      <div className="page-heading">
        <div>
          <span className="eyebrow">PERSONAL BRAIN</span>
          <h2>Keep what you learn.</h2>
        </div>
        <button
          disabled={working}
          onClick={() =>
            perform(() => send(`/repositories/${project}/memory/refresh`, {}))
          }
        >
          Refresh private graph
        </button>
      </div>
      <p>
        Private to this repository’s local operator. Only accepted memories are
        available to chat through FalkorDB. Review preserves evidence; it does
        not create a binding code policy.
      </p>
      {error && (
        <p className="failure" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="coverage" role="status">
          {notice}
        </p>
      )}
      <div className="coverage">
        <p>
          Company links resolve explicit code identifiers and verified source
          matches. For example: <code>`retry.delay_ms`</code>. This grants this
          local operator company-read access for memory traversal; team readers
          keep their existing permissions.
        </p>
        <button
          disabled={working}
          onClick={() =>
            perform(() =>
              send(`/repositories/${project}/memory/company-bridge`, {
                enabled: !companyEnabled,
              }),
            )
          }
        >
          {companyEnabled
            ? "Disconnect company evidence"
            : "Connect company evidence"}
        </button>
      </div>
      <details className="conversation-import">
        <summary>Transfer selected memories from another repository</summary>
        <p>
          Copies selected accepted private memories into this repository as
          proposals. Original snapshots are included in the exact preview.
          Copies are independent; later source revocation does not revoke an
          accepted destination copy.
        </p>
        <label>
          Source repository
          <select
            aria-label="Transfer source repository"
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
          >
            <option value="">Choose repository…</option>
            {repositories
              .filter((r) => r.id !== project && r.status === "ready")
              .map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
          </select>
        </label>
        {transferItems.map((item) => (
          <label className="source-selection" key={item.uid}>
            <input
              type="checkbox"
              checked={transferSelected.includes(item.uid)}
              onChange={(e) => {
                setTransferSelected((v) =>
                  e.target.checked
                    ? [...v, item.uid]
                    : v.filter((id) => id !== item.uid),
                );
                setTransferPreview(null);
              }}
            />
            {item.text}
          </label>
        ))}
        <button
          disabled={
            working || !transferSelected.length || transferSelected.length > 10
          }
          onClick={prepareTransfer}
        >
          Preview repository transfer
        </button>
        {transferPreview && (
          <div>
            <pre>{JSON.stringify(transferPreview, null, 2)}</pre>
            <button disabled={working} onClick={confirmTransfer}>
              Confirm exact transfer as proposals
            </button>
          </div>
        )}
      </details>
      <div className="memory-layout">
        <div>
          <form className="memory-create" onSubmit={add}>
            <label htmlFor="memory-note">
              Add a decision, preference or lesson
            </label>
            <textarea
              id="memory-note"
              required
              maxLength={4000}
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
            <button className="primary" disabled={working || !note.trim()}>
              Propose private memory
            </button>
          </form>
          <details className="conversation-import">
            <summary>Extract from selected conversation turns</summary>
            <p>
              Choose user turns from the current conversation. Assistant answers
              are excluded. Nothing is imported until you review and confirm the
              exact preview.
            </p>
            <form onSubmit={prepare}>
              <div className="source-selections">
                {turns
                  .filter((t) => t.status === "complete")
                  .map((t) => (
                    <label key={t.id}>
                      <input
                        type="checkbox"
                        checked={selected.includes(t.id)}
                        onChange={(e) => {
                          setSelected((v) =>
                            e.target.checked
                              ? [...v, t.id]
                              : v.filter((id) => id !== t.id),
                          );
                          setPreview(null);
                        }}
                      />
                      {t.question}
                    </label>
                  ))}
              </div>
              <button
                disabled={
                  !session || !selected.length || working || activeImport
                }
              >
                Preview selected turns
              </button>
            </form>
            {preview && (
              <div>
                <pre>
                  {preview.payload.turns.map((t) => t.text).join("\n\n")}
                </pre>
                <label>
                  <input
                    type="checkbox"
                    checked={semantic}
                    onChange={(e) => setSemantic(e.target.checked)}
                  />{" "}
                  Use the configured Codex model to select durable spans. Sends
                  only this previewed text and consumes account usage.
                </label>
                <p>
                  Without model selection, non-question user lines become
                  verbatim proposals.
                </p>
                <button
                  className="primary"
                  disabled={working || activeImport}
                  onClick={importTurns}
                >
                  Confirm exact selection and extract proposals
                </button>
              </div>
            )}
            {imports.at(-1) && (
              <p role="status">
                {imports.at(-1).stage}
                {imports.at(-1).error ? `: ${imports.at(-1).error}` : ""}
              </p>
            )}
          </details>
          <h3>Memories awaiting review and accepted lessons</h3>
          {!items.length && (
            <p>
              No memories yet. Add a private note or send a completed coding
              lesson here for review.
            </p>
          )}
          {truncated && (
            <p className="coverage">Showing the latest 100 records.</p>
          )}
          <div className="memory-list">
            {items.map((item) => (
              <button
                key={item.uid}
                className={detail?.uid === item.uid ? "selected" : ""}
                onClick={() => inspect(item)}
              >
                <span className={`memory-state ${item.state}`}>
                  {item.state}
                </span>
                <span>{item.text}</span>
                <small>
                  {item.collection === "coding-lessons"
                    ? "Coding lesson"
                    : item.collection?.startsWith("conversation:")
                      ? "Selected conversation"
                      : "Operator note"}
                </small>
              </button>
            ))}
          </div>
          {relationships.length > 0 && (
            <details>
              <summary>Correction and relationship proposals</summary>
              {relationships.map((r) => (
                <p key={r.uid}>
                  {r.source_uid} → {r.relation} → {r.target_uid} · {r.state}
                </p>
              ))}
              <p>
                Relationships have separate review state. Accepting a memory
                does not accept a proposed correction.
              </p>
            </details>
          )}
        </div>
        <aside className="memory-inspector">
          {detail ? (
            <>
              <span className="eyebrow">REVIEW MEMORY</span>
              <h3>{detail.state}</h3>
              <p>{detail.text}</p>
              <h4>Original source</h4>
              {detail.source_error && (
                <p className="failure">{detail.source_error}</p>
              )}
              {detail.sources.map((s) => (
                <details key={s.uri} open>
                  <summary>
                    {s.kind === "lesson"
                      ? "Coding report and proposed lesson"
                      : s.kind === "note"
                        ? "Original operator note"
                        : s.kind === "transfer"
                          ? "Selected repository transfer snapshot"
                          : "Selected user turn"}
                  </summary>
                  <SourceRecord source={s} />
                </details>
              ))}
              {(detail.state === "proposed" || detail.state === "accepted") && (
                <div className="memory-review">
                  <label htmlFor="review-reason">Review reason</label>
                  <textarea
                    id="review-reason"
                    maxLength={1000}
                    rows={2}
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                  {detail.state === "proposed" ? (
                    <div>
                      <button
                        className="primary"
                        disabled={
                          working || !reason.trim() || !!detail.source_error
                        }
                        onClick={() => review("accept")}
                      >
                        Accept memory
                      </button>
                      <button
                        disabled={working || !reason.trim()}
                        onClick={() => review("reject")}
                      >
                        Reject memory
                      </button>
                    </div>
                  ) : (
                    <button
                      disabled={working || !reason.trim()}
                      onClick={() => review("rollback")}
                    >
                      Revoke acceptance
                    </button>
                  )}
                </div>
              )}
              <details>
                <summary>Review history</summary>
                {detail.reviews.map((r, i) => (
                  <p key={i}>
                    {r.action} · {r.actor} · {new Date(r.at).toLocaleString()}
                    <br />
                    {JSON.parse(r.detail).reason}
                  </p>
                ))}
              </details>
            </>
          ) : (
            <p>Select a memory to inspect its source and review it.</p>
          )}
        </aside>
      </div>
      <details className="private-graph">
        <summary>
          Private memory graph · includes proposals for your review
        </summary>
        {graph?.status === "ok" ? (
          renderGraph(graph.graph)
        ) : (
          <p>{graph?.warnings?.join("; ") || "No private graph yet."}</p>
        )}
        {graph?.status === "ok" && graph.warnings?.length > 0 && (
          <p className="coverage">{graph.warnings.join("; ")}</p>
        )}
        {graph?.graph?.truncated && (
          <p>Graph view is bounded to 150 nodes and 300 edges.</p>
        )}
      </details>
    </section>
  );
}
