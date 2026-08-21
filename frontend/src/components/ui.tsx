import { type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, useId } from "react";
import { statusLabel, statusTone } from "../lib/status";

export function Button({
  variant = "primary",
  size = "md",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "tertiary" | "link" | "danger";
  size?: "sm" | "md" | "lg";
}) {
  return (
    <button className={`ao-btn ao-btn--${variant} ao-btn--${size}`} {...props}>
      {children}
    </button>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="ao-field">
      <span className="ao-field__label">{label}</span>
      {children}
      {hint && !error ? <span className="ao-field__hint">{hint}</span> : null}
      {error ? (
        <span className="ao-field__error" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return <input id={id} className="ao-input" {...props} />;
}

export function Card({
  children,
  title,
  action,
  quiet,
}: {
  children: ReactNode;
  title?: string;
  action?: ReactNode;
  quiet?: boolean;
}) {
  return (
    <section className={`ao-card ${quiet ? "ao-card--quiet" : ""}`}>
      {title ? (
        <header style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
          <h3>{title}</h3>
          {action}
        </header>
      ) : null}
      {children}
    </section>
  );
}

export function StatusBadge({ status, label }: { status?: string | null; label?: string }) {
  const tone = statusTone(status);
  return (
    <span className={`ao-badge ao-badge--${tone} ao-badge--${(status || "unknown").toLowerCase()}`}>
      <span className="ao-dot" aria-hidden="true" />
      <span>{label ?? statusLabel(status)}</span>
    </span>
  );
}

export function Alert({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "error" | "warning" | "success";
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className={`ao-alert ao-alert--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <div>
        <strong>{title}</strong>
        {children ? <p style={{ marginTop: 6 }}>{children}</p> : null}
      </div>
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="ao-empty">
      <h3>{title}</h3>
      <p style={{ marginTop: 8 }}>{body}</p>
    </div>
  );
}

export function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: ReactNode;
  note?: string | null;
}) {
  return (
    <div className="ao-metric">
      <div className="ao-metric__value">{value}</div>
      <div className="ao-metric__label">{label}</div>
      {note ? <div className="ao-metric__note">{note}</div> : null}
    </div>
  );
}

export function TelemetryValue({ value }: { value: unknown }) {
  if (value == null || value === "") return <span>—</span>;
  return <>{String(value)}</>;
}

export function JsonBlock({ value }: { value: unknown }) {
  return <pre className="ao-json">{JSON.stringify(value, null, 2)}</pre>;
}

export function CopyButton({ text }: { text: string }) {
  return (
    <Button
      type="button"
      variant="secondary"
      size="sm"
      onClick={async () => {
        await navigator.clipboard.writeText(text);
      }}
    >
      Copy
    </Button>
  );
}

export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: Array<{ id: string; label: string }>;
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="ao-tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={value === tab.id}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="ao-page-head">
      <div>
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions}
    </header>
  );
}

export function LoadingBlock() {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading</span>
      <div className="ao-grid ao-grid--metrics">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="ao-card">
            <div className="ao-skeleton" style={{ height: 48 }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ErrorPanel({
  title,
  body,
  onRetry,
}: {
  title: string;
  body: string;
  onRetry?: () => void;
}) {
  return (
    <Alert tone="error" title={title}>
      {body}
      {onRetry ? (
        <div style={{ marginTop: 12 }}>
          <Button type="button" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : null}
    </Alert>
  );
}
