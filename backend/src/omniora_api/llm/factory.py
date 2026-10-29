from __future__ import annotations

from ..config import Settings
from .anthropic_provider import AnthropicProvider
from .base import ModelProvider
from .groq_provider import GroqProvider


def build_planning_provider(settings: Settings) -> ModelProvider:
    """The provider used by the Project Manager agent, chosen by OMNIORA_MODEL_PROVIDER.

    Only the selected provider's credential is used. A provider without credentials raises
    `ModelError('not-configured')` instead of fabricating responses.
    """
    if settings.model_provider == "groq":
        return GroqProvider(
            api_key=settings.model_api_key,
            model=settings.planning_model,
            max_retries=settings.model_transport_retries,
        )
    return AnthropicProvider(
        api_key=settings.model_api_key,
        model=settings.planning_model,
        max_retries=settings.model_transport_retries,
        refusal_fallback=settings.anthropic_refusal_fallback,
    )
