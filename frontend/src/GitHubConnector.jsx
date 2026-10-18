import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { GitBranch, X } from "lucide-react";
import { api, send } from "./api";

const empty = {
  kind: "issue",
  title: "",
  body: "",
  number: "",
  head: "",
  base: "",
};
const labels = {
  issue: "issue",
  pull_request: "draft pull request",
  comment: "comment",
};

export default function GitHubConnector({ project, latestTurn }) {
  const [open, setOpen] = useState(false);
  const [connection, setConnection] = useState(null);
  const [history, setHistory] = useState([]);
  const [form, setForm] = useState(empty);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const dialog = useRef(null);
  const preview = useRef(null);
  const trigger = useRef(null);
  const route = `/repositories/${project}/github/actions`;

  useEffect(() => {
    if (draft) {
      preview.current?.focus({ preventScroll: true });
      preview.current?.scrollIntoView({ block: "nearest" });
    }
  }, [draft?.id, draft?.status]);

  async function refresh() {
    setError("");
    try {
      const [account, recent] = await Promise.all([
        api("/github/connection"),
        api(route),
      ]);
      setConnection(account);
      setHistory(recent.items.slice().reverse());
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    if (!open) return;
    refresh();
    const node = dialog.current;
    node?.focus();
    function keys(event) {
      if (event.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
      if (event.key !== "Tab") return;
      const items = Array.from(
        node.querySelectorAll("button, input, textarea, select, a[href]"),
      ).filter(
        (item) => !item.matches(":disabled") && item.getClientRects().length,
      );
      const first = items[0],
        last = items.at(-1);
      if (
        event.shiftKey &&
        (document.activeElement === first || document.activeElement === node)
      ) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    node?.addEventListener("keydown", keys);
    return () => node?.removeEventListener("keydown", keys);
  }, [open, project]);

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
    setDraft(null);
  }
  async function review(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const value = {
        ...form,
        number: form.kind === "comment" ? Number(form.number) : null,
      };
      setDraft(await send(route, value));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function publish() {
    setBusy(true);
    setError("");
    try {
      const result = await send(`${route}/${draft.id}/publish`, {
        consent_digest: draft.consent_digest,
      });
      setDraft(result);
      setHistory((items) => [
        result,
        ...items.filter((item) => item.id !== result.id),
      ]);
    } catch (e) {
      setError(e.message);
      // Retain the persisted outcome rather than inviting a duplicate write.
      try {
        const recent = await api(route);
        setHistory(recent.items.slice().reverse());
        const current = recent.items.find((item) => item.id === draft.id);
        setDraft(current || { ...draft, status: "unknown" });
      } catch {
        setDraft({ ...draft, status: "unknown" });
      }
    } finally {
      setBusy(false);
    }
  }
  function useAnswer() {
    setForm((current) => ({
      ...current,
      title: (latestTurn.question || "").slice(0, 256),
      body: (latestTurn.claims || [])
        .map((claim) => claim.text)
        .join("\n\n")
        .slice(0, 60000),
    }));
    setDraft(null);
  }
  return (
    <>
      <button ref={trigger} onClick={() => setOpen(true)}>
        <GitBranch size={15} /> GitHub
        {latestTurn?.github_drafts?.length
          ? ` · ${latestTurn.github_drafts.length} draft(s)`
          : ""}
      </button>
      {open &&
        createPortal(
          <div className="modal-backdrop">
            <section
              className="modal github-connector"
              role="dialog"
              aria-modal="true"
              aria-label="GitHub connector"
              tabIndex={-1}
              ref={dialog}
            >
              <button
                className="modal-close"
                aria-label="Close GitHub connector"
                onClick={() => {
                  setOpen(false);
                  trigger.current?.focus();
                }}
              >
                <X size={20} />
              </button>
              <h2>GitHub</h2>
              <p>
                Create an issue, open a draft pull request, or comment on an
                issue or PR.
              </p>
              {connection?.connected ? (
                <p>
                  Connected as <strong>{connection.login}</strong>.
                </p>
              ) : (
                <>
                  <p>{connection?.error || "Checking GitHub connection…"}</p>
                  {connection && (
                    <p>
                      On the computer running Company Brain, run{" "}
                      <code>{connection.setup}</code>, then check the connection
                      again.
                    </p>
                  )}
                </>
              )}
              <button disabled={busy} onClick={refresh}>
                Check connection
              </button>
              {error && (
                <p className="failure" role="alert">
                  {error}
                </p>
              )}
              <form onSubmit={review}>
                <fieldset
                  disabled={
                    busy ||
                    !connection?.connected ||
                    draft?.status === "published"
                  }
                >
                  <label>
                    Action
                    <select
                      value={form.kind}
                      onChange={(e) => update("kind", e.target.value)}
                    >
                      <option value="issue">Create issue</option>
                      <option value="pull_request">Open draft PR</option>
                      <option value="comment">Add comment</option>
                    </select>
                  </label>
                  {form.kind !== "comment" && (
                    <label>
                      Title
                      <input
                        required
                        maxLength={256}
                        value={form.title}
                        onChange={(e) => update("title", e.target.value)}
                      />
                    </label>
                  )}
                  {form.kind === "comment" && (
                    <label>
                      Issue or PR number
                      <input
                        required
                        type="number"
                        min="1"
                        max="1000000000"
                        value={form.number}
                        onChange={(e) => update("number", e.target.value)}
                      />
                    </label>
                  )}
                  {form.kind === "pull_request" && (
                    <>
                      <label>
                        Existing head branch
                        <input
                          required
                          placeholder="feature-branch or owner:feature-branch"
                          value={form.head}
                          onChange={(e) => update("head", e.target.value)}
                        />
                      </label>
                      <label>
                        Base branch
                        <input
                          placeholder="Repository default branch"
                          value={form.base}
                          onChange={(e) => update("base", e.target.value)}
                        />
                      </label>
                      <p>
                        Push your changes to the head branch first. This opens a
                        PR between existing GitHub branches; it does not upload
                        the isolated patch.
                      </p>
                    </>
                  )}
                  <label>
                    Body
                    <textarea
                      required
                      rows={7}
                      maxLength={60000}
                      value={form.body}
                      onChange={(e) => update("body", e.target.value)}
                    />
                  </label>
                  {!!latestTurn?.claims?.length && (
                    <button type="button" onClick={useAnswer}>
                      Use latest answer
                    </button>
                  )}
                  <button
                    type="submit"
                    disabled={busy || !connection?.connected}
                  >
                    Review draft
                  </button>
                </fieldset>
              </form>
              {draft && (
                <div
                  className="github-preview"
                  role="status"
                  ref={preview}
                  tabIndex={-1}
                >
                  <h3>
                    {draft.status === "published"
                      ? "Published"
                      : "Review publication"}
                  </h3>
                  <p>
                    Publish as <strong>{draft.login}</strong> to{" "}
                    <strong>{draft.repository}</strong>.
                  </p>
                  {draft.payload.title && <h4>{draft.payload.title}</h4>}
                  {draft.operation === "comment" && (
                    <p>On issue or PR #{draft.endpoint.split("/").at(-2)}</p>
                  )}
                  {draft.operation === "pull_request" && (
                    <p>
                      {draft.payload.head} → {draft.payload.base} · Draft PR
                    </p>
                  )}
                  <pre>{draft.payload.body}</pre>
                  {draft.status === "draft" && (
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={publish}
                    >
                      {busy
                        ? "Publishing…"
                        : `Publish ${labels[draft.operation]}`}
                    </button>
                  )}
                  {draft.url && (
                    <a href={draft.url} target="_blank" rel="noreferrer">
                      Open on GitHub
                    </a>
                  )}
                  {["unknown", "publishing"].includes(draft.status) && (
                    <p>
                      Inspect the repository on GitHub before trying again; this
                      request may have succeeded.
                    </p>
                  )}
                  {draft.status === "published" && (
                    <button
                      onClick={() => {
                        setDraft(null);
                        setForm(empty);
                      }}
                    >
                      New GitHub action
                    </button>
                  )}
                </div>
              )}
              {!!history.length && (
                <details>
                  <summary>Recent GitHub actions</summary>
                  <ul>
                    {history.map((item) => (
                      <li key={item.id}>
                        {labels[item.operation]} · {item.status}{" "}
                        {item.url && (
                          <a href={item.url} target="_blank" rel="noreferrer">
                            Open on GitHub
                          </a>
                        )}
                        {item.status === "draft" && (
                          <button
                            disabled={busy}
                            onClick={() => setDraft(item)}
                          >
                            Review
                          </button>
                        )}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </section>
          </div>,
          document.body,
        )}
    </>
  );
}
