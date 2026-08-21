"""Canonical AgentOps contract and agent catalog.

New agents are registered here. The dashboard renders from this catalog —
operational agents expose live health/executions; in-development agents appear
as placeholders with no fabricated metrics.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, Field

AgentLifecycle = Literal["operational", "in_development"]
AgentHealthStatus = Literal[
    "HEALTHY",
    "RUNNING",
    "IDLE",
    "DEGRADED",
    "FAILED",
    "OFFLINE",
    "RETRYING",
    "WAITING",
    "IN_DEVELOPMENT",
    "UNKNOWN",
]
TelemetryAvailability = Literal["live", "not_instrumented", "unavailable", "not_applicable"]


class AgentContract(BaseModel):
    """Integration contract every agent should eventually satisfy."""

    agent_id: str
    name: str
    description: str
    version: str | None = None
    lifecycle: AgentLifecycle
    pipeline_order: int
    stage_key: str
    purpose: str
    input_schema: str | None = None
    output_schema: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    environment: str = "local"
    implementation: str | None = None
    telemetry: TelemetryAvailability = "not_instrumented"


AGENT_CATALOG: tuple[AgentContract, ...] = (
    AgentContract(
        agent_id="intent-recognition",
        name="Intent Recognition Agent",
        description=(
            "Understands the customer request, extracts entities, scores confidence, "
            "and proposes a journey type. A deterministic gate accepts or rejects."
        ),
        version="1.0.0",
        lifecycle="operational",
        pipeline_order=10,
        stage_key="intent",
        purpose="Understand user intent",
        input_schema="IntentInput",
        output_schema="IntentProposalOutput",
        dependencies=["llm"],
        capabilities=[
            "intent_classification",
            "entity_extraction",
            "confidence_scoring",
            "ambiguity_detection",
        ],
        implementation="hdfc_journey.agents.intent.agent.IntentRecognitionAgent",
        telemetry="live",
    ),
    AgentContract(
        agent_id="platform-capability",
        name="Platform Capability Agent",
        description=(
            "Checks whether the selected platform can support the capabilities "
            "required by the accepted intent. Deterministic; no LLM."
        ),
        version="1.0.0",
        lifecycle="operational",
        pipeline_order=20,
        stage_key="capability",
        purpose="Validate platform capabilities",
        input_schema="CapabilityRequest",
        output_schema="AgentResponse",
        dependencies=["platform-capability-knowledge"],
        capabilities=[
            "platform_detection",
            "capability_lookup",
            "compatibility_check",
            "conflict_detection",
        ],
        implementation="platform-capability-agent.agent.PlatformCapabilityAgent",
        telemetry="live",
    ),
    AgentContract(
        agent_id="knowledge-repository",
        name="Knowledge Repository Engine",
        description=(
            "Indexes and retrieves enterprise knowledge documents used to plan journeys. "
            "Serves files from the Knowledge Base; vector embedding is not yet instrumented."
        ),
        version="0.1.0",
        lifecycle="operational",
        pipeline_order=30,
        stage_key="knowledge",
        purpose="Retrieve relevant knowledge",
        input_schema="KnowledgeQuery",
        output_schema="KnowledgePack",
        dependencies=["knowledge-base-files"],
        capabilities=[
            "document_index",
            "keyword_retrieval",
            "pack_assembly",
        ],
        implementation="agentops_api.knowledge.KnowledgeRepositoryEngine",
        telemetry="live",
    ),
    AgentContract(
        agent_id="journey-planner",
        name="Journey Planner Agent",
        description=(
            "Produces a structured journey plan from accepted intent, retrieved knowledge, "
            "and a journey skeleton. Does not generate UI or call enterprise APIs."
        ),
        version="1.0.0",
        lifecycle="operational",
        pipeline_order=40,
        stage_key="planning",
        purpose="Plan the customer journey",
        input_schema="PlannerInput",
        output_schema="PlannerOutput",
        dependencies=["llm", "knowledge-repository"],
        capabilities=[
            "step_selection",
            "entity_binding",
            "assumption_recording",
            "unknown_requirement_flagging",
        ],
        implementation="hdfc_journey.agents.planner.agent.JourneyPlannerAgent",
        telemetry="live",
    ),
    AgentContract(
        agent_id="component-intelligence",
        name="Component Intelligence Engine",
        description="Selects design-system components for each planned screen.",
        lifecycle="in_development",
        pipeline_order=50,
        stage_key="components",
        purpose="Map plan steps to UI components",
        telemetry="not_applicable",
    ),
    AgentContract(
        agent_id="design-system-engine",
        name="Design System Engine",
        description="Applies brand tokens, typography, and layout rules to selected components.",
        lifecycle="in_development",
        pipeline_order=60,
        stage_key="design",
        purpose="Apply design-system rules",
        telemetry="not_applicable",
    ),
    AgentContract(
        agent_id="response-orchestrator",
        name="Response Orchestrator",
        description="Coordinates downstream generation, validation, and human approval.",
        lifecycle="in_development",
        pipeline_order=70,
        stage_key="orchestrate",
        purpose="Coordinate remaining pipeline stages",
        telemetry="not_applicable",
    ),
    AgentContract(
        agent_id="json-compiler",
        name="JSON Compiler",
        description="Compiles the planned journey into a machine-readable blueprint.",
        lifecycle="in_development",
        pipeline_order=80,
        stage_key="compile",
        purpose="Compile journey JSON",
        telemetry="not_applicable",
    ),
    AgentContract(
        agent_id="validation-engine",
        name="AI Validation Engine",
        description="Validates compiled journeys against policy, accessibility, and contract rules.",
        lifecycle="in_development",
        pipeline_order=90,
        stage_key="validation",
        purpose="Validate generated output",
        telemetry="not_applicable",
    ),
    AgentContract(
        agent_id="output-engine",
        name="Output Engine",
        description="Packages the approved journey for delivery to the target platform.",
        lifecycle="in_development",
        pipeline_order=100,
        stage_key="output",
        purpose="Emit platform output",
        telemetry="not_applicable",
    ),
    AgentContract(
        agent_id="human-in-the-loop",
        name="Human-in-the-Loop",
        description="Routes journeys that need an approver before they continue.",
        lifecycle="in_development",
        pipeline_order=110,
        stage_key="hitl",
        purpose="Human approval gate",
        telemetry="not_applicable",
    ),
    AgentContract(
        agent_id="learning-engine",
        name="Learning Engine",
        description="Captures feedback from approvals, failures, and production outcomes.",
        lifecycle="in_development",
        pipeline_order=120,
        stage_key="learning",
        purpose="Learn from outcomes",
        telemetry="not_applicable",
    ),
)

WORKFLOW_ANCHORS: tuple[dict[str, Any], ...] = (
    {
        "agent_id": "request",
        "name": "Request",
        "pipeline_order": 0,
        "kind": "anchor",
        "lifecycle": "operational",
    },
    {
        "agent_id": "output-delivery",
        "name": "Output",
        "pipeline_order": 130,
        "kind": "anchor",
        "lifecycle": "in_development",
    },
)

PIPELINE_STAGE_STATUS = (
    "queued",
    "running",
    "completed",
    "warning",
    "failed",
    "retrying",
    "skipped",
    "waiting",
    "not_implemented",
    "not_started",
)


def catalog_by_id() -> dict[str, AgentContract]:
    return {agent.agent_id: agent for agent in AGENT_CATALOG}


def operational_agents() -> tuple[AgentContract, ...]:
    return tuple(a for a in AGENT_CATALOG if a.lifecycle == "operational")


def development_agents() -> tuple[AgentContract, ...]:
    return tuple(a for a in AGENT_CATALOG if a.lifecycle == "in_development")


def empty_metrics() -> dict[str, Any]:
    """Placeholder metrics — never filled with invented production numbers."""
    return {
        "active_executions": None,
        "total_executions": None,
        "success_count": None,
        "failure_count": None,
        "success_rate": None,
        "failure_rate": None,
        "average_latency_ms": None,
        "p50_latency_ms": None,
        "p95_latency_ms": None,
        "p99_latency_ms": None,
        "last_execution_at": None,
        "availability": "not_applicable",
        "note": "Runtime not available while this agent is in development.",
    }


def unavailable_metrics(note: str) -> dict[str, Any]:
    return {
        "active_executions": None,
        "total_executions": None,
        "success_count": None,
        "failure_count": None,
        "success_rate": None,
        "failure_rate": None,
        "average_latency_ms": None,
        "p50_latency_ms": None,
        "p95_latency_ms": None,
        "p99_latency_ms": None,
        "last_execution_at": None,
        "availability": "unavailable",
        "note": note,
    }


STATUS_LABELS: Mapping[str, str] = {
    "HEALTHY": "Healthy",
    "RUNNING": "Running",
    "IDLE": "Ready",
    "DEGRADED": "Needs attention",
    "FAILED": "Failed",
    "OFFLINE": "Unavailable",
    "RETRYING": "Retrying",
    "WAITING": "Waiting",
    "IN_DEVELOPMENT": "In development",
    "UNKNOWN": "Unknown",
}
