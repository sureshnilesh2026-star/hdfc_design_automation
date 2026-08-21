import { useEffect, useState } from "react";
import { WorkflowPipeline } from "../components/WorkflowPipeline";
import { Card, ErrorPanel, LoadingBlock, PageHeader } from "../components/ui";
import { api, type WorkflowStage } from "../lib/api";

export function WorkflowPage() {
  const [stages, setStages] = useState<WorkflowStage[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ stages: WorkflowStage[] }>("/api/workflow")
      .then((data) => setStages(data.stages))
      .catch((err) => setError(err instanceof Error ? err.message : "Workflow is unavailable."));
  }, []);

  if (error) return <ErrorPanel title="Workflow unavailable" body={error} />;
  if (!stages) return <LoadingBlock />;

  return (
    <>
      <PageHeader
        title="Workflow"
        description="The observable pipeline from customer request to output. Future agents remain in development until they are registered."
      />
      <Card>
        <WorkflowPipeline nodes={stages} hrefFor={(id) => `/agents/${id}`} />
      </Card>
    </>
  );
}
