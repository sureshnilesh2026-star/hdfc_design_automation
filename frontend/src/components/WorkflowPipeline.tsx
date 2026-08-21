import { Link } from "react-router-dom";
import type { ExecutionStage, WorkflowStage } from "../lib/api";
import { formatMs } from "../lib/format";
import { statusLabel } from "../lib/status";
import { StatusBadge } from "./ui";

type Node = {
  agent_id: string;
  name: string;
  status?: string | null;
  duration_ms?: number | null;
  note?: string | null;
  kind?: string;
};

export function WorkflowPipeline({
  nodes,
  hrefFor,
}: {
  nodes: Array<WorkflowStage | ExecutionStage | Node>;
  hrefFor?: (id: string) => string | undefined;
}) {
  return (
    <ol className="ao-pipeline">
      {nodes.map((node, index) => {
        const href = node.kind === "anchor" ? undefined : hrefFor?.(node.agent_id);
        const mark = (node.status || "unknown").toLowerCase();
        const body = (
          <>
            <span className="ao-pipeline__rail" aria-hidden="true">
              <span className={`ao-pipeline__mark ao-pipeline__mark--${mark}`} />
              {index < nodes.length - 1 ? <span className="ao-pipeline__line" /> : null}
            </span>
            <span>
              <strong>{node.name}</strong>
              <div style={{ fontSize: 12, color: "var(--text-subtle)", marginTop: 4 }}>
                {"note" in node && node.note ? node.note : statusLabel(node.status)}
              </div>
            </span>
            <span>
              <StatusBadge status={node.status} />
              {"duration_ms" in node && node.duration_ms != null ? (
                <div style={{ fontSize: 12, marginTop: 6, textAlign: "right" }}>{formatMs(node.duration_ms)}</div>
              ) : null}
            </span>
          </>
        );
        return (
          <li key={node.agent_id}>
            {href ? (
              <Link className="ao-pipeline__node" to={href}>
                {body}
              </Link>
            ) : (
              <div className="ao-pipeline__node">{body}</div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
