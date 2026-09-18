"""Provider factory — builds the configured LLMProvider from Settings."""

from __future__ import annotations

from perfagent.config import Settings, get_settings
from perfagent.providers.base import LLMProvider


def build_provider(settings: Settings | None = None) -> LLMProvider:
    """Construct the provider named in settings.llm_provider."""
    settings = settings or get_settings()
    choice = settings.llm_provider.lower()

    if choice == "openai":
        from perfagent.providers.openai_provider import OpenAIProvider

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set (see .env).")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            max_tokens=settings.max_tokens,
        )

    if choice == "anthropic":
        from perfagent.providers.anthropic_provider import AnthropicProvider

        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set (see .env).")
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            max_tokens=settings.max_tokens,
        )

    raise ValueError(
        f"unknown llm_provider {settings.llm_provider!r}; use 'openai' or 'anthropic'"
    )


__all__ = ["LLMProvider", "build_provider"]
