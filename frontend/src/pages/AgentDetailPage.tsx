import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Alert,
  Card,
  CopyButton,
  ErrorPanel,
  JsonBlock,
  LoadingBlock,
  Metric,
  PageHeader,
  StatusBadge,
  Tabs,
  TelemetryValue,
} from "../components/ui";
import { api, type AgentRecord } from "../lib/api";
import { formatDate, formatMs, formatPct } from "../lib/format";

export function AgentDetailPage() {
  const { agentId = "" } = useParams();
  const [agent, setAgent] = useState<AgentRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("overview");

  useEffect(() => {
    setAgent(null);
    api<AgentRecord>(`/api/agents/${agentId}`)
      .then(setAgent)
      .catch((err) => setError(err instanceof Error ? err.message : "This agent could not be loaded."));
  }, [agentId]);

  if (error) {
    return (
      <ErrorPanel
        title="Agent unavailable"
        body={error}
        onRetry={() => {
          setError(null);
          api<AgentRecord>(`/api/agents/${agentId}`).then(setAgent).catch((err) => setError(err.message));
        }}
      />
    );
  }
  if (!agent) return <LoadingBlock />;

  const metrics = agent.metrics as Record<string, unknown>;
  const health = agent.health as Record<string, unknown>;
  const developing = agent.lifecycle === "in_development";
  const latest = agent.latest_execution as
    | {
        flow_id: string;
        execution_id: string;
        input?: unknown;
        output?: unknown;
        error?: { message?: string; type?: string; recovery?: string } | null;
        duration_ms?: number;
        mode?: string;
      }
    | null;

  return (
    <>
      <PageHeader
        title={agent.name}
        description={agent.description}
        actions={<StatusBadge status={agent.status} label={agent.status_label} />}
      />
      {developing ? (
        <Alert tone="info" title="In development">
          Runtime is not available. Executions, success rate, and latency stay empty until this agent is implemented.
        </Alert>
      ) : null}
      <div style={{ margin: "20px 0" }}>
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { id: "overview", label: "Overview" },
            { id: "performance", label: "Performance" },
            { id: "io", label: "Input & output" },
            { id: "errors", label: "Errors" },
          ]}
        />
      </div>
      {tab === "overview" ? (
        <div className="ao-grid ao-grid--metrics">
          <Card>
            <Metric label="Version" value={agent.version || "—"} />
          </Card>
          <Card>
            <Metric label="Environment" value={agent.environment} />
          </Card>
          <Card>
            <Metric label="Last heartbeat" value={formatDate(agent.last_heartbeat)} />
          </Card>
          <Card>
            <Metric label="Uptime" value={agent.uptime_seconds != null ? formatMs((agent.uptime_seconds as number) * 1000) : "—"} />
          </Card>
          <Card>
            <Metric label="Runtime" value={String(health.runtime ?? (developing ? "Not available" : "—"))} note={String(health.note ?? "")} />
          </Card>
          <Card>
            <Metric label="Purpose" value={<span style={{ fontSize: 16 }}>{agent.purpose}</span>} />
          </Card>
        </div>
      ) : null}
      {tab === "performance" ? (
        <div className="ao-grid ao-grid--metrics">
          <Card>
            <Metric label="Executions" value={<TelemetryValue value={metrics.total_executions} />} />
          </Card>
          <Card>
            <Metric label="Success rate" value={formatPct(metrics.success_rate as number | null)} />
          </Card>
          <Card>
            <Metric label="Failure rate" value={formatPct(metrics.failure_rate as number | null)} />
          </Card>
          <Card>
            <Metric label="Average latency" value={formatMs(metrics.average_latency_ms as number | null)} />
          </Card>
          <Card>
            <Metric label="P50" value={formatMs(metrics.p50_latency_ms as number | null)} />
          </Card>
          <Card>
            <Metric label="P95" value={formatMs(metrics.p95_latency_ms as number | null)} />
          </Card>
          <Card>
            <Metric label="P99" value={formatMs(metrics.p99_latency_ms as number | null)} />
          </Card>
          <p style={{ gridColumn: "1 / -1", color: "var(--text-subtle)" }}>{String(metrics.note ?? "")}</p>
        </div>
      ) : null}
      {tab === "io" ? (
        latest ? (
          <div className="ao-grid ao-grid--2">
            <Card
              title="Input"
              action={<CopyButton text={JSON.stringify(latest.input ?? {}, null, 2)} />}
            >
              {latest.mode === "demo" ? <div className="ao-demo-banner">Demo mode</div> : null}
              <p style={{ margin: "12px 0" }}>Human-readable view of the last recorded input.</p>
              <JsonBlock value={latest.input} />
            </Card>
            <Card
              title="Output"
              action={<CopyButton text={JSON.stringify(latest.output ?? {}, null, 2)} />}
            >
              <JsonBlock value={latest.output} />
              <div style={{ marginTop: 12 }}>
                <Link to={`/executions/${latest.execution_id}`}>Open flow {latest.flow_id}</Link>
              </div>
            </Card>
          </div>
        ) : (
          <Alert tone="info" title="No execution yet">
            Run a workflow to inspect live input and output for this agent.
          </Alert>
        )
      ) : null}
      {tab === "errors" ? (
        (agent.recent_errors?.length ?? 0) === 0 ? (
          <Alert tone="success" title="No recorded errors">
            Failures for this agent will appear here with type, message, trace, and recovery action.
          </Alert>
        ) : (
          <Card>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 16 }}>
              {(agent.recent_errors || []).map((item) => (
                <li key={String(item.execution_id)}>
                  <StatusBadge status="failed" />
                  <strong style={{ marginLeft: 8 }}>{String(item.type || "Error")}</strong>
                  <p>{String(item.message)}</p>
                  <p style={{ fontSize: 13, color: "var(--text-subtle)" }}>
                    Trace {String(item.trace_id)} · {formatDate(String(item.at))}
                  </p>
                  {item.recovery ? <p>Recovery: {String(item.recovery)}</p> : null}
                  <Link to={`/executions/${String(item.execution_id)}`}>View execution</Link>
                </li>
              ))}
            </ul>
          </Card>
        )
      ) : null}
    </>
  );
}
