import React from "react";
import { Handle, Position } from "@xyflow/react";
import {
  Code2,
  FileCode2,
  FileText,
  GitBranch,
  BrainCircuit,
  Network,
} from "lucide-react";
const icons = {
  code: Code2,
  file: FileCode2,
  document: FileText,
  history: GitBranch,
  memory: BrainCircuit,
  entity: Network,
};
export default function KnowledgeNode({ data }) {
  const Icon = icons[data.appearance.icon];
  return (
    <div
      className={`entity-node ${data.cluster ? "entity-cluster" : "entity-detail"} tone-${data.appearance.tone} ${data.emphasized ? "entity-emphasized" : ""}`}
      title={data.fullLabel}
      role="button"
      tabIndex={0}
      aria-label={
        data.cluster
          ? `Open ${data.fullLabel} cluster`
          : `Inspect ${data.fullLabel}`
      }
      onClick={(event) => {
        event.stopPropagation();
        data.onActivate?.();
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          event.stopPropagation();
          data.onActivate?.();
        }
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div className={`entity-glyph shape-${data.appearance.shape}`}>
        <Icon size={data.cluster ? 22 : 17} />
        {data.cluster && <b>{data.count.toLocaleString()}</b>}
      </div>
      <div className="entity-label">
        <strong>
          {data.label.split(/([./])/).map((part, i) => (
            <React.Fragment key={i}>
              {part}
              {/^[./]$/.test(part) && <wbr />}
            </React.Fragment>
          ))}
        </strong>
        <small>
          {data.cluster ? "entities · open cluster" : data.appearance.type}
        </small>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
export const knowledgeNodeTypes = { knowledge: KnowledgeNode };
