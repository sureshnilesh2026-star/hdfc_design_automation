import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, ErrorPanel, LoadingBlock, Metric, PageHeader, StatusBadge } from "../components/ui";
import { WorkflowPipeline } from "../components/WorkflowPipeline";
import { api } from "../lib/api";
import { formatNumber } from "../lib/format";

const INGESTION = [
  "upload",
  "parse",
  "chunk",
  "tag",
  "version",
  "embed",
  "index",
  "approve",
  "available",
];

export function KnowledgePage() {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Record<string, unknown>>("/api/knowledge/stats")
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : "Knowledge stats unavailable."));
  }, []);

  if (error) return <ErrorPanel title="Knowledge repository unavailable" body={error} />;
  if (!stats) return <LoadingBlock />;

  const nodes = INGESTION.map((stage) => ({
    agent_id: stage,
    name: stage.replace(/^./, (c) => c.toUpperCase()),
    status: stage === "embed" ? "not_implemented" : "completed",
    note: stage === "embed" ? "Vector embedding is not yet instrumented." : "Available for bundled knowledge files",
  }));

  return (
    <>
      <PageHeader
        title="Knowledge repository"
        description="Documents shipped in Knowledge_Base plus files uploaded through AgentOps. Retrieval is keyword-based until embedding is instrumented."
        actions={<Link className="ao-btn ao-btn--secondary" to="/documents">Open documents</Link>}
      />
      <div className="ao-grid ao-grid--metrics" style={{ marginBottom: 24 }}>
        <Card>
          <Metric label="Documents indexed" value={formatNumber(stats.documents_indexed as number)} />
        </Card>
        <Card>
          <Metric label="Uploaded" value={formatNumber(stats.documents_uploaded as number)} />
        </Card>
        <Card>
          <Metric label="Processed" value={formatNumber(stats.documents_processed as number)} />
        </Card>
        <Card>
          <Metric label="Failed" value={formatNumber(stats.failed_documents as number)} />
        </Card>
        <Card>
          <Metric label="Retrieval" value={String(stats.retrieval_method)} note="Embedding not instrumented" />
        </Card>
        <Card>
          <StatusBadge status={stats.healthy ? "healthy" : "unavailable"} />
        </Card>
      </div>
      <Card title="Ingestion pipeline">
        <WorkflowPipeline nodes={nodes} />
      </Card>
    </>
  );
}
