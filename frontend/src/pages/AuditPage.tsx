import { useEffect, useState } from "react";
import { Card, EmptyState, ErrorPanel, LoadingBlock, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { formatDate } from "../lib/format";

type Log = {
  id: number;
  at: string;
  username: string | null;
  action: string;
  resource: string | null;
  result: string;
  ip: string | null;
  trace_id: string | null;
};

export function AuditPage() {
  const [logs, setLogs] = useState<Log[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");

  async function load(query = q) {
    const data = await api<{ logs: Log[] }>(`/api/audit${query ? `?q=${encodeURIComponent(query)}` : ""}`);
    setLogs(data.logs);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Audit logs unavailable."));
  }, []);

  if (error) return <ErrorPanel title="Audit logs unavailable" body={error} />;
  if (!logs) return <LoadingBlock />;

  return (
    <>
      <PageHeader title="Audit logs" description="Administrative activity across sign-in, users, approvals, and document changes." />
      <Card>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void load(q);
          }}
          style={{ marginBottom: 16 }}
        >
          <input className="ao-input" placeholder="Search user, action, or resource" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        {logs.length === 0 ? (
          <EmptyState title="No matching events" body="Try a different search." />
        ) : (
          <div className="ao-table-wrap">
            <table className="ao-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Resource</th>
                  <th>Result</th>
                  <th>IP</th>
                  <th>Trace</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td data-label="Time">{formatDate(log.at)}</td>
                    <td data-label="User">{log.username}</td>
                    <td data-label="Action">{log.action}</td>
                    <td data-label="Resource">{log.resource}</td>
                    <td data-label="Result">{log.result}</td>
                    <td data-label="IP">{log.ip || "—"}</td>
                    <td data-label="Trace">{log.trace_id || "—"}</td>
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
