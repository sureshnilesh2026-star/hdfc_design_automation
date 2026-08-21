const TOKEN_KEY = "agentops.token";

export type Role = "super_admin" | "approver" | "viewer";

export type User = {
  id: number;
  username: string;
  display_name: string;
  role: Role;
  status: string;
  last_login_at?: string | null;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) return body.detail.map((d: { msg?: string }) => d.msg).join(" ");
  } catch {
    /* ignore */
  }
  if (response.status === 401) return "Please sign in to continue.";
  if (response.status === 403) return "You do not have permission for this action.";
  return "The request could not be completed.";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers });
  if (response.status === 204) return undefined as T;
  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }
  return response.json() as Promise<T>;
}

export type Overview = {
  overall_health: string;
  overall_health_label: string;
  agent_counts: Record<string, number>;
  executions: {
    active_executions: number;
    successful_executions: number;
    failed_executions: number;
    total_executions: number;
    average_execution_time_ms: number | null;
    telemetry_available: boolean;
    recent_errors: Array<{
      execution_id: string;
      flow_id: string;
      agent_id: string | null;
      message: string | null;
      at: string | null;
    }>;
  };
  workflow: WorkflowStage[];
  system: { overall: string; components: HealthComponent[]; uptime_seconds: number };
};

export type WorkflowStage = {
  agent_id: string;
  name: string;
  pipeline_order: number;
  kind: string;
  lifecycle?: string;
  status?: string;
  status_label?: string;
  note?: string | null;
};

export type HealthComponent = {
  component: string;
  status: string;
  note?: string;
  last_checked?: string;
};

export type AgentRecord = {
  agent_id: string;
  name: string;
  description: string;
  version?: string | null;
  lifecycle: string;
  pipeline_order: number;
  purpose: string;
  status: string;
  status_label: string;
  capabilities: string[];
  dependencies: string[];
  implementation?: string | null;
  environment: string;
  last_heartbeat?: string | null;
  uptime_seconds?: number | null;
  health: Record<string, unknown>;
  metrics: Record<string, unknown>;
  latest_execution?: Record<string, unknown> | null;
  recent_errors?: Array<Record<string, unknown>>;
};

export type ExecutionRecord = {
  flow_id: string;
  execution_id: string;
  trace_id: string;
  parent_trace_id?: string | null;
  username?: string | null;
  request_text: string;
  channel?: string | null;
  environment: string;
  mode: string;
  runtime_mode?: string | null;
  status: string;
  current_stage?: string | null;
  failed_agent_id?: string | null;
  started_at: string;
  ended_at?: string | null;
  duration_ms?: number | null;
  error_summary?: string | null;
  approval_status?: string | null;
  replay_of?: string | null;
  is_demo?: boolean;
  payload: {
    stages?: ExecutionStage[];
    business_summary?: string;
    runtime_mode?: string;
    llm_model?: string;
  };
  events?: ExecutionEvent[];
};

export type ExecutionStage = {
  agent_id: string;
  name: string;
  kind?: string;
  status: string;
  duration_ms?: number | null;
  note?: string | null;
  input?: unknown;
  output?: unknown;
  error?: {
    type?: string;
    message?: string;
    severity?: string;
    recovery?: string;
    stack?: string;
  } | null;
};

export type ExecutionEvent = {
  at: string;
  agent_id?: string | null;
  event_type: string;
  status?: string | null;
  message: string;
  duration_ms?: number | null;
  payload?: unknown;
};

export type DocumentRecord = {
  document_id: string;
  file_name: string;
  file_type: string;
  version: string;
  uploaded_at: string;
  uploaded_by?: string | null;
  status: string;
  processing_status: string;
  indexing_status: string;
  size_bytes?: number | null;
  page_count?: number | null;
  category?: string | null;
  last_updated: string;
  origin?: string;
  source_path?: string;
  ingestion?: Array<{ stage: string; status: string; note?: string }>;
  preview?: { preview_available: boolean; content?: string; reason?: string; chunks?: unknown[] };
  history?: Array<Record<string, unknown>>;
  error_message?: string | null;
};

export async function subscribeExecution(
  executionId: string,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<() => void> {
  const token = getToken();
  const controller = new AbortController();
  try {
    const response = await fetch(`/api/executions/${executionId}/events`, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      signal: controller.signal,
    });
    if (!response.ok || !response.body) {
      throw new Error("stream unavailable");
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    void (async () => {
      while (!controller.signal.aborted) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";
        for (const chunk of chunks) {
          const line = chunk.split("\n").find((entry) => entry.startsWith("data: "));
          if (!line) continue;
          try {
            onEvent(JSON.parse(line.slice(6)));
          } catch {
            /* ignore malformed frames */
          }
        }
      }
    })();
  } catch {
    const timer = window.setInterval(async () => {
      try {
        const snapshot = await api<ExecutionRecord>(`/api/executions/${executionId}`);
        onEvent({ event_type: "snapshot", execution: snapshot });
        if (snapshot.status === "completed" || snapshot.status === "failed") {
          window.clearInterval(timer);
        }
      } catch {
        onEvent({ event_type: "error", message: "Live updates are temporarily unavailable." });
      }
    }, 1500);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }
  return () => controller.abort();
}
