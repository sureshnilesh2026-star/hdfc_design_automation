import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorPanel,
  LoadingBlock,
  PageHeader,
  StatusBadge,
} from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api, type DocumentRecord } from "../lib/api";
import { formatBytes, formatDate, formatNumber } from "../lib/format";
import { WorkflowPipeline } from "../components/WorkflowPipeline";

export function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const { can } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  async function load(query = q) {
    const data = await api<{ documents: DocumentRecord[] }>(
      `/api/knowledge/documents${query ? `?q=${encodeURIComponent(query)}` : ""}`,
    );
    setDocs(data.documents);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Documents unavailable."));
  }, []);

  if (error) return <ErrorPanel title="Documents unavailable" body={error} />;
  if (!docs) return <LoadingBlock />;

  return (
    <>
      <PageHeader title="Documents" description="Search, filter, and inspect knowledge files." />
      <Card>
        <form
          style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}
          onSubmit={(event) => {
            event.preventDefault();
            void load(q);
          }}
        >
          <input className="ao-input" style={{ maxWidth: 320 }} placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} />
          <Button type="submit" variant="secondary">
            Search
          </Button>
          {can(["super_admin"]) ? (
            <label className="ao-btn ao-btn--primary">
              Upload
              <input
                type="file"
                className="sr-only"
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  const body = new FormData();
                  body.append("file", file);
                  await api("/api/knowledge/documents", { method: "POST", body });
                  toast.push("Document uploaded");
                  await load();
                }}
              />
            </label>
          ) : null}
        </form>
        {docs.length === 0 ? (
          <EmptyState title="No documents match" body="Try another search, or upload a file if you are an administrator." />
        ) : (
          <div className="ao-table-wrap">
            <table className="ao-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Size</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => (
                  <tr key={doc.document_id} tabIndex={0} onClick={() => navigate(`/documents/${doc.document_id}`)}>
                    <td data-label="Name">
                      <Link to={`/documents/${doc.document_id}`}>{doc.file_name}</Link>
                    </td>
                    <td data-label="Type">{doc.file_type}</td>
                    <td data-label="Category">{doc.category}</td>
                    <td data-label="Status">
                      <StatusBadge status={doc.status} />
                    </td>
                    <td data-label="Size">{formatBytes(doc.size_bytes)}</td>
                    <td data-label="Updated">{formatDate(doc.last_updated)}</td>
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

export function DocumentDetailPage() {
  const { documentId = "" } = useParams();
  const [doc, setDoc] = useState<DocumentRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<DocumentRecord>(`/api/knowledge/documents/${documentId}`)
      .then(setDoc)
      .catch((err) => setError(err instanceof Error ? err.message : "Document unavailable."));
  }, [documentId]);

  if (error) return <ErrorPanel title="Document unavailable" body={error} />;
  if (!doc) return <LoadingBlock />;

  const stages = (doc.ingestion || []).map((item) => ({
    agent_id: item.stage,
    name: item.stage,
    status: item.status === "skipped" ? "not_implemented" : item.status,
    note: item.note,
  }));

  return (
    <>
      <PageHeader title={doc.file_name} description={`${doc.category || "Uncategorised"} · ${doc.document_id}`} />
      <div className="ao-grid ao-grid--metrics">
        <Card>
          <div>Type</div>
          <strong>{doc.file_type}</strong>
        </Card>
        <Card>
          <div>Version</div>
          <strong>{doc.version}</strong>
        </Card>
        <Card>
          <StatusBadge status={doc.status} />
        </Card>
        <Card>
          <div>Pages</div>
          <strong>{formatNumber(doc.page_count)}</strong>
        </Card>
        <Card>
          <div>Uploaded by</div>
          <strong>{doc.uploaded_by}</strong>
        </Card>
        <Card>
          <div>Last updated</div>
          <strong>{formatDate(doc.last_updated)}</strong>
        </Card>
      </div>
      <div className="ao-grid ao-grid--2" style={{ marginTop: 20 }}>
        <Card title="Ingestion">
          {stages.length ? <WorkflowPipeline nodes={stages} /> : <p>Bundled documents are already indexed.</p>}
        </Card>
        <Card title="Preview">
          {doc.preview?.preview_available ? (
            <pre className="ao-json">{doc.preview.content}</pre>
          ) : (
            <Alert tone="info" title="Preview not available">
              {doc.preview?.reason || "This file type cannot be previewed in the dashboard."}
            </Alert>
          )}
        </Card>
      </div>
    </>
  );
}
