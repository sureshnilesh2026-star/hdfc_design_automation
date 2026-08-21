export const STATUS_LABELS: Record<string, string> = {
  HEALTHY: "Healthy",
  RUNNING: "Running",
  IDLE: "Ready",
  DEGRADED: "Needs attention",
  FAILED: "Failed",
  OFFLINE: "Unavailable",
  RETRYING: "Retrying",
  WAITING: "Waiting",
  IN_DEVELOPMENT: "In development",
  UNKNOWN: "Unknown",
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  warning: "Warning",
  failed: "Failed",
  retrying: "Retrying",
  skipped: "Skipped",
  waiting: "Waiting",
  not_implemented: "In development",
  not_started: "Not started",
  healthy: "Healthy",
  degraded: "Needs attention",
  unavailable: "Unavailable",
  indexed: "Indexed",
  uploaded: "Uploaded",
  processing: "Processing",
  archived: "Archived",
  approved: "Approved",
  rejected: "Rejected",
  active: "Active",
  disabled: "Disabled",
};

export function statusLabel(status?: string | null): string {
  if (!status) return "Unknown";
  return STATUS_LABELS[status] ?? STATUS_LABELS[status.toUpperCase()] ?? status.replaceAll("_", " ");
}

export function statusTone(status?: string | null): string {
  const value = (status || "").toLowerCase();
  if (["healthy", "completed", "success", "indexed", "approved", "active"].includes(value)) return "healthy";
  if (["degraded", "warning", "partial"].includes(value)) return "degraded";
  if (["failed", "unavailable", "offline", "error", "rejected", "disabled"].includes(value)) return "failed";
  if (["running", "processing", "queued"].includes(value)) return "running";
  if (["in_development", "not_implemented", "dev"].includes(value)) return "dev";
  return "neutral";
}

export function isDevelopment(lifecycle?: string, status?: string): boolean {
  return lifecycle === "in_development" || status === "IN_DEVELOPMENT" || status === "not_implemented";
}
