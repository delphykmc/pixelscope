from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import QObject

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.remote.iqa_submission import IqaResultReference, JobState
from pixelscope.ui.iqa_result_mapping import RemoteIqaResultMappingGuard
from pixelscope.ui.iqa_submission import RemoteJobRecord
from pixelscope.workers.task_worker import TaskWorker


class _FakeWorkspace:
    def __init__(self) -> None:
        self.updated_jobs: list[str] = []

    def upsert_job(self, job: RemoteJobRecord) -> None:
        self.updated_jobs.append(job.job_id)


class _FakeController:
    def __init__(self, settings: RemoteIqaSettings, job: RemoteJobRecord) -> None:
        self.window = SimpleNamespace(application_settings=SimpleNamespace(remote_iqa=settings))
        self.workspace = _FakeWorkspace()
        self._jobs = {job.job_id: job}
        self._workers: dict[str, TaskWorker] = {}
        self._result_resolve_jobs: set[str] = set()
        self._active = True

    def settings_changed(self) -> None:
        for job in self._jobs.values():
            if job.result_reference is not None and job.state in {
                JobState.SUCCEEDED,
                JobState.PARTIAL,
            }:
                self._resolve_result_path(job)

    def _resolve_result_path(self, job: RemoteJobRecord) -> None:
        if job.result_reference is None or job.job_id in self._result_resolve_jobs:
            return
        self._result_resolve_jobs.add(job.job_id)
        worker = TaskWorker(
            lambda: None,
            document_id=job.job_id,
            generation=0,
        )
        self._track_worker(worker)

    def _track_worker(self, worker: TaskWorker) -> None:
        self._workers[worker.task_id] = worker

    def _result_path_ready(
        self,
        _task_id: str,
        document_id: object,
        _generation: int,
        value: object,
    ) -> None:
        if not isinstance(document_id, str):
            return
        job = self._jobs.get(document_id)
        if job is None:
            return
        job.result_path = getattr(value, "path", None)
        job.result_resolution_error = getattr(value, "error", None)
        self.workspace.upsert_job(job)

    def _result_resolve_finished(self, task_id: str) -> None:
        worker = self._workers.get(task_id)
        if worker is not None and isinstance(worker.document_id, str):
            self._result_resolve_jobs.discard(worker.document_id)


def _settings(server: str, client_path: str) -> RemoteIqaSettings:
    return RemoteIqaSettings(
        server_base_url=server,
        storage_roots=(RemoteIqaStorageRoot("shared", client_path),),
        staging_root_id="shared",
    )


def _terminal_job(path: Path) -> RemoteJobRecord:
    return RemoteJobRecord(
        "job_000001",
        "current_pair",
        "https://iqa.example.test",
        JobState.SUCCEEDED,
        1,
        1,
        "result published",
        result_reference=IqaResultReference(
            "job_000001",
            "shared",
            "results/job_000001",
            2,
            "complete",
        ),
        result_path=path,
    )


def test_mapping_change_ignores_stale_result_and_reresolves_latest() -> None:
    old_path = Path("C:/shared-old/results/job_000001")
    new_path = Path("D:/shared-new/results/job_000001")
    job = _terminal_job(old_path)
    controller = _FakeController(
        _settings("https://iqa.example.test", "C:/shared-old"),
        job,
    )
    parent = QObject()
    guard = RemoteIqaResultMappingGuard(controller, parent)

    controller._resolve_result_path(job)
    first_task_id = next(iter(controller._workers))
    assert controller._result_resolve_jobs == {job.job_id}

    controller.window.application_settings.remote_iqa = _settings(
        "https://iqa.example.test",
        "D:/shared-new",
    )
    controller.settings_changed()

    assert guard.revision == 1
    assert guard.pending_jobs == {job.job_id}
    assert job.result_path is None
    assert job.result_resolution_error == "storage mapping changed · resolving result path"

    controller._result_path_ready(
        first_task_id,
        job.job_id,
        0,
        SimpleNamespace(path=old_path, error=None),
    )
    assert job.result_path is None

    controller._result_resolve_finished(first_task_id)
    task_ids = set(controller._workers)
    task_ids.remove(first_task_id)
    assert len(task_ids) == 1
    second_task_id = task_ids.pop()
    assert guard.pending_jobs == frozenset()

    controller._result_path_ready(
        second_task_id,
        job.job_id,
        0,
        SimpleNamespace(path=new_path, error=None),
    )
    assert job.result_path == new_path
    assert job.result_resolution_error is None


def test_server_url_only_change_does_not_invalidate_result_mapping() -> None:
    result_path = Path("C:/shared/results/job_000001")
    job = _terminal_job(result_path)
    controller = _FakeController(
        _settings("https://iqa-old.example.test", "C:/shared"),
        job,
    )
    parent = QObject()
    guard = RemoteIqaResultMappingGuard(controller, parent)

    controller.window.application_settings.remote_iqa = _settings(
        "https://iqa-new.example.test",
        "C:/shared",
    )
    controller.settings_changed()

    assert guard.revision == 0
    assert job.result_path == result_path


def test_production_composition_installs_result_mapping_guard(qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    _compose_main_window_presentation(window)

    assert isinstance(window.remote_iqa_result_mapping, RemoteIqaResultMappingGuard)
    assert window.remote_iqa_result_mapping.controller is window.remote_iqa_controller
    window.close()
