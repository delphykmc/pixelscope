"""Deterministic fake HTTP transport for P5-C contract and lifecycle tests."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx

from pixelscope.remote.iqa_submission import JobState


@dataclass(frozen=True)
class MockJobStep:
    state: JobState
    completed_scenes: int | None = None
    total_scenes: int | None = None
    message: str | None = None


@dataclass(frozen=True)
class MockJobScript:
    steps: tuple[MockJobStep, ...]
    result_reference: dict[str, object] | None = None
    create_status_code: int = 200
    malformed_status: bool = False

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("mock job script requires at least one status step")


@dataclass
class _MockJob:
    script: MockJobScript
    index: int = 0
    cancelled: bool = False

    @property
    def step(self) -> MockJobStep:
        return self.script.steps[min(self.index, len(self.script.steps) - 1)]

    def advance(self) -> None:
        if self.index < len(self.script.steps) - 1:
            self.index += 1


class MockIqaService:
    """Stateful fake server exposed through httpx.MockTransport."""

    def __init__(self, scripts: tuple[MockJobScript, ...]) -> None:
        self._scripts = list(scripts)
        self._jobs: dict[str, _MockJob] = {}
        self._lock = Lock()
        self.request_counts: dict[tuple[str, str], int] = defaultdict(int)
        self.created_requests: list[dict[str, Any]] = []
        self._next_job = 1

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        key = (request.method, path)
        with self._lock:
            self.request_counts[key] += 1
            if request.method == "POST" and path == "/v1/iqa/jobs":
                return self._create(request)
            parts = tuple(part for part in path.split("/") if part)
            if len(parts) not in {4, 5} or parts[:3] != ("v1", "iqa", "jobs"):
                return httpx.Response(404, json={"detail": "not found"})
            job_id = parts[3]
            job = self._jobs.get(job_id)
            if job is None:
                return httpx.Response(404, json={"detail": "unknown job"})
            if len(parts) == 4 and request.method == "GET":
                return self._status(job_id, job)
            if len(parts) == 5 and parts[4] == "result" and request.method == "GET":
                return self._result(job_id, job)
            if len(parts) == 5 and parts[4] == "cancel" and request.method == "POST":
                return self._cancel(job_id, job)
            return httpx.Response(405, json={"detail": "method not allowed"})

    def _create(self, request: httpx.Request) -> httpx.Response:
        if not self._scripts:
            return httpx.Response(503, json={"detail": "no scripted job"})
        script = self._scripts.pop(0)
        try:
            payload = request.json()
        except ValueError:
            return httpx.Response(400, json={"detail": "invalid json"})
        if not isinstance(payload, dict):
            return httpx.Response(400, json={"detail": "invalid request"})
        self.created_requests.append(payload)
        if script.create_status_code >= 400:
            return httpx.Response(script.create_status_code, json={"detail": "scripted create error"})
        job_id = f"job_{self._next_job:06d}"
        self._next_job += 1
        job = _MockJob(script)
        self._jobs[job_id] = job
        state = job.step.state
        if state.terminal:
            state = JobState.QUEUED
        return httpx.Response(200, json={"job_id": job_id, "state": state.value})

    def _status(self, job_id: str, job: _MockJob) -> httpx.Response:
        if job.script.malformed_status:
            return httpx.Response(200, json={"job_id": job_id, "state": 17})
        if job.cancelled:
            return httpx.Response(200, json=self._cancelled_payload(job_id, job))
        step = job.step
        payload = self._step_payload(job_id, step)
        if not step.state.terminal:
            job.advance()
        return httpx.Response(200, json=payload)

    def _result(self, job_id: str, job: _MockJob) -> httpx.Response:
        state = self._effective_terminal_state(job)
        if state not in {JobState.SUCCEEDED, JobState.PARTIAL}:
            return httpx.Response(409, json={"detail": "result is not published"})
        reference = job.script.result_reference
        if reference is None:
            return httpx.Response(500, json={"detail": "missing scripted result"})
        payload = {"job_id": job_id, **reference}
        return httpx.Response(200, json=payload)

    def _cancel(self, job_id: str, job: _MockJob) -> httpx.Response:
        step = job.step
        if step.state.terminal:
            return httpx.Response(200, json=self._step_payload(job_id, step))
        completed = step.completed_scenes or 0
        if completed > 0 and job.script.result_reference is not None:
            terminal = MockJobStep(
                JobState.PARTIAL,
                completed_scenes=completed,
                total_scenes=step.total_scenes,
                message="cancelled after partial completion",
            )
            job.script = MockJobScript(
                steps=(terminal,),
                result_reference=job.script.result_reference,
            )
            job.index = 0
            return httpx.Response(200, json=self._step_payload(job_id, terminal))
        job.cancelled = True
        return httpx.Response(200, json=self._cancelled_payload(job_id, job))

    @staticmethod
    def _step_payload(job_id: str, step: MockJobStep) -> dict[str, object]:
        payload: dict[str, object] = {"job_id": job_id, "state": step.state.value}
        if step.completed_scenes is not None:
            payload["completed_scenes"] = step.completed_scenes
        if step.total_scenes is not None:
            payload["total_scenes"] = step.total_scenes
        if step.message is not None:
            payload["message"] = step.message
        return payload

    @staticmethod
    def _cancelled_payload(job_id: str, job: _MockJob) -> dict[str, object]:
        step = job.step
        payload: dict[str, object] = {"job_id": job_id, "state": JobState.CANCELLED.value}
        if step.completed_scenes is not None:
            payload["completed_scenes"] = step.completed_scenes
        if step.total_scenes is not None:
            payload["total_scenes"] = step.total_scenes
        payload["message"] = "cancelled"
        return payload

    @staticmethod
    def _effective_terminal_state(job: _MockJob) -> JobState:
        if job.cancelled:
            return JobState.CANCELLED
        state = job.step.state
        return state if state.terminal else JobState.QUEUED
