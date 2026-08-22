"""Synchronous Qt-free HTTP client for the P5-C IQA job API."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import httpx

from pixelscope.core.cancellation import cancellation_checkpoint
from pixelscope.remote.iqa_submission import (
    IqaJobCreated,
    IqaJobRequest,
    IqaJobStatus,
    IqaResultReference,
    JobState,
)


class IqaClientErrorKind(str, Enum):
    """Stable error classes suitable for UI diagnostics and localhost fault tests."""

    CONFIG = "config"
    CONNECT = "connect"
    TIMEOUT = "timeout"
    HTTP = "http"
    PROTOCOL = "protocol"
    STORAGE = "storage"


class IqaClientError(RuntimeError):
    """Bounded classified client error suitable for Jobs UI display."""

    def __init__(
        self,
        kind: IqaClientErrorKind,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        self.kind = kind
        self.detail = _bounded_text(message)
        self.status_code = status_code
        super().__init__(f"{kind.value}: {self.detail}")


class IqaCreateOutcomeUnknown(IqaClientError):
    """The create POST may have reached the server, but no durable job ID was confirmed."""


class IqaJobClient(ABC):
    """Synchronous interface; every call must be scheduled outside the Qt UI thread."""

    @abstractmethod
    def create_job(self, request: IqaJobRequest) -> IqaJobCreated:
        raise NotImplementedError

    @abstractmethod
    def get_status(self, job_id: str) -> IqaJobStatus:
        raise NotImplementedError

    @abstractmethod
    def get_result(self, job_id: str) -> IqaResultReference:
        raise NotImplementedError

    @abstractmethod
    def cancel_job(self, job_id: str) -> IqaJobStatus:
        raise NotImplementedError

    def close(self) -> None:
        return None


class HttpIqaJobClient(IqaJobClient):
    """Finite-timeout HTTP transport for the IQA-specific REST endpoints."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if timeout_seconds <= 0.0:
            raise ValueError("timeout_seconds must be positive")
        try:
            parsed = httpx.URL(base_url)
        except (httpx.InvalidURL, TypeError, ValueError) as exc:
            raise IqaClientError(IqaClientErrorKind.CONFIG, "server base URL is invalid") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.host:
            raise IqaClientError(
                IqaClientErrorKind.CONFIG,
                "server base URL must use http or https and include a host",
            )
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            verify=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def create_job(self, request: IqaJobRequest) -> IqaJobCreated:
        # Final cooperative checkpoint before the non-idempotent create POST.
        cancellation_checkpoint()
        try:
            data = self._request_json("POST", "/v1/iqa/jobs", json=request.to_json())
            job_id = _job_id(_required_string(data, "job_id"))
            state = _job_state(data.get("state", JobState.QUEUED.value))
            if state.terminal:
                raise _protocol_error("create-job response unexpectedly reported a terminal state")
            return IqaJobCreated(job_id, state)
        except IqaClientError as exc:
            if _create_outcome_is_ambiguous(exc):
                raise IqaCreateOutcomeUnknown(
                    exc.kind,
                    "create outcome unknown; server may have accepted the job; "
                    f"do not blindly resubmit · {exc.detail}",
                    status_code=exc.status_code,
                ) from exc
            raise

    def get_status(self, job_id: str) -> IqaJobStatus:
        data = self._request_json("GET", f"/v1/iqa/jobs/{_job_id(job_id)}")
        returned_id = _job_id(_required_string(data, "job_id"))
        if returned_id != job_id:
            raise _protocol_error("job status identity mismatch")
        completed = _optional_nonnegative_int(data, "completed_scenes")
        total = _optional_nonnegative_int(data, "total_scenes")
        if completed is not None and total is not None and completed > total:
            raise _protocol_error("job progress is invalid")
        return IqaJobStatus(
            returned_id,
            _job_state(data.get("state")),
            completed,
            total,
            _optional_string(data, "message"),
        )

    def get_result(self, job_id: str) -> IqaResultReference:
        data = self._request_json("GET", f"/v1/iqa/jobs/{_job_id(job_id)}/result")
        returned_id = _job_id(_required_string(data, "job_id"))
        if returned_id != job_id:
            raise _protocol_error("result reference job identity mismatch")
        publication_state = _required_string(data, "publication_state")
        if publication_state not in {"complete", "partial"}:
            raise _protocol_error("result reference publication_state must be complete or partial")
        schema_version = _required_int(data, "schema_version")
        if schema_version != 2:
            raise _protocol_error("P5-C result reference must identify schema_version 2")
        return IqaResultReference(
            returned_id,
            _required_string(data, "storage_root_id"),
            _required_string(data, "relative_path"),
            schema_version,
            publication_state,
        )

    def cancel_job(self, job_id: str) -> IqaJobStatus:
        data = self._request_json(
            "POST",
            f"/v1/iqa/jobs/{_job_id(job_id)}/cancel",
        )
        returned_id = _job_id(_required_string(data, "job_id"))
        if returned_id != job_id:
            raise _protocol_error("cancel response job identity mismatch")
        return IqaJobStatus(
            returned_id,
            _job_state(data.get("state")),
            _optional_nonnegative_int(data, "completed_scenes"),
            _optional_nonnegative_int(data, "total_scenes"),
            _optional_string(data, "message"),
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, json=json)
        except httpx.TimeoutException as exc:
            raise IqaClientError(IqaClientErrorKind.TIMEOUT, _bounded_error(exc)) from exc
        except httpx.HTTPError as exc:
            raise IqaClientError(IqaClientErrorKind.CONNECT, _bounded_error(exc)) from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise IqaClientError(
                IqaClientErrorKind.HTTP,
                f"HTTP {status} for {method} {path}",
                status_code=status,
            ) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise IqaClientError(
                IqaClientErrorKind.PROTOCOL,
                "server response is not valid JSON",
            ) from exc
        if not isinstance(data, dict):
            raise _protocol_error("server response must be a JSON object")
        return data


def _create_outcome_is_ambiguous(error: IqaClientError) -> bool:
    if error.kind in {
        IqaClientErrorKind.CONNECT,
        IqaClientErrorKind.TIMEOUT,
        IqaClientErrorKind.PROTOCOL,
    }:
        return True
    return (
        error.kind is IqaClientErrorKind.HTTP
        and error.status_code is not None
        and error.status_code >= 500
    )


def _job_state(value: object) -> JobState:
    if not isinstance(value, str):
        raise _protocol_error("job state is missing")
    try:
        return JobState(value)
    except ValueError as exc:
        raise _protocol_error(f"unknown job state: {value[:64]}") from exc


def _job_id(value: str) -> str:
    if not value or len(value) > 128 or any(char in value for char in "/\\\x00"):
        raise _protocol_error("job_id is invalid")
    return value


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value or len(value) > 2048 or "\x00" in value:
        raise _protocol_error(f"{key} is missing or invalid")
    return value


def _optional_string(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise _protocol_error(f"{key} must be a string")
    clean = " ".join(value.split())
    return clean[:512]


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise _protocol_error(f"{key} must be an integer")
    return value


def _optional_nonnegative_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _protocol_error(f"{key} must be a non-negative integer")
    return value


def _protocol_error(message: str) -> IqaClientError:
    return IqaClientError(IqaClientErrorKind.PROTOCOL, message)


def _bounded_error(exc: BaseException) -> str:
    text = " ".join(str(exc).split())
    return _bounded_text(text or exc.__class__.__name__)


def _bounded_text(value: str) -> str:
    clean = " ".join(value.split())
    return (clean or "Remote IQA client error")[:512]
