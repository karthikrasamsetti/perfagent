"""The LoadModel — the tool-agnostic contract at the centre of the pipeline.

Every stage reads or writes this. The Planner drafts it; the Generator renders it to
a runnable script. Plain, validated data — no tool-specific details leak in here.

Supports data-file parameterization (${field} from a CSV row), global headers, and
correlation: a step can EXTRACT a value from its response into a variable that later
steps reference as ${var} (e.g. capture a login token, reuse it on protected calls).
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


class Extract(BaseModel):
    """Capture a value from a step's response into a variable for later steps.

    var  — the variable name; later steps reference it as ${var}
    source — where to read from: 'json' (a field path in the JSON body)
    path — for json: a dotted field path, e.g. 'token' or 'data.id'
    """

    var: str = Field(..., description="Variable name, usable later as ${var}.")
    source: str = Field(default="json", description="json (JSON body field path).")
    path: str = Field(..., description="For json: dotted path, e.g. 'token' or 'data.id'.")

    @field_validator("var")
    @classmethod
    def var_is_identifier(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError(f"extract var must be a simple identifier: {v!r}")
        return v

    @field_validator("source")
    @classmethod
    def known_source(cls, v: str) -> str:
        if v not in {"json"}:
            raise ValueError("only 'json' extraction is supported for now")
        return v


class Step(BaseModel):
    """A single request within a scenario (one call in a user journey).

    Paths, bodies and header values may contain ${name} placeholders filled from a
    data-file row OR from a variable captured earlier via `extract`.
    """

    name: str = Field(..., description="Human-readable label, e.g. 'view products'.")
    method: HttpMethod = HttpMethod.GET
    path: str = Field(..., description="Path relative to the target base URL.")
    body: dict | None = Field(default=None, description="JSON body for POST/PUT/PATCH.")
    extract: list[Extract] = Field(
        default_factory=list,
        description="Values to capture from this response for later steps.",
    )

    @field_validator("path")
    @classmethod
    def path_must_start_with_slash(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError(f"path must start with '/': got {v!r}")
        return v


class ThinkTime(BaseModel):
    min_seconds: float = Field(1.0, ge=0)
    max_seconds: float = Field(3.0, ge=0)

    @model_validator(mode="after")
    def check_order(self) -> ThinkTime:
        if self.max_seconds < self.min_seconds:
            raise ValueError("max_seconds must be >= min_seconds")
        return self


class Scenario(BaseModel):
    name: str
    weight: float = Field(1.0, gt=0)
    steps: list[Step] = Field(..., min_length=1)
    think_time: ThinkTime = Field(default_factory=ThinkTime)


class LoadProfileType(str, Enum):
    RAMP = "ramp"
    SPIKE = "spike"
    SOAK = "soak"
    STRESS = "stress"


class Stage(BaseModel):
    duration_seconds: int = Field(..., gt=0)
    target_users: int = Field(..., ge=0)


class LoadProfile(BaseModel):
    type: LoadProfileType = LoadProfileType.RAMP
    stages: list[Stage] = Field(..., min_length=1)

    @property
    def peak_users(self) -> int:
        return max(s.target_users for s in self.stages)

    @property
    def total_seconds(self) -> int:
        return sum(s.duration_seconds for s in self.stages)


class Threshold(BaseModel):
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
    filename: str = Field(..., description="e.g. 'users.csv'.")
    fields: list[str] = Field(..., min_length=1)
    row_count: int = Field(default=0, ge=0)
    source_format: str = Field(default="csv")


class LoadModel(BaseModel):
    target_base_url: str
    scenarios: list[Scenario] = Field(..., min_length=1)
    load_profile: LoadProfile
    thresholds: list[Threshold] = Field(default_factory=list)
    data_file: DataFile | None = None
    headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("target_base_url")
    @classmethod
    def url_looks_valid(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("target_base_url must start with http:// or https://")
        return v.rstrip("/")

    def normalised_weights(self) -> list[float]:
        total = sum(s.weight for s in self.scenarios)
        return [s.weight / total for s in self.scenarios]