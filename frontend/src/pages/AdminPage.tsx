import { FormEvent, useEffect, useState } from "react";
import { Button, Card, ErrorPanel, Field, LoadingBlock, PageHeader, StatusBadge, TextInput } from "../components/ui";
import { useToast } from "../context/ToastContext";
import { api, type User } from "../lib/api";
import { formatDate } from "../lib/format";

export function AdminPage() {
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  const [form, setForm] = useState({
    username: "",
    password: "",
    display_name: "",
    role: "viewer",
  });

  async function load() {
    const data = await api<{ users: User[] }>("/api/admin/users");
    setUsers(data.users);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "User directory unavailable."));
  }, []);

  async function createUser(event: FormEvent) {
    event.preventDefault();
    await api("/api/admin/users", { method: "POST", body: JSON.stringify(form) });
    toast.push("User created");
    setForm({ username: "", password: "", display_name: "", role: "viewer" });
    await load();
  }

  if (error) return <ErrorPanel title="Administration unavailable" body={error} />;
  if (!users) return <LoadingBlock />;

  return (
    <>
      <PageHeader title="Administration" description="Create users, assign roles, and disable access. Passwords are stored hashed." />
      <div className="ao-grid ao-grid--2">
        <Card title="Create user">
          <form onSubmit={createUser} className="ao-grid" style={{ gap: 16 }}>
            <Field label="User ID">
              <TextInput value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
            </Field>
            <Field label="Display name">
              <TextInput value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} required />
            </Field>
            <Field label="Password" hint="At least 10 characters. Never stored in plaintext.">
              <TextInput type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required minLength={10} />
            </Field>
            <Field label="Role">
              <select className="ao-select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="viewer">Viewer</option>
                <option value="approver">Approver</option>
                <option value="super_admin">Super Admin</option>
              </select>
            </Field>
            <Button type="submit">Create user</Button>
          </form>
        </Card>
        <Card title="Directory">
          <div className="ao-table-wrap">
            <table className="ao-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Last login</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td data-label="User">
                      {user.display_name}
                      <div style={{ color: "var(--text-subtle)" }}>{user.username}</div>
                    </td>
                    <td data-label="Role">{user.role}</td>
                    <td data-label="Status">
                      <StatusBadge status={user.status} />
                    </td>
                    <td data-label="Last login">{formatDate(user.last_login_at)}</td>
                    <td data-label="Actions">
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        onClick={async () => {
                          await api(`/api/admin/users/${user.id}`, {
                            method: "PATCH",
                            body: JSON.stringify({
                              status: user.status === "active" ? "disabled" : "active",
                            }),
                          });
                          toast.push(user.status === "active" ? "User disabled" : "User restored");
                          await load();
                        }}
                      >
                        {user.status === "active" ? "Disable" : "Enable"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}
