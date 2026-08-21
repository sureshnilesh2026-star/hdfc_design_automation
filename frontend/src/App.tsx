import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { useAuth } from "./context/AuthContext";
import type { Role } from "./lib/api";
import { AdminPage } from "./pages/AdminPage";
import { AgentDetailPage } from "./pages/AgentDetailPage";
import { AgentsPage } from "./pages/AgentsPage";
import { AuditPage } from "./pages/AuditPage";
import { DocumentDetailPage, DocumentsPage } from "./pages/DocumentsPage";
import { ErrorsPage } from "./pages/ErrorsPage";
import { ExecutionDetailPage } from "./pages/ExecutionDetailPage";
import { ExecutionsPage } from "./pages/ExecutionsPage";
import { HealthPage } from "./pages/HealthPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { LoginPage } from "./pages/LoginPage";
import { OverviewPage } from "./pages/OverviewPage";
import { WorkflowPage } from "./pages/WorkflowPage";

function Guard({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { user, loading, can } = useAuth();
  const location = useLocation();
  if (loading) {
    return <p className="ao-empty">Loading session…</p>;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (roles && !can(roles)) {
    return <p className="ao-empty">You do not have permission to open this page.</p>;
  }
  return <>{children}</>;
}

export function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          element={
            <Guard>
              <AppShell />
            </Guard>
          }
        >
          <Route index element={<OverviewPage />} />
          <Route path="workflow" element={<WorkflowPage />} />
          <Route path="executions" element={<ExecutionsPage />} />
          <Route path="executions/:executionId" element={<ExecutionDetailPage />} />
          <Route path="history" element={<ExecutionsPage history />} />
          <Route path="agents" element={<AgentsPage />} />
          <Route path="agents/:agentId" element={<AgentDetailPage />} />
          <Route path="knowledge" element={<KnowledgePage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="documents/:documentId" element={<DocumentDetailPage />} />
          <Route path="errors" element={<ErrorsPage />} />
          <Route path="health" element={<HealthPage />} />
          <Route path="audit" element={<Guard roles={["super_admin"]}><AuditPage /></Guard>} />
          <Route path="admin" element={<Guard roles={["super_admin"]}><AdminPage /></Guard>} />
        </Route>
      </Routes>
    </ErrorBoundary>
  );
}
