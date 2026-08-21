import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, Card, EmptyState, ErrorPanel, LoadingBlock, PageHeader, StatusBadge } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { api, type ExecutionRecord } from "../lib/api";
import { formatDate, formatMs } from "../lib/format";

export function ExecutionsPage({ history = false }: { history?: boolean }) {
  const [rows, setRows] = useState<ExecutionRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const { can } = useAuth();
  const navigate = useNavigate();

  async function load() {
    try {
      const query = status ? `?status=${encodeURIComponent(status)}` : "";
      const data = await api<{ executions: ExecutionRecord[] }>(`/api/executions${query}`);
      setRows(data.executions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Executions are unavailable.");
    }
  }

  useEffect(() => {
    void load();
  }, [status]);

  if (error) return <ErrorPanel title="Execution history unavailable" body={error} onRetry={load} />;
  if (!rows) return <LoadingBlock />;

  const visible = history ? rows : rows.filter((row) => ["queued", "running"].includes(row.status)).concat(rows.slice(0, 8));

  return (
    <>
      <PageHeader
        title={history ? "Execution history" : "Live executions"}
        description={history ? "Every recorded flow, including retries and replays." : "Watch in-flight journeys. Completed work lives in history."}
        actions={
          can(["super_admin", "approver"]) ? (
            <Button type="button" onClick={() => navigate("/")}>
              Start from overview
            </Button>
          ) : null
        }
      />
      <Card quiet>
        <label className="ao-field" style={{ maxWidth: 240, marginBottom: 16 }}>
          <span className="ao-field__label">Status</span>
          <select className="ao-select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="queued">Queued</option>
          </select>
        </label>
        {visible.length === 0 ? (
          <EmptyState title="No executions" body="Start a workflow to see live progress through the agents." />
        ) : (
          <div className="ao-table-wrap">
            <table className="ao-table">
              <thead>
                <tr>
                  <th>Flow ID</th>
                  <th>User</th>
                  <th>Request</th>
                  <th>Started</th>
                  <th>Duration</th>
                  <th>Stage</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr
                    key={row.execution_id}
                    tabIndex={0}
                    onClick={() => navigate(`/executions/${row.execution_id}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") navigate(`/executions/${row.execution_id}`);
                    }}
                  >
                    <td data-label="Flow ID">
                      <Link to={`/executions/${row.execution_id}`}>{row.flow_id}</Link>
                      {row.mode === "demo" ? <div className="ao-demo-banner">Demo</div> : null}
                    </td>
                    <td data-label="User">{row.username}</td>
                    <td data-label="Request">{row.request_text}</td>
                    <td data-label="Started">{formatDate(row.started_at)}</td>
                    <td data-label="Duration">{formatMs(row.duration_ms)}</td>
                    <td data-label="Stage">{row.current_stage || "—"}</td>
                    <td data-label="Status">
                      <StatusBadge status={row.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
