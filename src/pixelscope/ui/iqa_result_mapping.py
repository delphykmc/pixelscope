"""Protect Remote IQA result-path resolution across live storage-mapping changes."""

from __future__ import annotations

from types import MethodType
from typing import Any

from PySide6.QtCore import QObject

from pixelscope.remote.iqa_settings import RemoteIqaSettings
from pixelscope.remote.iqa_submission import JobState
from pixelscope.workers.task_worker import TaskWorker

RESULT_MAPPING_REFRESH_MESSAGE = "storage mapping changed · resolving result path"


def _mapping_identity(settings: RemoteIqaSettings) -> tuple[tuple[str, str], ...]:
    return tuple((root.storage_root_id, root.client_path) for root in settings.storage_roots)


class RemoteIqaResultMappingGuard(QObject):
    """Ensure only the latest machine-local storage mapping can publish a result path."""

    def __init__(self, controller: Any, parent: QObject) -> None:
        super().__init__(parent)
        self.controller = controller
        self.workspace = controller.workspace
        self._revision = 0
        self._mapping_identity = _mapping_identity(
            controller.window.application_settings.remote_iqa
        )
        self._pending_jobs: set[str] = set()
        self._task_revisions: dict[str, int] = {}
        self._task_jobs: dict[str, str] = {}
        self._starting_resolution: tuple[str, int] | None = None

        self._original_settings_changed = controller.settings_changed
        self._original_resolve_result_path = controller._resolve_result_path
        self._original_result_path_ready = controller._result_path_ready
        self._original_result_resolve_finished = controller._result_resolve_finished
        self._original_track_worker = controller._track_worker

        def guarded_settings_changed(_controller: Any) -> None:
            self._settings_changed()

        def guarded_resolve_result_path(_controller: Any, job: Any) -> None:
            self._resolve_result_path(job)

        def guarded_result_path_ready(
            _controller: Any,
            task_id: str,
            document_id: object,
            generation: int,
            value: object,
        ) -> None:
            self._result_path_ready(
                task_id,
                document_id,
                generation,
                value,
            )

        def guarded_result_resolve_finished(_controller: Any, task_id: str) -> None:
            self._result_resolve_finished(task_id)

        def guarded_track_worker(_controller: Any, worker: TaskWorker) -> None:
            self._track_worker(worker)

        controller.settings_changed = MethodType(guarded_settings_changed, controller)
        controller._resolve_result_path = MethodType(
            guarded_resolve_result_path,
            controller,
        )
        controller._result_path_ready = MethodType(
            guarded_result_path_ready,
            controller,
        )
        controller._result_resolve_finished = MethodType(
            guarded_result_resolve_finished,
            controller,
        )
        controller._track_worker = MethodType(guarded_track_worker, controller)

    @property
    def revision(self) -> int:
        return self._revision

    @property
    def pending_jobs(self) -> frozenset[str]:
        return frozenset(self._pending_jobs)

    def _settings_changed(self) -> None:
        current_identity = _mapping_identity(
            self.controller.window.application_settings.remote_iqa
        )
        if current_identity != self._mapping_identity:
            self._mapping_identity = current_identity
            self._revision += 1
            for job in self.controller._jobs.values():
                if job.result_reference is None or job.state not in {
                    JobState.SUCCEEDED,
                    JobState.PARTIAL,
                }:
                    continue
                job.result_path = None
                job.result_resolution_error = RESULT_MAPPING_REFRESH_MESSAGE
                self.workspace.upsert_job(job)
                if job.job_id in self.controller._result_resolve_jobs:
                    self._pending_jobs.add(job.job_id)
        self._original_settings_changed()

    def _resolve_result_path(self, job: Any) -> None:
        if job.result_reference is None:
            self._original_resolve_result_path(job)
            return
        if job.job_id in self.controller._result_resolve_jobs:
            self._pending_jobs.add(job.job_id)
            return

        self._starting_resolution = (job.job_id, self._revision)
        try:
            self._original_resolve_result_path(job)
        finally:
            self._starting_resolution = None

    def _track_worker(self, worker: TaskWorker) -> None:
        if self._starting_resolution is not None:
            job_id, revision = self._starting_resolution
            if worker.document_id == job_id:
                self._task_revisions[worker.task_id] = revision
                self._task_jobs[worker.task_id] = job_id
        self._original_track_worker(worker)

    def _result_path_ready(
        self,
        task_id: str,
        document_id: object,
        generation: int,
        value: object,
    ) -> None:
        revision = self._task_revisions.get(task_id)
        if revision is not None and revision != self._revision:
            return
        self._original_result_path_ready(
            task_id,
            document_id,
            generation,
            value,
        )

    def _result_resolve_finished(self, task_id: str) -> None:
        job_id = self._task_jobs.pop(task_id, None)
        revision = self._task_revisions.pop(task_id, None)
        self._original_result_resolve_finished(task_id)

        if job_id is None:
            return
        should_reresolve = job_id in self._pending_jobs or (
            revision is not None and revision != self._revision
        )
        self._pending_jobs.discard(job_id)
        if not should_reresolve or not getattr(self.controller, "_active", False):
            return
        job = self.controller._jobs.get(job_id)
        if job is None or job.result_reference is None or job.state not in {
            JobState.SUCCEEDED,
            JobState.PARTIAL,
        }:
            return
        self.controller._resolve_result_path(job)


def install_remote_iqa_result_mapping(window: Any) -> RemoteIqaResultMappingGuard:
    """Install live remap protection on the existing Remote IQA result-path owner."""

    controller = getattr(window, "remote_iqa_controller", None)
    if controller is None:
        raise RuntimeError("Remote IQA must be installed before result mapping hardening")
    guard = RemoteIqaResultMappingGuard(controller, window)
    window.remote_iqa_result_mapping = guard
    return guard
