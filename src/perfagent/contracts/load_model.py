"""The LoadModel — the tool-agnostic contract at the centre of the pipeline.

Every stage reads or writes this. The Planner (later) drafts it; the Generator
renders it to a runnable script for the chosen tool. It is deliberately a plain,
validated data structure — no tool-specific details leak in here.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class Step(BaseModel):
    """A single request within a scenario (one call in a user journey).

    Paths and bodies may contain ${field} placeholders that are filled per virtual
    user from the LoadModel's data_file (see DataFile below).
    """

    name: str = Field(..., description="Human-readable label, e.g. 'view products'.")
    method: HttpMethod = HttpMethod.GET
    path: str = Field(..., description="Path relative to the target base URL, e.g. '/products'.")
    body: dict | None = Field(
        default=None, description="JSON body for POST/PUT/PATCH; None for GET/DELETE."
    )

    @field_validator("path")
    @classmethod
    def path_must_start_with_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError(f"path must start with '/': got {v!r}")
        return v


class ThinkTime(BaseModel):
    """Pause between steps, in seconds. A range renders as a random wait."""

    min_seconds: float = Field(1.0, ge=0)
    max_seconds: float = Field(3.0, ge=0)

    @model_validator(mode="after")
    def check_order(self) -> ThinkTime:
        if self.max_seconds < self.min_seconds:
            raise ValueError("max_seconds must be >= min_seconds")
        return self


class Scenario(BaseModel):
    """A named user journey: an ordered list of steps, plus its share of traffic."""

    name: str
    weight: float = Field(
        1.0, gt=0, description="Relative share of virtual users. Weights are normalised."
    )
    steps: list[Step] = Field(..., min_length=1)
    think_time: ThinkTime = Field(default_factory=ThinkTime)


class LoadProfileType(str, Enum):
    RAMP = "ramp"
    SPIKE = "spike"
    SOAK = "soak"
    STRESS = "stress"


class Stage(BaseModel):
    """One phase of the load over time: hold `target_users` for `duration_seconds`."""

    duration_seconds: int = Field(..., gt=0)
    target_users: int = Field(..., ge=0)


class LoadProfile(BaseModel):
    """How load changes over the run — a shape plus the stages that realise it."""

    type: LoadProfileType = LoadProfileType.RAMP
    stages: list[Stage] = Field(..., min_length=1)

    @property
    def peak_users(self) -> int:
        return max(s.target_users for s in self.stages)

    @property
    def total_seconds(self) -> int:
        return sum(s.duration_seconds for s in self.stages)


class Threshold(BaseModel):
    """A pass/fail bound. Owned by code later — declared here so it travels with the plan."""

    metric: str = Field(..., description="e.g. 'p95_ms', 'error_rate'.")
    op: str = Field(..., description="Comparison operator: '<', '<=', '>', '>='.")
    value: float

    @field_validator("op")
    @classmethod
    def known_op(cls, v: str) -> str:
        if v not in {"<", "<=", ">", ">="}:
            raise ValueError(f"unsupported operator {v!r}")
        return v


class DataFile(BaseModel):
    """A test-data file the run parameterizes requests from.

    Only the field names (schema) and metadata live here — never the actual values,
    which stay with the deterministic runner and never reach the LLM. Steps reference
    these fields as ${field} in their path or body.
    """

    filename: str = Field(..., description="e.g. 'users.csv'.")
    fields: list[str] = Field(
        ..., min_length=1, description="Column/field names available as ${field}."
    )
    row_count: int = Field(default=0, ge=0, description="Number of data rows.")
    source_format: str = Field(
        default="csv", description="csv | tsv | txt | json | jsonl."
    )


class LoadModel(BaseModel):
    """The whole plan: what to hit, which journeys, how hard, and the pass criteria."""

    target_base_url: str = Field(..., description="Base URL of the system under test.")
    scenarios: list[Scenario] = Field(..., min_length=1)
    load_profile: LoadProfile
    thresholds: list[Threshold] = Field(default_factory=list)
    data_file: DataFile | None = Field(
        default=None,
        description="Optional test data; steps may reference its fields as ${field}.",
    )

    @field_validator("target_base_url")
    @classmethod
    def url_looks_valid(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("target_base_url must start with http:// or https://")
        return v.rstrip("/")

    def normalised_weights(self) -> list[float]:
        """Scenario weights as fractions summing to 1.0."""
        total = sum(s.weight for s in self.scenarios)
        return [s.weight / total for s in self.scenarios]