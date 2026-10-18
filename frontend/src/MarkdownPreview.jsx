import React from "react";

// The author emits a bounded Markdown subset. React escapes text; raw HTML is never evaluated.
function prose(text, onEvidence) {
  return text.split(/(\[\^source-[a-f0-9]{24}\])/g).map((part, index) => {
    const match = part.match(/^\[\^source-([a-f0-9]{24})\]$/);
    return match ? (
      <button
        className="doc-citation"
        key={index}
        onClick={() => onEvidence?.(match[1])}
      >
        Source {match[1].slice(0, 6)}
      </button>
    ) : (
      part.replace(/\\([\\`*_{}\[\]<>!#|])/g, "$1")
    );
  });
}

export default function MarkdownPreview({ markdown, onEvidence }) {
  const rows = markdown.split("\n"),
    nodes = [];
  let code = null;
  rows.forEach((line, index) => {
    if (line.startsWith("```")) {
      if (code === null) code = [];
      else {
        nodes.push(<pre key={index}>{code.join("\n")}</pre>);
        code = null;
      }
    } else if (code !== null) code.push(line);
    else if (/^\[\^source-/.test(line))
      nodes.push(
        <p className="doc-source" key={index}>
          {prose(line, onEvidence)}
        </p>,
      );
    else if (/^# /.test(line))
      nodes.push(<h2 key={index}>{prose(line.slice(2), onEvidence)}</h2>);
    else if (/^## /.test(line))
      nodes.push(<h3 key={index}>{prose(line.slice(3), onEvidence)}</h3>);
    else if (line.startsWith("- "))
      nodes.push(<p key={index}>• {prose(line.slice(2), onEvidence)}</p>);
    else if (line.trim())
      nodes.push(<p key={index}>{prose(line, onEvidence)}</p>);
  });
  return <article className="markdown-preview">{nodes}</article>;
}
