"""Configuration — reads settings and secrets from the environment.

Copy `.env.example` to `.env` and fill in your keys. Nothing else in the code
reads os.environ directly; everything goes through this Settings object.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Which provider to use for planning: "openai" or "anthropic".
    llm_provider: str = Field(default="openai")

    # API keys (leave blank for whichever provider you are not using).
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")

    # Model names — override in .env if you want different models.
    openai_model: str = Field(default="gpt-4o-2024-11-20")
    anthropic_model: str = Field(default="claude-sonnet-4-5-20250929")

    # Max tokens for the planning response.
    max_tokens: int = Field(default=4096)


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so we don't re-read the env on every call."""
    return Settings()
