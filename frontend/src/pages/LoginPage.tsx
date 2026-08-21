import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/api";
import { Alert, Button, Field, TextInput } from "../components/ui";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const from = (location.state as { from?: string } | null)?.from || "/";

  if (user) return <Navigate to={from} replace />;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Sign-in is unavailable right now.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="ao-login">
      <form className="ao-card ao-login__card" onSubmit={onSubmit}>
        <div className="ao-login__brand">
          <span className="ao-brand__mark" aria-hidden="true">
            AO
          </span>
          <div>
            <strong>AgentOps Control Center</strong>
            <p style={{ color: "var(--text-subtle)", marginTop: 4 }}>HDFC Journey Generation Platform</p>
          </div>
        </div>
        <h1 style={{ fontSize: 28, marginBottom: 8 }}>Sign in</h1>
        <p style={{ color: "var(--text-subtle)", marginBottom: 24 }}>
          Use your AgentOps user ID and password.
        </p>
        {error ? <Alert tone="error" title="Could not sign in">{error}</Alert> : null}
        <div style={{ display: "grid", gap: 16, marginTop: 16 }}>
          <Field label="User ID">
            <TextInput
              name="username"
              autoComplete="username"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </Field>
          <Field label="Password">
            <TextInput
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
          <Button type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </div>
        <p style={{ marginTop: 20, fontSize: 12, color: "var(--text-subtle)" }}>
          Seed accounts: admin, approver, viewer. Change the default passwords after first sign-in.
        </p>
      </form>
    </div>
  );
}
