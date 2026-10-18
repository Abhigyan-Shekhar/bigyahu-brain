import React, { useLayoutEffect, useRef, useState } from "react";
import { ArrowUp, Network } from "lucide-react";
import { promptState, shouldSubmitPrompt } from "./promptPresentation";

export default function PromptComposer({
  value,
  onChange,
  onSubmit,
  context,
  busy,
  ingesting,
  sending,
}) {
  const input = useRef(null);
  const [expanded, setExpanded] = useState(false);
  const state = promptState(value, context);
  const disabled = busy || ingesting || sending;
  useLayoutEffect(() => {
    const element = input.current;
    if (!element) return;
    const resize = () => {
      const scroll = element.scrollTop;
      element.style.height = "auto";
      const maximum = Math.min(
        expanded ? 480 : 240,
        window.innerHeight * (expanded ? 0.55 : 0.32),
      );
      element.style.height = `${Math.max(48, Math.min(element.scrollHeight, maximum))}px`;
      element.style.overflowY =
        element.scrollHeight > maximum ? "auto" : "hidden";
      element.scrollTop = scroll;
    };
    resize();
    let width = element.parentElement.getBoundingClientRect().width;
    const observer = new ResizeObserver((entries) => {
      const next = entries[0].contentRect.width;
      if (next !== width) {
        width = next;
        resize();
      }
    });
    observer.observe(element.parentElement);
    const onResize = () => resize();
    window.addEventListener("resize", onResize);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", onResize);
    };
  }, [value, expanded]);
  return (
    <form
      className={`composer prompt-composer ${expanded ? "prompt-expanded" : ""}`}
      onSubmit={(event) => {
        event.preventDefault();
        if (!disabled && state.valid) onSubmit(event);
      }}
    >
      <div className="prompt-toolbar">
        <label htmlFor="question">Your prompt</label>
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls="question"
          onClick={() => {
            setExpanded(!expanded);
            input.current?.focus();
          }}
        >
          {expanded ? "Compact editor" : "Expand editor"}
        </button>
      </div>
      <textarea
        ref={input}
        id="question"
        placeholder="Ask a question, explore a past approach, or describe a change…"
        rows={2}
        value={value}
        disabled={disabled}
        aria-describedby="prompt-help prompt-length prompt-error"
        aria-invalid={!!state.error}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (shouldSubmitPrompt(event, value)) {
            event.preventDefault();
            if (!disabled && state.valid)
              event.currentTarget.form.requestSubmit();
          }
        }}
      />
      <div
        id="prompt-error"
        className="prompt-validation"
        role={state.error ? "alert" : undefined}
      >
        {state.error}
      </div>
      <div className="composer-bottom">
        <span>
          <span className="scope-pill">
            <Network size={12} /> Company
          </span>
          <small>
            {sending
              ? "Sending…"
              : ingesting
                ? "Building document graph…"
                : busy
                  ? "Investigating…"
                  : "Code · documents · available history"}
          </small>
        </span>
        <span
          id="prompt-length"
          className={state.error ? "prompt-over-limit" : "prompt-count"}
        >
          {state.length.toLocaleString()} / 8,000
          {context ? " incl. graph context" : ""}
        </span>
        <button
          className="submit"
          type="submit"
          aria-label="Send question"
          disabled={disabled || !state.valid}
        >
          <ArrowUp size={18} />
        </button>
      </div>
      <small id="prompt-help" className="prompt-help">
        {value.includes("\n")
          ? "Multiline prompt: Enter adds a line. "
          : "Enter sends · Shift+Enter adds a line. "}
        Ctrl/⌘+Enter sends.
      </small>
    </form>
  );
}
