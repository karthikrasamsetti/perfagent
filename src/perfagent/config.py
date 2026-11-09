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

    # Logging level for the structured logs (DEBUG | INFO | WARNING | ERROR).
    log_level: str = Field(default="INFO")

    # Guardrail debug: when true, logs the REDACTED prompt actually sent to the LLM
    # (and output-scrub results) so you can confirm no sensitive data survives.
    # Logs only the redacted text, never raw secrets. Keep false for normal use.
    guardrail_debug: bool = Field(default=False)

    # ---- k6 load engine -------------------------------------------------------
    # k6 is found or downloaded automatically (see runner/k6_binary.py). Set this to
    # use a specific k6 binary instead, e.g. on machines without internet access.
    perfagent_k6_path: str = Field(default="")
    # Base folder for PerfAgent's own files, including the downloaded k6.
    # Empty = ~/.perfagent
    perfagent_home: str = Field(default="")

    # ---- Git export / import ---------------------------------------------------
    # The repository URL, branch and access token are entered by the user in the
    # UI for each push or import and are never stored. These are server-side options.
    git_author_name: str = Field(default="PerfAgent")
    git_author_email: str = Field(default="perfagent@localhost")
    # Comma-separated Git hosts users may push to / import from, e.g.
    # "github.com,dev.azure.com". Empty = any host. Recommended when hosted.
    git_allowed_hosts: str = Field(default="")
    # Allow file:// and local paths as repositories (tests / local demos only).
    git_allow_local: bool = Field(default=False)


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so we don't re-read the env on every call."""
    return Settings()