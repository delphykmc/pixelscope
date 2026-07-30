from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from pixelscope.remote.schemas import (
    EvaluationJobCreated,
    EvaluationJobStatus,
    EvaluationRequest,
    EvaluationResult,
)


class EvaluationClient(ABC):
    """Synchronous job client; callers must run network methods in a worker."""

    @abstractmethod
    def create_job(self, request: EvaluationRequest) -> EvaluationJobCreated:
        raise NotImplementedError

    @abstractmethod
    def get_status(self, job_id: str) -> EvaluationJobStatus:
        raise NotImplementedError

    @abstractmethod
    def get_result(self, job_id: str) -> EvaluationResult:
        raise NotImplementedError

    @abstractmethod
    def cancel_job(self, job_id: str) -> EvaluationJobStatus:
        raise NotImplementedError


class HttpEvaluationClient(EvaluationClient):
    """Minimal v1 HTTP transport with finite timeouts and TLS verification."""

    def __init__(
        self,
        base_url: str,
        bearer_token: str | None = None,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not base_url.lower().startswith("https://") and transport is None:
            raise ValueError("production evaluation URLs must use HTTPS")
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
        self._client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout_seconds),
            verify=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def create_job(self, request: EvaluationRequest) -> EvaluationJobCreated:
        response = self._client.post("/v1/jobs", json=request.dict(exclude_none=True))
        response.raise_for_status()
        return EvaluationJobCreated.parse_obj(response.json())

    def get_status(self, job_id: str) -> EvaluationJobStatus:
        response = self._client.get(f"/v1/jobs/{job_id}")
        response.raise_for_status()
        return EvaluationJobStatus.parse_obj(response.json())

    def get_result(self, job_id: str) -> EvaluationResult:
        response = self._client.get(f"/v1/jobs/{job_id}/result")
        response.raise_for_status()
        return EvaluationResult.parse_obj(response.json())

    def cancel_job(self, job_id: str) -> EvaluationJobStatus:
        response = self._client.post(f"/v1/jobs/{job_id}/cancel")
        response.raise_for_status()
        return EvaluationJobStatus.parse_obj(response.json())

    def __enter__(self) -> HttpEvaluationClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
