import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Activity, ArrowUpRight, X } from "lucide-react";
import { api } from "./api";

const kindLabels = {
  action: "Fix agent",
  investigation: "Investigation",
  repository: "Repository indexing",
  enrichment: "Document indexing",
  documentation_draft: "Documentation",
  workflow: "Auto-investigate",
  documentation_patch: "Document patch",
};

export function LiveWorkSurface({ items, error, truncated, onNavigate }) {
  const [dismissed, setDismissed] = useState("");
  const banner = useRef(null);
  const popup = useRef(null);
  const signature = items
    .map((item) => item.id)
    .sort()
    .join(":");
  const open = !!signature && dismissed !== signature;
  const close = () => {
    setDismissed(signature);
    banner.current?.focus();
  };
  useEffect(() => {
    if (!open) return;
    // Modeless: keep the workspace usable, and leave focus with the user's task.
    const keys = (event) => {
      if (
        event.key === "Escape" &&
        !event.defaultPrevented &&
        !document.querySelector('dialog[open], [aria-modal="true"]')
      ) {
        event.preventDefault();
        setDismissed(signature);
        if (popup.current?.contains(document.activeElement))
          banner.current?.focus();
      }
    };
    document.addEventListener("keydown", keys);
    return () => document.removeEventListener("keydown", keys);
  }, [open, signature]);
  if (!items.length && !error) return null;
  return (
    <>
      <section
        className={`live-work-banner ${error ? "updates-paused" : ""}`}
        aria-label="Workspace activity"
      >
        <span className="working-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <div role="status">
          <strong>
            {error
              ? "Activity updates paused"
              : `${items.length} ${items.length === 1 ? "task" : "tasks"} live`}
          </strong>
          <span>{error || items[0]?.stage}</span>
        </div>
        {!!items.length && (
          <button
            ref={banner}
            aria-expanded={open}
            aria-controls="live-work-popup"
            onClick={() => setDismissed(open ? signature : "")}
          >
            {open ? "Minimize" : "Show activity"} <ArrowUpRight size={16} />
          </button>
        )}
      </section>
      {open &&
        createPortal(
          <section
            ref={popup}
            id="live-work-popup"
            className={`live-work-popup ${error ? "updates-paused" : ""}`}
            role="dialog"
            aria-modal="false"
            aria-labelledby="live-work-title"
          >
            <header>
              <span className="live-work-kicker">
                <Activity size={16} /> LIVE WORKSPACE
              </span>
              <button onClick={close} aria-label="Minimize live activity">
                <X size={20} />
              </button>
            </header>
            <h2 id="live-work-title">
              {error ? "Updates paused." : "Here’s what’s happening."}
            </h2>
            <p>
              Keep working here. Minimize this window to follow progress in the
              red banner.
            </p>
            {error && (
              <p role="alert">{error} · Showing the last received state.</p>
            )}
            <div className="live-work-tasks">
              {items.map((item) => (
                <article key={item.id}>
                  <span className="live-work-kicker">
                    {kindLabels[item.kind] || item.kind} · {item.status}
                  </span>
                  <h3>{item.stage}</h3>
                  <p>{item.title}</p>
                  {onNavigate &&
                    ["action", "investigation"].includes(item.kind) && (
                      <button
                        onClick={() => {
                          close();
                          onNavigate(item);
                        }}
                      >
                        Follow this task <ArrowUpRight size={15} />
                      </button>
                    )}
                </article>
              ))}
            </div>
            {truncated && <p>Showing the first 50 active tasks.</p>}
            <footer>
              <span className="working-dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              {error
                ? "Waiting to reconnect"
                : "Real job states · refreshes every 3 seconds"}
            </footer>
          </section>,
          document.body,
        )}
    </>
  );
}

export default function LiveWork({ project, onNavigate }) {
  const [value, setValue] = useState({ project, items: [] });
  useEffect(() => {
    if (!project) return;
    let live = true,
      timer;
    const controller = new AbortController();
    async function refresh() {
      try {
        const next = await api(`/repositories/${project}/activity`, {
          signal: controller.signal,
        });
        if (live) setValue({ project, ...next, error: "" });
      } catch (error) {
        if (live)
          setValue((previous) => ({
            ...previous,
            project,
            error: error.message,
          }));
      } finally {
        if (live) timer = setTimeout(refresh, 3000);
      }
    }
    refresh();
    return () => {
      live = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [project]);
  return (
    <LiveWorkSurface
      key={project}
      items={value.project === project ? value.items : []}
      error={value.project === project ? value.error : ""}
      truncated={value.truncated}
      onNavigate={onNavigate}
    />
  );
}
