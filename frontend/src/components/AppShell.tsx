import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Menu, Moon, Sun, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { initials } from "../lib/format";
import { Button } from "./ui";

const NAV = [
  {
    legend: "Control center",
    items: [
      { to: "/", label: "Overview" },
      { to: "/workflow", label: "Workflow" },
      { to: "/executions", label: "Live executions" },
      { to: "/history", label: "Execution history" },
    ],
  },
  {
    legend: "Agents",
    items: [
      { to: "/agents", label: "All agents" },
      { to: "/agents/intent-recognition", label: "Intent Recognition" },
      { to: "/agents/platform-capability", label: "Platform Capability" },
      { to: "/agents/knowledge-repository", label: "Knowledge Repository" },
      { to: "/agents/journey-planner", label: "Journey Planner" },
      { to: "/agents/component-intelligence", label: "Component Intelligence" },
      { to: "/agents/response-orchestrator", label: "Response Orchestrator" },
      { to: "/agents/json-compiler", label: "JSON Compiler" },
      { to: "/agents/validation-engine", label: "Validation Engine" },
      { to: "/agents/output-engine", label: "Output Engine" },
    ],
  },
  {
    legend: "Knowledge",
    items: [
      { to: "/knowledge", label: "Knowledge repository" },
      { to: "/documents", label: "Documents" },
    ],
  },
  {
    legend: "Operations",
    items: [
      { to: "/errors", label: "Errors & incidents" },
      { to: "/health", label: "System health" },
    ],
  },
];

export function AppShell() {
  const { user, logout, can } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const groups = useMemo(() => {
    const extra = [];
    if (can(["super_admin"])) {
      extra.push({
        legend: "Administration",
        items: [
          { to: "/audit", label: "Audit logs" },
          { to: "/admin", label: "Administration" },
        ],
      });
    }
    return [...NAV, ...extra];
  }, [can]);

  const nav = (
    <nav aria-label="Primary">
      {groups.map((group) => (
        <fieldset key={group.legend} className="ao-nav-group">
          <legend>{group.legend}</legend>
          {group.items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/" || item.to === "/agents"}
              className={({ isActive }) =>
                `ao-nav-link ${item.to.startsWith("/agents/") ? "ao-nav-sub" : ""} ${isActive ? "is-active" : ""}`
              }
              onClick={() => setOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}
        </fieldset>
      ))}
    </nav>
  );

  return (
    <div className="ao-shell">
      <aside className="ao-sidebar" aria-label="Application">
        <div style={{ padding: "0 20px 16px" }}>
          <div className="ao-brand">
            <span className="ao-brand__mark" aria-hidden="true">
              AO
            </span>
            AgentOps
          </div>
        </div>
        {nav}
      </aside>
      <header className="ao-topbar">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button
            type="button"
            className="ao-btn ao-btn--secondary ao-menu-btn"
            aria-label={open ? "Close navigation" : "Open navigation"}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X size={18} /> : <Menu size={18} />}
          </button>
          <span className="ao-brand" style={{ display: "flex" }}>
            <span className="ao-brand__mark" aria-hidden="true">
              AO
            </span>
            Control Center
          </span>
        </div>
        <div className="ao-user">
          <Button type="button" variant="tertiary" aria-label="Switch theme" onClick={toggle}>
            {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          </Button>
          <div className="ao-avatar" aria-hidden="true">
            {initials(user?.display_name)}
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>{user?.display_name}</div>
            <div style={{ fontSize: 12, color: "var(--text-subtle)" }}>{user?.role.replace("_", " ")}</div>
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
          >
            Log out
          </Button>
        </div>
      </header>
      {open ? (
        <div className="ao-drawer-backdrop" onClick={() => setOpen(false)}>
          <div
            className="ao-drawer"
            role="dialog"
            aria-label="Navigation"
            onClick={(event) => event.stopPropagation()}
          >
            <div style={{ padding: 20, display: "flex", justifyContent: "space-between" }}>
              <strong>AgentOps</strong>
              <Button type="button" variant="tertiary" onClick={() => setOpen(false)} aria-label="Close">
                <X size={18} />
              </Button>
            </div>
            {nav}
          </div>
        </div>
      ) : null}
      <main className="ao-main" key={location.pathname}>
        <Outlet />
      </main>
    </div>
  );
}
