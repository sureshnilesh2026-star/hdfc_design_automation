import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { WorkflowPipeline } from "../components/WorkflowPipeline";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorPanel,
  LoadingBlock,
  Metric,
  PageHeader,
  StatusBadge,
  TelemetryValue,
} from "../components/ui";
import { api, type Overview } from "../lib/api";
import { formatMs, formatNumber } from "../lib/format";
import { useAuth } from "../context/AuthContext";

export function OverviewPage() {
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [utterance, setUtterance] = useState("I want to change my address");
  const [channel, setChannel] = useState("asknow");
  const [mode, setMode] = useState<"live" | "demo">("live");
  const [starting, setStarting] = useState(false);
  const navigate = useNavigate();
  const { can } = useAuth();

  async function load() {
    setError(null);
    try {
      setData(await api<Overview>("/api/overview"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Overview is unavailable.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  if (error) return <ErrorPanel title="Telemetry temporarily unavailable" body={error} onRetry={load} />;
  if (!data) return <LoadingBlock />;

  const counts = data.agent_counts;
  const exec = data.executions;

  return (
    <>
      <PageHeader
        title="Overview"
        description="A live view of the journey-generation pipeline. Technical detail is one click away."
        actions={
          <Link className="ao-btn ao-btn--secondary" to="/health">
            System health
          </Link>
        }
      />
      <div className="ao-grid ao-grid--metrics" style={{ marginBottom: 24 }}>
        <Card>
          <Metric
            label="System health"
            value={<StatusBadge status={data.overall_health} label={data.overall_health_label} />}
          />
        </Card>
        <Card>
          <Metric label="Agents" value={formatNumber(counts.total)} note={`${counts.operational} active · ${counts.in_development} in development`} />
        </Card>
        <Card>
          <Metric label="Healthy" value={formatNumber(counts.healthy)} />
        </Card>
        <Card>
          <Metric label="Needs attention" value={formatNumber(counts.degraded)} />
        </Card>
        <Card>
          <Metric label="Unavailable" value={formatNumber(counts.offline)} />
        </Card>
        <Card>
          <Metric
            label="Active executions"
            value={exec.telemetry_available ? formatNumber(exec.active_executions) : "—"}
            note={exec.telemetry_available ? null : "No executions recorded yet"}
          />
        </Card>
        <Card>
          <Metric label="Successful" value={exec.telemetry_available ? formatNumber(exec.successful_executions) : "—"} />
        </Card>
        <Card>
          <Metric label="Failed" value={exec.telemetry_available ? formatNumber(exec.failed_executions) : "—"} />
        </Card>
        <Card>
          <Metric label="Average time" value={<TelemetryValue value={exec.average_execution_time_ms ? formatMs(exec.average_execution_time_ms) : null} />} />
        </Card>
      </div>

      <div className="ao-grid ao-grid--2">
        <Card title="Workflow">
          <p style={{ color: "var(--text-subtle)", marginBottom: 16 }}>
            Existing agents are operational. Later stages stay marked in development until they are implemented.
          </p>
          <WorkflowPipeline nodes={data.workflow} hrefFor={(id) => `/agents/${id}`} />
        </Card>
        <div className="ao-grid">
          {can(["super_admin", "approver"]) ? (
            <Card title="Start a journey">
              <form
                onSubmit={async (event) => {
                  event.preventDefault();
                  setStarting(true);
                  try {
                    const created = await api<{ execution_id: string }>("/api/executions", {
                      method: "POST",
                      body: JSON.stringify({ request_text: utterance, channel, mode }),
                    });
                    navigate(`/executions/${created.execution_id}`);
                  } finally {
                    setStarting(false);
                  }
                }}
              >
                <label className="ao-field">
                  <span className="ao-field__label">Customer request</span>
                  <textarea className="ao-textarea" value={utterance} onChange={(e) => setUtterance(e.target.value)} />
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
                  <label className="ao-field">
                    <span className="ao-field__label">Channel</span>
                    <select className="ao-select" value={channel} onChange={(e) => setChannel(e.target.value)}>
                      <option value="asknow">AskNow</option>
                      <option value="eva">EVA</option>
                      <option value="web">Web</option>
                    </select>
                  </label>
                  <label className="ao-field">
                    <span className="ao-field__label">Mode</span>
                    <select className="ao-select" value={mode} onChange={(e) => setMode(e.target.value as "live" | "demo")}>
                      <option value="live">Live</option>
                      <option value="demo">Demo mode</option>
                    </select>
                  </label>
                </div>
                <div style={{ marginTop: 16 }}>
                  <Button type="submit" disabled={starting}>
                    {starting ? "Starting…" : "Run workflow"}
                  </Button>
                </div>
                {mode === "demo" ? (
                  <p style={{ marginTop: 12, fontSize: 12 }} className="ao-demo-banner">
                    Demo mode — labelled in the trace. Not mixed with unlabelled production telemetry.
                  </p>
                ) : null}
              </form>
            </Card>
          ) : (
            <Alert tone="info" title="View only">
              You can observe the platform. Starting a workflow requires an Approver or Super Admin role.
            </Alert>
          )}
          <Card title="Recent incidents" action={<Link to="/errors">View all</Link>}>
            {exec.recent_errors.length === 0 ? (
              <EmptyState title="No recent errors" body="Failures will appear here when a flow stops." />
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 12 }}>
                {exec.recent_errors.map((item) => (
                  <li key={item.execution_id}>
                    <Link to={`/executions/${item.execution_id}`}>{item.flow_id}</Link>
                    <div style={{ fontSize: 13, color: "var(--text-subtle)" }}>
                      {item.agent_id} · {item.message || "See trace"}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
