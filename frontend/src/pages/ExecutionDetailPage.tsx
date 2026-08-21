import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { WorkflowPipeline } from "../components/WorkflowPipeline";
import {
  Alert,
  Button,
  Card,
  CopyButton,
  ErrorPanel,
  JsonBlock,
  LoadingBlock,
  PageHeader,
  StatusBadge,
  Tabs,
} from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api, subscribeExecution, type ExecutionRecord } from "../lib/api";
import { formatDate, formatMs } from "../lib/format";

export function ExecutionDetailPage() {
  const { executionId = "" } = useParams();
  const [record, setRecord] = useState<ExecutionRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState("business");
  const [openStage, setOpenStage] = useState<string | null>(null);
  const { can } = useAuth();
  const toast = useToast();

  useEffect(() => {
    let stop: (() => void) | undefined;
    api<ExecutionRecord>(`/api/executions/${executionId}`)
      .then(async (data) => {
        setRecord(data);
        stop = await subscribeExecution(data.execution_id, (event) => {
          if (event.event_type === "snapshot" && event.execution) {
            setRecord(event.execution as ExecutionRecord);
          } else {
            void api<ExecutionRecord>(`/api/executions/${executionId}`).then(setRecord);
          }
        });
      })
      .catch((err) => setError(err instanceof Error ? err.message : "This execution is unavailable."));
    return () => stop?.();
  }, [executionId]);

  if (error) return <ErrorPanel title="Execution unavailable" body={error} />;
  if (!record) return <LoadingBlock />;

  const stages = record.payload.stages || [];
  const failed = stages.find((stage) => stage.status === "failed");
  const live = ["queued", "running"].includes(record.status);
  const executionIdValue = record.execution_id;
  const modeValue = record.mode;

  async function act(path: "retry" | "replay") {
    const created = await api<ExecutionRecord>(`/api/executions/${executionIdValue}/${path}`, {
      method: "POST",
      body: path === "replay" ? JSON.stringify({ mode: modeValue }) : undefined,
    });
    toast.push(path === "replay" ? "Replay started as a new execution." : "Retry started.");
    window.location.assign(`/executions/${created.execution_id}`);
  }

  return (
    <>
      {record.mode === "demo" ? <div className="ao-demo-banner">Demo mode — simulated label on a real agent run</div> : null}
      <PageHeader
        title={record.flow_id}
        description={record.payload.business_summary || record.request_text}
        actions={
          <div className="ao-chip-row">
            <StatusBadge status={record.status} />
            {can(["super_admin", "approver"]) && record.status === "failed" ? (
              <Button type="button" onClick={() => void act("retry")}>
                Retry
              </Button>
            ) : null}
            {can(["super_admin", "approver"]) ? (
              <Button type="button" variant="secondary" onClick={() => void act("replay")}>
                Replay
              </Button>
            ) : null}
          </div>
        }
      />
      {failed ? (
        <Alert tone="error" title="Flow failed">
          It stopped at {failed.name}. {failed.error?.message}
          <div style={{ marginTop: 8, fontSize: 13 }}>
            Trace ID {record.trace_id} · {formatDate(record.ended_at)}
          </div>
        </Alert>
      ) : null}
      <div className="ao-grid ao-grid--metrics" style={{ margin: "20px 0" }}>
        <Card>
          <div>Trace ID</div>
          <strong>{record.trace_id}</strong>
        </Card>
        <Card>
          <div>Execution ID</div>
          <strong>{record.execution_id}</strong>
        </Card>
        <Card>
          <div>Duration</div>
          <strong>{formatMs(record.duration_ms)}</strong>
        </Card>
        <Card>
          <div>Runtime</div>
          <strong>{record.runtime_mode || record.payload.runtime_mode || "—"}</strong>
        </Card>
      </div>
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "business", label: "Journey view" },
          { id: "technical", label: "View details" },
        ]}
      />
      <div style={{ marginTop: 20 }} className="ao-grid ao-grid--2">
        <Card title={live ? "Live flow" : "Pipeline"}>
          <WorkflowPipeline nodes={stages} hrefFor={(id) => `/agents/${id}`} />
        </Card>
        <Card title="Trace">
          {(record.events || []).map((event) => (
            <div key={`${event.at}-${event.message}`} style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 8, fontSize: 13, marginBottom: 8 }}>
              <span style={{ color: "var(--text-subtle)" }}>{new Date(event.at).toLocaleTimeString()}</span>
              <span>
                {event.agent_id ? <strong>{event.agent_id} · </strong> : null}
                {event.message}
              </span>
            </div>
          ))}
        </Card>
      </div>
      {tab === "technical" ? (
        <div style={{ marginTop: 20 }} className="ao-grid">
          {record.parent_trace_id ? (
            <Alert tone="info" title="Replay / retry">
              This execution is based on previous trace {record.parent_trace_id}.
            </Alert>
          ) : null}
          {stages
            .filter((stage) => stage.kind !== "anchor")
            .map((stage) => (
              <Card key={stage.agent_id} title={stage.name} action={<StatusBadge status={stage.status} />}>
                <Button type="button" variant="link" onClick={() => setOpenStage(openStage === stage.agent_id ? null : stage.agent_id)}>
                  {openStage === stage.agent_id ? "Collapse" : "Expand"}
                </Button>
                {openStage === stage.agent_id ? (
                  <div className="ao-grid ao-grid--2" style={{ marginTop: 12 }}>
                    <div>
                      <h3>Input</h3>
                      <CopyButton text={JSON.stringify(stage.input ?? {}, null, 2)} />
                      <JsonBlock value={stage.input} />
                    </div>
                    <div>
                      <h3>Output</h3>
                      <CopyButton text={JSON.stringify(stage.output ?? {}, null, 2)} />
                      <JsonBlock value={stage.output} />
                    </div>
                    {stage.error ? (
                      <Alert tone="error" title={stage.error.type || "Error"}>
                        {stage.error.message}
                        {stage.error.recovery ? <div>Recovery: {stage.error.recovery}</div> : null}
                      </Alert>
                    ) : null}
                  </div>
                ) : null}
              </Card>
            ))}
          {can(["approver", "super_admin"]) ? (
            <Card title="Approval">
              <p style={{ marginBottom: 12 }}>Approvers can record a review of this flow.</p>
              <div className="ao-chip-row">
                <Button
                  type="button"
                  onClick={() =>
                    void api(`/api/executions/${record.execution_id}/approval`, {
                      method: "POST",
                      body: JSON.stringify({ decision: "approved" }),
                    }).then(() => toast.push("Flow approved"))
                  }
                >
                  Approve
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  onClick={() =>
                    void api(`/api/executions/${record.execution_id}/approval`, {
                      method: "POST",
                      body: JSON.stringify({ decision: "rejected" }),
                    }).then(() => toast.push("Flow rejected"))
                  }
                >
                  Reject
                </Button>
                {record.approval_status ? <StatusBadge status={record.approval_status} /> : null}
              </div>
            </Card>
          ) : null}
        </div>
      ) : (
        <Card title="What this means">
          <p>
            {record.payload.business_summary ||
              (live ? "The request is moving through the active agents." : "The active agents have finished. Later stages are still in development.")}
          </p>
          <p style={{ marginTop: 12 }}>
            <Link to="/workflow">See the full workflow</Link>
          </p>
        </Card>
      )}
    </>
  );
}
