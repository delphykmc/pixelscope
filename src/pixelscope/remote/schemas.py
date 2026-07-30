from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvaluationRequest(BaseModel):
    api_schema_version: str = "1.0"
    model_id: str
    input_sha256: str = Field(regex=r"^[0-9a-f]{64}$")
    file_name: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class EvaluationJobCreated(BaseModel):
    job_id: str
    api_schema_version: str = "1.0"
    created_at: datetime


class EvaluationJobStatus(BaseModel):
    job_id: str
    state: JobState
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    message: str | None = None


class EvaluationMetric(BaseModel):
    name: str
    value: float
    unit: str | None = None
    attributes: dict[str, float] = Field(default_factory=dict)


class EvaluationArtifact(BaseModel):
    artifact_id: str
    kind: str
    media_type: str
    download_url: str | None = None
    width: int | None = None
    height: int | None = None
    inline_values: list[list[float]] | None = None


class EvaluationError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    api_schema_version: str = "1.0"
    job_id: str
    input_sha256: str
    model_id: str
    model_version: str
    preprocessing_version: str
    created_at: datetime
    elapsed_seconds: float = Field(ge=0.0)
    metrics: list[EvaluationMetric] = Field(default_factory=list)
    artifacts: list[EvaluationArtifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: EvaluationError | None = None
