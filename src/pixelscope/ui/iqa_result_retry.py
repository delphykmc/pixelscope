"""Bounded terminal result-reference retry owner for P5-C Remote IQA."""

from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QObject, QTimer, Slot

from pixelscope.remote.iqa_submission import JobState

RESULT_REFERENCE_RETRY_DELAYS_SECONDS = (1.0, 2.0, 4.0, 8.0)
RESULT_REFERENCE_RETRY_TICK_MS = 250


class RemoteIqaResultRetryController(QObject):
    """Retry idempotent GET /result after terminal status without retrying create POST."""

    def __init__(self, remote_controller: Any, parent: QObject) -> None:
        super().__init__(parent)
        self.remote_controller = remote_controller
        self._retry_count: dict[str, int] = {}
        self._next_due: dict[str, float] = {}
        self._was_fetching: set[str] = set()
        self._exhausted: set[str] = set()
        self._timer = QTimer(self)
        self._timer.setInterval(RESULT_REFERENCE_RETRY_TICK_MS)
        self._timer.timeout.connect(self._tick)  # type: ignore[attr-defined]
        self._timer.start()

    @Slot()
    def _tick(self) -> None:
        controller = self.remote_controller
        if not getattr(controller, "_active", False):
            self._timer.stop()
            return
        now = time.monotonic()
        jobs = tuple(getattr(controller, "_jobs", {}).values())
        live_ids = {job.job_id for job in jobs}
        self._discard_stale(live_ids)

        for job in jobs:
            if job.state not in {JobState.SUCCEEDED, JobState.PARTIAL}:
                self._clear_job(job.job_id)
                continue
            if job.result_reference is not None:
                self._clear_job(job.job_id)
                continue

            fetching = job.job_id in getattr(controller, "_result_fetch_jobs", set())
            if fetching:
                self._was_fetching.add(job.job_id)
                continue

            if job.job_id in self._was_fetching:
                self._was_fetching.discard(job.job_id)
                retry_index = self._retry_count.get(job.job_id, 0)
                if retry_index < len(RESULT_REFERENCE_RETRY_DELAYS_SECONDS):
                    self._next_due[job.job_id] = (
                        now + RESULT_REFERENCE_RETRY_DELAYS_SECONDS[retry_index]
                    )
                continue

            retry_index = self._retry_count.get(job.job_id, 0)
            if retry_index >= len(RESULT_REFERENCE_RETRY_DELAYS_SECONDS):
                self._mark_exhausted(job)
                continue

            due = self._next_due.setdefault(
                job.job_id,
                now + RESULT_REFERENCE_RETRY_DELAYS_SECONDS[retry_index],
            )
            if now < due:
                continue

            self._retry_count[job.job_id] = retry_index + 1
            self._next_due.pop(job.job_id, None)
            controller._fetch_result_reference(job)
            if job.job_id in getattr(controller, "_result_fetch_jobs", set()):
                self._was_fetching.add(job.job_id)

    def _mark_exhausted(self, job: Any) -> None:
        if job.job_id in self._exhausted:
            return
        self._exhausted.add(job.job_id)
        message = job.message or "result reference unavailable"
        if "retry limit reached" not in message:
            message = f"{message} · retry limit reached"
        self.remote_controller.workspace.show_job_operation_error(job.job_id, message)

    def _discard_stale(self, live_ids: set[str]) -> None:
        for job_id in set(self._retry_count) - live_ids:
            self._clear_job(job_id)
        self._was_fetching.intersection_update(live_ids)
        self._exhausted.intersection_update(live_ids)

    def _clear_job(self, job_id: str) -> None:
        self._retry_count.pop(job_id, None)
        self._next_due.pop(job_id, None)
        self._was_fetching.discard(job_id)
        self._exhausted.discard(job_id)


def install_remote_iqa_result_retry(window: Any) -> RemoteIqaResultRetryController:
    """Attach bounded GET /result recovery to the existing Remote IQA controller."""

    controller = getattr(window, "remote_iqa_controller", None)
    if controller is None:
        raise RuntimeError("Remote IQA must be installed before result-reference retry")
    retry = RemoteIqaResultRetryController(controller, window)
    window.remote_iqa_result_retry_controller = retry
    return retry
