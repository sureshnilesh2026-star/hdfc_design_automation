"""Intent Recognition Agent package."""

from hdfc_journey.agents.intent.agent import (
    IntentRecognitionAgent,
    create_intent_agent,
)
from hdfc_journey.agents.intent.errors import (
    IntentAgentError,
    IntentBoundaryError,
)
from hdfc_journey.agents.intent.prompts import (
    INTENT_PROMPT_VERSION,
    INTENT_RECOGNITION_SYSTEM_PROMPT,
    build_intent_system_prompt,
    build_intent_user_message,
)

__all__ = [
    "INTENT_PROMPT_VERSION",
    "INTENT_RECOGNITION_SYSTEM_PROMPT",
    "IntentAgentError",
    "IntentBoundaryError",
    "IntentRecognitionAgent",
    "build_intent_system_prompt",
    "build_intent_user_message",
    "create_intent_agent",
]
