"""Planner input types: what the user supplies to get a plan drafted."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from perfagent.contracts.load_model import HttpMethod, LoadProfileType


class EndpointSpec(BaseModel):
    """One endpoint the user wants covered."""

    method: HttpMethod = HttpMethod.GET
    path: str
    description: str | None = None
    example_body: dict | None = None

    @field_validator("path")
    @classmethod
    def path_must_start_with_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError(f"path must start with '/': got {v!r}")
        return v


class PlanRequest(BaseModel):
    """Everything the Planner needs to draft a LoadModel."""

    target_base_url: str
    endpoints: list[EndpointSpec] = Field(..., min_length=1)
    goal: str = ""
    max_users: int = Field(default=100, gt=0)
    duration_seconds: int = Field(default=300, gt=0)
    profile_type: LoadProfileType = LoadProfileType.RAMP

    @field_validator("target_base_url")
    @classmethod
    def url_looks_valid(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("target_base_url must start with http:// or https://")
        return v.rstrip("/")