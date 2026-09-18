"""The Planner's input: a description of the endpoints to test.

This is what the team supplies today (by hand). Later, the discovery stage will
produce this same structure automatically by crawling a site or parsing traffic.
Keeping it as an explicit contract means the Planner never changes when the source
of endpoints changes.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from perfagent.contracts.load_model import HttpMethod


class EndpointSpec(BaseModel):
    """One endpoint the system exposes."""

    method: HttpMethod = HttpMethod.GET
    path: str = Field(..., description="Path relative to the target, e.g. '/products'.")
    description: str | None = Field(
        default=None, description="Optional hint about what this endpoint does."
    )
    example_body: dict | None = Field(
        default=None, description="Optional example request body for POST/PUT/PATCH."
    )

    @field_validator("path")
    @classmethod
    def path_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError(f"path must start with '/': {v!r}")
        return v


class PlanRequest(BaseModel):
    """Everything the Planner needs to draft a LoadModel."""

    target_base_url: str
    endpoints: list[EndpointSpec] = Field(..., min_length=1)
    goal: str = Field(
        default="A realistic load test of the main user journeys.",
        description="Plain-language intent, e.g. 'spike test the checkout flow'.",
    )
    # Optional guard rails the human can set up front.
    max_users: int = Field(default=100, gt=0)
    duration_seconds: int = Field(default=300, gt=0)

    @field_validator("target_base_url")
    @classmethod
    def url_ok(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("target_base_url must start with http:// or https://")
        return v.rstrip("/")
