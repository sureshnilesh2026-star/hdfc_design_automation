"""Canonical enums shared by Planner contracts and JourneyGenerationState."""

from __future__ import annotations

from enum import StrEnum


class JourneyType(StrEnum):
    ACQUISITION = "acquisition"
    SERVICING = "servicing"
    TRANSACTION = "transaction"
    INFORMATION = "information"
    SUPPORT = "support"


class Platform(StrEnum):
    ASKNOW = "asknow"
    EVA_DBU = "eva_dbu"
    WEB = "web"
    MOBILE_NATIVE = "mobile_native"
    UNSPECIFIED = "unspecified"


class Priority(StrEnum):
    NORMAL = "normal"
    HIGH = "high"


class SkeletonStepType(StrEnum):
    INTERACTION = "interaction"
    AUTH_GATE = "auth_gate"
    DECISION = "decision"
    SYSTEM = "system"
    CONFIRMATION = "confirmation"
    TERMINAL = "terminal"


class DecisionKind(StrEnum):
    USE_SKELETON_STEP = "use_skeleton_step"
    SKIP_OPTIONAL = "skip_optional"
    BIND_ENTITY = "bind_entity"
    REQUIRE_AUTH = "require_auth"
    FLAG_ASSUMPTION = "flag_assumption"
    MARK_UNKNOWN_REQUIREMENT = "mark_unknown_requirement"
    ORDER_STEPS = "order_steps"
    REQUIRE_INFORMATION = "require_information"


class UnknownRequirementKind(StrEnum):
    API = "api"
    POLICY = "policy"
    FIELD = "field"
    CAPABILITY = "capability"
    ELIGIBILITY = "eligibility"
    FEE = "fee"
    OTHER = "other"


class AssumptionRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RequiredInfoSource(StrEnum):
    USER = "user"
    SYSTEM = "system"
    DERIVED = "derived"
    API = "api"


class PlannerStatus(StrEnum):
    """Planner artifact status — never equals Blueprint validation_status."""

    PLANNED = "planned"
    PLANNED_WITH_ASSUMPTIONS = "planned_with_assumptions"
    PLANNED_WITH_UNKNOWNS = "planned_with_unknowns"
    FAILED = "failed"


class AttributionKind(StrEnum):
    """What a planning decision cites as evidence."""

    KNOWLEDGE_DOCUMENT = "knowledge_document"
    KNOWLEDGE_CHUNK = "knowledge_chunk"
    INPUT_ENTITY = "input_entity"
    INPUT_INTENT = "input_intent"
    SKELETON_STEP = "skeleton_step"
    CONFIG = "config"
