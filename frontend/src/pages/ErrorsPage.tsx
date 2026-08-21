import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, EmptyState, ErrorPanel, LoadingBlock, PageHeader, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";

type IncidentPayload = {
  incidents: Array<{
    incident_id: string;
    agent_id: string;
    title: string;
    severity: string;
    failure_count: number;
    last_seen: string;
    sample_message: string;
    sample_execution_id: string;
  }>;
  recent_failures: Array<{
    flow_id: string;
    execution_id: string;
    failed_agent_id: string;
    error_summary: string;
    ended_at: string;
    mode: string;
  }>;
  note?: string | null;
};

export function ErrorsPage() {
  const [data, setData] = useState<IncidentPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<IncidentPayload>("/api/incidents")
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Incidents unavailable."));
  }, []);

  if (error) return <ErrorPanel title="Incident center unavailable" body={error} />;
  if (!data) return <LoadingBlock />;

  return (
    <>
      <PageHeader title="Errors & incidents" description="Failures are never hidden. Open the execution to see exactly where the flow stopped." />
      {data.incidents.length === 0 ? (
        <EmptyState title="No incidents yet" body={data.note || "The platform has not recorded a failed execution."} />
      ) : (
        <div className="ao-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", marginBottom: 24 }}>
          {data.incidents.map((item) => (
            <Card key={item.incident_id}>
              <StatusBadge status={item.severity === "high" ? "failed" : "warning"} label={item.severity} />
              <h3 style={{ marginTop: 12 }}>{item.title}</h3>
              <p style={{ margin: "8px 0" }}>{item.failure_count} failures</p>
              <p style={{ color: "var(--text-subtle)", fontSize: 13 }}>Last seen {formatDate(item.last_seen)}</p>
              <p>{item.sample_message}</p>
              <div className="ao-chip-row" style={{ marginTop: 12 }}>
                <Link className="ao-btn ao-btn--secondary ao-btn--sm" to={`/executions/${item.sample_execution_id}`}>
                  View executions
                </Link>
                <Link className="ao-btn ao-btn--tertiary ao-btn--sm" to={`/agents/${item.agent_id}`}>
                  View agent
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}
      <Card title="Recent failures">
        {data.recent_failures.length === 0 ? (
          <p>None recorded.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 12 }}>
            {data.recent_failures.map((item) => (
              <li key={item.execution_id}>
                <Link to={`/executions/${item.execution_id}`}>{item.flow_id}</Link>
                {item.mode === "demo" ? <span className="ao-demo-banner">Demo</span> : null}
                <div style={{ color: "var(--text-subtle)" }}>
                  {item.failed_agent_id} · {item.error_summary}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
