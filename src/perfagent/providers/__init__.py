"""Provider factory — builds the configured LLMProvider from Settings.

Every provider is wrapped in GuardedProvider, so all LLM calls (planning and
reporting) pass through the data guardrails: sensitive data is redacted before it
reaches the model, and the response is scrubbed on the way back.
"""

from __future__ import annotations

from perfagent.config import Settings, get_settings
from perfagent.guardrails import GuardedProvider
from perfagent.providers.base import LLMProvider


def build_provider(settings: Settings | None = None) -> LLMProvider:
    """Construct the provider named in settings.llm_provider, wrapped with guardrails."""
    settings = settings or get_settings()
    choice = settings.llm_provider.lower()

    if choice == "openai":
        from perfagent.providers.openai_provider import OpenAIProvider

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set (see .env).")
        provider: LLMProvider = OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_tokens=settings.max_tokens,
        )

    elif choice == "anthropic":
        from perfagent.providers.anthropic_provider import AnthropicProvider

        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set (see .env).")
        provider = AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            max_tokens=settings.max_tokens,
        )

    else:
        raise ValueError(
            f"unknown llm_provider {settings.llm_provider!r}; use 'openai' or 'anthropic'"
        )

    # Wrap once — protects both the planner and the reporter automatically.
    return GuardedProvider(provider)


__all__ = ["LLMProvider", "build_provider"]