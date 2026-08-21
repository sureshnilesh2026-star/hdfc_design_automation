import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, ErrorPanel, LoadingBlock, PageHeader, StatusBadge } from "../components/ui";
import { api, type AgentRecord } from "../lib/api";
import { formatMs, formatPct } from "../lib/format";

export function AgentsPage() {
  const [agents, setAgents] = useState<AgentRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ agents: AgentRecord[] }>("/api/agents")
      .then((data) => setAgents(data.agents))
      .catch((err) => setError(err instanceof Error ? err.message : "Agents are unavailable."));
  }, []);

  if (error) return <ErrorPanel title="Agent list unavailable" body={error} />;
  if (!agents) return <LoadingBlock />;

  return (
    <>
      <PageHeader title="Agents" description="Operational agents report live health. Agents still being built are labelled in development and never show invented metrics." />
      <div className="ao-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
        {agents.map((agent) => {
          const metrics = agent.metrics as Record<string, unknown>;
          const unavailable = agent.lifecycle === "in_development" || metrics.availability !== "live";
          return (
            <Card key={agent.agent_id}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <h3>{agent.name}</h3>
                <StatusBadge status={agent.status} label={agent.status_label} />
              </div>
              <p style={{ color: "var(--text-subtle)", margin: "12px 0 16px", minHeight: 40 }}>{agent.purpose}</p>
              <dl style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 13 }}>
                <div>
                  <dt style={{ color: "var(--text-subtle)" }}>Executions</dt>
                  <dd>{unavailable ? "—" : String(metrics.total_executions ?? "—")}</dd>
                </div>
                <div>
                  <dt style={{ color: "var(--text-subtle)" }}>Success</dt>
                  <dd>{unavailable ? "—" : formatPct(metrics.success_rate as number | null)}</dd>
                </div>
                <div>
                  <dt style={{ color: "var(--text-subtle)" }}>Latency</dt>
                  <dd>{unavailable ? "—" : formatMs(metrics.average_latency_ms as number | null)}</dd>
                </div>
                <div>
                  <dt style={{ color: "var(--text-subtle)" }}>Runtime</dt>
                  <dd>{agent.lifecycle === "in_development" ? "Not available" : String((agent.health as { runtime?: string }).runtime ?? "—")}</dd>
                </div>
              </dl>
              {unavailable ? (
                <p style={{ fontSize: 12, color: "var(--text-subtle)", marginTop: 12 }}>
                  {String(metrics.note ?? "Telemetry unavailable")}
                </p>
              ) : null}
              <div style={{ marginTop: 16 }}>
                <Link className="ao-btn ao-btn--secondary ao-btn--sm" to={`/agents/${agent.agent_id}`}>
                  View details
                </Link>
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}
