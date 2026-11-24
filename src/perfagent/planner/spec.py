"""Planner input types: what the user supplies to get a plan drafted."""

from __future__ import annotations

from math import isfinite

from pydantic import BaseModel, Field, field_validator, model_validator

from perfagent.contracts.load_model import Assertion, HttpMethod, LoadProfileType, Stage, Threshold


class EndpointSpec(BaseModel):
    """One endpoint the user wants covered."""

    method: HttpMethod = HttpMethod.GET
    path: str
    description: str | None = None
    example_body: dict | None = None
    assertions: list[Assertion] | None = None

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
    project_id: str | None = None
    test_name: str = Field(default="", max_length=120)
    max_users: int = Field(default=100, gt=0)
    duration_seconds: int = Field(default=300, gt=0)
    profile_type: LoadProfileType = LoadProfileType.RAMP
    environment: str = ""
    insecure_tls: bool = False
    thresholds: list[Threshold] | None = None

    target_request_rate: int | None = Field(default=None, ge=1, le=1_000_000)
    stages: list[Stage] | None = Field(default=None, min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_workload(self) -> "PlanRequest":
        if self.target_request_rate is not None:
            if len(self.endpoints) != 1:
                raise ValueError("A request-rate target requires exactly one endpoint.")
            if self.stages is not None or self.profile_type != LoadProfileType.RAMP:
                raise ValueError("A constant request-rate target uses a duration instead of VU stages.")
        if self.stages is not None:
            if sum(stage.duration_seconds for stage in self.stages) != self.duration_seconds:
                raise ValueError("Stage durations must add up to the total duration.")
            if max(stage.target_users for stage in self.stages) != self.max_users:
                raise ValueError("The largest stage target must equal the requested peak users.")
        return self

    @field_validator("thresholds")
    @classmethod
    def known_thresholds(cls, values: list[Threshold] | None) -> list[Threshold] | None:
        for threshold in values or []:
            metric, value = threshold.metric, threshold.value
            if metric not in {"error_rate", "p50_ms", "p90_ms", "p95_ms", "p99_ms",
                              "avg_ms", "median_ms", "max_ms"} or not isfinite(value):
                raise ValueError("Choose a supported threshold metric and a finite limit.")
            if value < 0 or (metric == "error_rate" and value > 1):
                raise ValueError("Latency limits must be nonnegative and error rate must be between 0 and 1.")
        return values

    @field_validator("target_base_url")
    @classmethod
    def url_looks_valid(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("target_base_url must start with http:// or https://")
        return v.rstrip("/")
