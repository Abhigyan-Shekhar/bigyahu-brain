import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { BookOpen, X } from "lucide-react";
import { api, send, watchResource } from "./api";
import MarkdownPreview from "./MarkdownPreview";

export function downloadText(text, filename) {
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/plain;charset=utf-8" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function DocumentationPanel({
  project,
  sourceTurn,
  sourceAction,
  documentId,
  label = "Docs",
}) {
  const [open, setOpen] = useState(false),
    [items, setItems] = useState([]),
    [current, setCurrent] = useState(null);
  const [instruction, setInstruction] = useState(""),
    [kind, setKind] = useState("incident"),
    [path, setPath] = useState("");
  const [destination, setDestination] = useState("app_docs"),
    [revision, setRevision] = useState("");
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [patch, setPatch] = useState(null),
    [evidence, setEvidence] = useState(null);
  const dialog = useRef(null),
    trigger = useRef(null);
  const route = `/repositories/${project}/documentation/drafts`;
  async function refresh() {
    setItems((await api(route)).items.slice().reverse());
  }
  async function choose(id) {
    setCurrent(await api(`${route}/${id}`));
    setPatch(null);
    setEvidence(null);
  }
  useEffect(() => {
    if (!open) return;
    refresh().catch((e) => setError(e.message));
    if (documentId) choose(documentId).catch((e) => setError(e.message));
    dialog.current?.focus();
    function keys(e) {
      if (e.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
      if (e.key !== "Tab") return;
      const nodes = Array.from(
        dialog.current.querySelectorAll("button,input,textarea,select"),
      ).filter((n) => !n.matches(":disabled") && n.getClientRects().length);
      if (
        e.shiftKey &&
        [nodes[0], dialog.current].includes(document.activeElement)
      ) {
        e.preventDefault();
        nodes.at(-1)?.focus();
      } else if (!e.shiftKey && document.activeElement === nodes.at(-1)) {
        e.preventDefault();
        nodes[0]?.focus();
      }
    }
    dialog.current?.addEventListener("keydown", keys);
    return () => dialog.current?.removeEventListener("keydown", keys);
  }, [open, project]);
  useEffect(() => {
    if (!open || !current || !["queued", "running"].includes(current.status))
      return;
    const base = `${route}/${current.id}`;
    return watchResource(
      `${base}/events`,
      base,
      (value) => {
        setCurrent(value);
        if (!["queued", "running"].includes(value.status))
          refresh().catch(() => {});
      },
      (e) => setError(e.message),
    );
  }, [open, current?.id, current?.status]);
  async function perform(fn) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const consent = current && {
    expected_digest: current.review_digest,
    source_revision: current.source_revision,
  };
  const active = busy || ["queued", "running"].includes(current?.status);
  return (
    <>
      <button ref={trigger} onClick={() => setOpen(true)}>
        <BookOpen size={15} /> {label}
      </button>
      {open &&
        createPortal(
          <div className="modal-backdrop">
            <section
              className="modal authoring-panel"
              role="dialog"
              aria-modal="true"
              aria-label="Company Brain Docs"
              ref={dialog}
              tabIndex={-1}
            >
              <button
                className="modal-close"
                aria-label="Close documentation"
                onClick={() => {
                  setOpen(false);
                  trigger.current?.focus();
                }}
              >
                <X />
              </button>
              <h2>Company Brain Docs</h2>
              <p>
                Create a cited Markdown draft. App Docs and Git repository
                patches are separate destinations.
              </p>
              {error && (
                <p className="failure" role="alert">
                  {error}
                </p>
              )}
              <div className="authoring-layout">
                <aside>
                  <h3>Document versions</h3>
                  <button
                    onClick={() => {
                      setCurrent(null);
                      setPatch(null);
                      setError("");
                    }}
                  >
                    New document
                  </button>
                  {items.map((item) => (
                    <button
                      key={item.id}
                      onClick={() =>
                        choose(item.id).catch((e) => setError(e.message))
                      }
                    >
                      {item.title || item.instruction.slice(0, 60)} ·{" "}
                      {item.status}
                      {item.supersedes ? " · revision" : ""}
                    </button>
                  ))}
                </aside>
                <div>
                  {!current && (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        perform(async () => {
                          setCurrent(
                            await send(route, {
                              kind,
                              instruction,
                              destination,
                              proposed_repo_path: path || null,
                              source_turn_id: sourceTurn?.id || null,
                              source_action_id: sourceAction?.id || null,
                            }),
                          );
                        });
                      }}
                    >
                      <label>
                        Document type
                        <select
                          value={kind}
                          onChange={(e) => setKind(e.target.value)}
                        >
                          {[
                            "architecture",
                            "runbook",
                            "incident",
                            "adr",
                            "api_guide",
                            "change_summary",
                            "custom",
                          ].map((value) => (
                            <option key={value}>{value}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        What should it document?
                        <textarea
                          required
                          maxLength={8000}
                          rows={4}
                          value={instruction}
                          onChange={(e) => setInstruction(e.target.value)}
                        />
                      </label>
                      {sourceTurn && (
                        <p>Source investigation: {sourceTurn.question}</p>
                      )}
                      {sourceAction && (
                        <p>Source patch run: {sourceAction.id}</p>
                      )}
                      <label>
                        Destination
                        <select
                          value={destination}
                          onChange={(e) => setDestination(e.target.value)}
                        >
                          <option value="app_docs">App Docs</option>
                          <option value="repo_patch">
                            Git repository docs/ patch
                          </option>
                        </select>
                      </label>
                      <label>
                        Proposed Markdown path (optional)
                        <input
                          maxLength={180}
                          placeholder="docs/incidents/recovery.md"
                          value={path}
                          onChange={(e) => setPath(e.target.value)}
                        />
                      </label>
                      <button className="primary" disabled={active}>
                        Generate cited draft
                      </button>
                    </form>
                  )}
                  {current && (
                    <>
                      <p role="status">
                        <strong>{current.stage || current.status}</strong>
                      </p>
                      {current.error && (
                        <p className="failure">{current.error}</p>
                      )}
                      {current.markdown && (
                        <>
                          <p>
                            {current.proposed_repo_path} · revision{" "}
                            {current.source_revision?.slice(0, 8)} ·{" "}
                            {current.status === "approved"
                              ? "Saved to App Docs"
                              : "Unapproved draft"}
                          </p>
                          <p>
                            {current.stale
                              ? "Stale evidence: regenerate before approval or export."
                              : "Source provenance checked; interpretation reviewed by a fallible model."}{" "}
                            Generated documentation is advisory.
                          </p>
                          <MarkdownPreview
                            markdown={current.markdown}
                            onEvidence={(id) =>
                              api(`${route}/${current.id}/evidence/${id}`)
                                .then(setEvidence)
                                .catch((e) => setError(e.message))
                            }
                          />
                          {evidence && (
                            <details open>
                              <summary>
                                Checked source: {evidence.title}
                              </summary>
                              <pre>{evidence.text}</pre>
                              <p>
                                {evidence.graph?.nodes?.length || 0} graph nodes
                                · {evidence.graph?.edges?.length || 0}{" "}
                                relationships
                              </p>
                            </details>
                          )}
                          <details>
                            <summary>Markdown source</summary>
                            <pre>{current.markdown}</pre>
                          </details>
                          {current.diff != null && (
                            <details>
                              <summary>
                                Diff from current repository file
                              </summary>
                              <pre>{current.diff || "No text changes"}</pre>
                            </details>
                          )}
                          <div className="authoring-actions">
                            <button
                              onClick={() =>
                                downloadText(
                                  current.markdown,
                                  current.proposed_repo_path.split("/").at(-1),
                                )
                              }
                            >
                              Download .md
                            </button>
                            <button
                              disabled={
                                active ||
                                current.stale ||
                                current.status === "approved"
                              }
                              onClick={() =>
                                perform(async () => {
                                  await send(
                                    `${route}/${current.id}/approve`,
                                    consent,
                                  );
                                  await choose(current.id);
                                })
                              }
                            >
                              Approve & save to App Docs
                            </button>
                            <button
                              disabled={active || current.stale}
                              onClick={() =>
                                perform(async () =>
                                  setPatch(
                                    await send(
                                      `${route}/${current.id}/prepare-patch`,
                                      consent,
                                    ),
                                  ),
                                )
                              }
                            >
                              Prepare repository docs/ patch
                            </button>
                            {current.status === "approved" && (
                              <button
                                disabled={
                                  active ||
                                  current.stale ||
                                  !!current.indexing_result
                                }
                                onClick={() =>
                                  perform(async () => {
                                    await send(
                                      `${route}/${current.id}/index-approved`,
                                      consent,
                                    );
                                    await choose(current.id);
                                  })
                                }
                              >
                                {current.indexing_result
                                  ? "Indexed as reviewed generated document"
                                  : "Index approved App Doc"}
                              </button>
                            )}
                          </div>
                          <form
                            onSubmit={(e) => {
                              e.preventDefault();
                              perform(async () => {
                                setCurrent(
                                  await send(`${route}/${current.id}/revise`, {
                                    instruction: revision,
                                    expected_digest: current.review_digest,
                                  }),
                                );
                                setPatch(null);
                              });
                            }}
                          >
                            <label>
                              Revise this document
                              <textarea
                                required
                                rows={2}
                                maxLength={8000}
                                value={revision}
                                onChange={(e) => setRevision(e.target.value)}
                                placeholder="Describe the changes. The revised version needs new review."
                              />
                            </label>
                            <button disabled={active}>
                              Generate revised draft
                            </button>
                          </form>
                        </>
                      )}
                      {patch && (
                        <div className="github-preview">
                          <h3>Repository Markdown patch · {patch.status}</h3>
                          <p>{patch.notice}</p>
                          <pre>{patch.patch}</pre>
                          {patch.status === "awaiting_approval" && (
                            <button
                              disabled={busy}
                              onClick={() =>
                                perform(async () =>
                                  setPatch(
                                    await send(
                                      `${route}/${current.id}/patches/${patch.id}/approve`,
                                      {
                                        expected_digest: patch.consent_digest,
                                        source_revision: patch.source_revision,
                                      },
                                    ),
                                  ),
                                )
                              }
                            >
                              Approve exact patch export
                            </button>
                          )}
                          {patch.status === "complete" && (
                            <button
                              onClick={() =>
                                downloadText(
                                  patch.patch,
                                  `documentation-${patch.id}.patch`,
                                )
                              }
                            >
                              Download approved patch
                            </button>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </section>
          </div>,
          document.body,
        )}
    </>
  );
}
