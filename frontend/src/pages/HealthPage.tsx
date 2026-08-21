import { useEffect, useState } from "react";
import { Card, ErrorPanel, LoadingBlock, PageHeader, StatusBadge } from "../components/ui";
import { api, type HealthComponent } from "../lib/api";

type HealthPayload = {
  overall: string;
  uptime_seconds: number;
  note: string;
  components: HealthComponent[];
  agents: Array<{ agent_id: string; name: string; status: string; note?: string }>;
};

export function HealthPage() {
  const [data, setData] = useState<HealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<HealthPayload>("/api/health")
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Health is unavailable."));
  }, []);

  if (error) return <ErrorPanel title="System health unavailable" body={error} />;
  if (!data) return <LoadingBlock />;

  return (
    <>
      <PageHeader
        title="System health"
        description="Unknown means there is no telemetry. It is not treated as healthy."
        actions={<StatusBadge status={data.overall} />}
      />
      <div className="ao-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", marginBottom: 24 }}>
        {data.components.map((item) => (
          <Card key={item.component}>
            <StatusBadge status={item.status} />
            <h3 style={{ marginTop: 12, textTransform: "capitalize" }}>{item.component.replaceAll("_", " ")}</h3>
            <p style={{ color: "var(--text-subtle)", marginTop: 8 }}>{item.note}</p>
          </Card>
        ))}
      </div>
      <Card title="Agents">
        <div className="ao-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
          {data.agents.map((agent) => (
            <div key={agent.agent_id}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <strong>{agent.name}</strong>
                <StatusBadge status={agent.status} />
              </div>
              <p style={{ fontSize: 13, color: "var(--text-subtle)" }}>{agent.note}</p>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}
