"""Deterministic client-side compatibility probe for the frozen P5-C job contract."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from pixelscope.remote.iqa_client import IqaClientError, IqaClientErrorKind, IqaJobClient
from pixelscope.remote.iqa_submission import IqaJobRequest, IqaResultReference, JobState

PROBE_ENDPOINTS = (
    "POST /v1/iqa/jobs",
    "GET /v1/iqa/jobs/{job_id}",
    "GET /v1/iqa/jobs/{job_id}/result",
    "POST /v1/iqa/jobs/{job_id}/cancel",
)


@dataclass(frozen=True)
class IqaProbeOperation:
    operation: str
    duration_ms: float
    state: str | None = None
    completed_scenes: int | None = None
    total_scenes: int | None = None


@dataclass(frozen=True)
class IqaCompatibilityTrace:
    """Bounded probe output containing protocol metadata, never request bodies or paths."""

    endpoints: tuple[str, ...]
    job_id: str | None
    state_sequence: tuple[str, ...]
    operations: tuple[IqaProbeOperation, ...]
    terminal_state: str | None
    result_schema_version: int | None
    result_publication_state: str | None
    result_storage_root_id: str | None
    result_relative_path: str | None
    error_kind: str | None
    error_message: str | None


def run_iqa_compatibility_probe(
    client: IqaJobClient,
    request: IqaJobRequest,
    *,
    max_status_requests: int = 64,
    cancel_after_status_requests: int | None = None,
    poll_pause: Callable[[], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> IqaCompatibilityTrace:
    """Exercise create/status/result/cancel without retries or overlapping requests.

    ``poll_pause`` is injectable so tests remain deterministic while an owner-side live
    probe may provide a bounded sleep. CREATE is issued exactly once. Cancel is issued
    at most once; a non-terminal cancel response remains server-owned state and polling
    continues until a terminal state or the actual status-request bound.
    """

    if max_status_requests < 1:
        raise ValueError("max_status_requests must be positive")
    if cancel_after_status_requests is not None and cancel_after_status_requests < 1:
        raise ValueError("cancel_after_status_requests must be positive when supplied")

    operations: list[IqaProbeOperation] = []
    states: list[str] = []
    job_id: str | None = None
    reference: IqaResultReference | None = None
    observed_state: JobState | None = None

    try:
        started = clock()
        created = client.create_job(request)
        duration = max(0.0, (clock() - started) * 1000.0)
        job_id = created.job_id
        observed_state = created.state
        states.append(created.state.value)
        operations.append(IqaProbeOperation("create", duration, created.state.value))

        status_requests = 0
        cancel_issued = False
        while not observed_state.terminal and status_requests < max_status_requests:
            if poll_pause is not None:
                poll_pause()
            started = clock()
            status = client.get_status(created.job_id)
            duration = max(0.0, (clock() - started) * 1000.0)
            status_requests += 1
            observed_state = status.state
            states.append(status.state.value)
            operations.append(
                IqaProbeOperation(
                    "status",
                    duration,
                    status.state.value,
                    status.completed_scenes,
                    status.total_scenes,
                )
            )
            if (
                cancel_after_status_requests is not None
                and not cancel_issued
                and status_requests >= cancel_after_status_requests
                and not observed_state.terminal
            ):
                started = clock()
                status = client.cancel_job(created.job_id)
                duration = max(0.0, (clock() - started) * 1000.0)
                cancel_issued = True
                observed_state = status.state
                states.append(status.state.value)
                operations.append(
                    IqaProbeOperation(
                        "cancel",
                        duration,
                        status.state.value,
                        status.completed_scenes,
                        status.total_scenes,
                    )
                )

        if not observed_state.terminal:
            return _status_limit_trace(job_id, states, operations)

        if observed_state in {JobState.SUCCEEDED, JobState.PARTIAL}:
            started = clock()
            reference = client.get_result(created.job_id)
            duration = max(0.0, (clock() - started) * 1000.0)
            operations.append(IqaProbeOperation("result", duration, observed_state.value))
            _validate_terminal_publication(observed_state, reference)

        return _trace(job_id, states, operations, observed_state, reference, None)
    except IqaClientError as error:
        terminal = (
            observed_state if observed_state is not None and observed_state.terminal else None
        )
        return _trace(job_id, states, operations, terminal, reference, error)


def _validate_terminal_publication(
    terminal: JobState,
    reference: IqaResultReference,
) -> None:
    expected_publication = "complete" if terminal is JobState.SUCCEEDED else "partial"
    if reference.publication_state != expected_publication:
        raise IqaClientError(
            IqaClientErrorKind.PROTOCOL,
            "terminal state/result publication mismatch",
        )


def _status_limit_trace(
    job_id: str,
    states: list[str],
    operations: list[IqaProbeOperation],
) -> IqaCompatibilityTrace:
    return IqaCompatibilityTrace(
        endpoints=PROBE_ENDPOINTS,
        job_id=job_id,
        state_sequence=tuple(states),
        operations=tuple(operations),
        terminal_state=None,
        result_schema_version=None,
        result_publication_state=None,
        result_storage_root_id=None,
        result_relative_path=None,
        error_kind="status_limit",
        error_message="status request limit reached before terminal state",
    )


def _trace(
    job_id: str | None,
    states: list[str],
    operations: list[IqaProbeOperation],
    terminal: JobState | None,
    reference: IqaResultReference | None,
    error: IqaClientError | None,
) -> IqaCompatibilityTrace:
    error_message: str | None = None
    if error is not None:
        error_message = (
            f"HTTP {error.status_code}" if error.status_code is not None else error.kind.value
        )
    return IqaCompatibilityTrace(
        endpoints=PROBE_ENDPOINTS,
        job_id=job_id,
        state_sequence=tuple(states),
        operations=tuple(operations),
        terminal_state=terminal.value if terminal is not None else None,
        result_schema_version=reference.schema_version if reference is not None else None,
        result_publication_state=reference.publication_state if reference is not None else None,
        result_storage_root_id=reference.storage_root_id if reference is not None else None,
        result_relative_path=reference.relative_path if reference is not None else None,
        error_kind=error.kind.value if error is not None else None,
        error_message=error_message,
    )
