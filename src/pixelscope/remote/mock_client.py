from __future__ import annotations

from datetime import datetime, timezone

from pixelscope.remote.evaluation_client import EvaluationClient
from pixelscope.remote.schemas import (
    EvaluationArtifact,
    EvaluationJobCreated,
    EvaluationJobStatus,
    EvaluationMetric,
    EvaluationRequest,
    EvaluationResult,
    JobState,
)


class MockEvaluationClient(EvaluationClient):
    """Deterministic in-memory evaluator for UI and contract tests."""

    def __init__(self) -> None:
        self._requests: dict[str, EvaluationRequest] = {}
        self._cancelled: set[str] = set()

    def create_job(self, request: EvaluationRequest) -> EvaluationJobCreated:
        job_id = f"mock-{request.input_sha256[:12]}"
        self._requests[job_id] = request.copy(deep=True)
        return EvaluationJobCreated(
            job_id=job_id,
            created_at=datetime.now(timezone.utc),
        )

    def _require(self, job_id: str) -> EvaluationRequest:
        try:
            return self._requests[job_id]
        except KeyError as exc:
            raise KeyError(f"unknown mock job: {job_id}") from exc

    def get_status(self, job_id: str) -> EvaluationJobStatus:
        self._require(job_id)
        state = JobState.CANCELLED if job_id in self._cancelled else JobState.SUCCEEDED
        return EvaluationJobStatus(job_id=job_id, state=state, progress=1.0)

    def get_result(self, job_id: str) -> EvaluationResult:
        request = self._require(job_id)
        if job_id in self._cancelled:
            raise RuntimeError("cancelled jobs do not have a result")
        raw_score = int(request.input_sha256[:8], 16) / float(0xFFFFFFFF)
        heatmap = [
            [round((raw_score + (row * 4 + column) / 31.0) % 1.0, 6) for column in range(4)]
            for row in range(4)
        ]
        return EvaluationResult(
            job_id=job_id,
            input_sha256=request.input_sha256,
            model_id=request.model_id,
            model_version="mock-1.0",
            preprocessing_version="mock-preprocess-1.0",
            created_at=datetime.now(timezone.utc),
            elapsed_seconds=0.001,
            metrics=[
                EvaluationMetric(
                    name="quality",
                    value=round(raw_score, 6),
                    attributes={"detail": round(1.0 - raw_score, 6)},
                )
            ],
            artifacts=[
                EvaluationArtifact(
                    artifact_id=f"{job_id}-heatmap",
                    kind="heatmap",
                    media_type="application/x-pixelscope-float-map",
                    width=4,
                    height=4,
                    inline_values=heatmap,
                )
            ],
            metadata={"deterministic": True},
        )

    def cancel_job(self, job_id: str) -> EvaluationJobStatus:
        self._require(job_id)
        self._cancelled.add(job_id)
        return EvaluationJobStatus(job_id=job_id, state=JobState.CANCELLED, progress=1.0)
