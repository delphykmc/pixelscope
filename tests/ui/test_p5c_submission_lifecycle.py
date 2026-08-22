from __future__ import annotations

import time
from collections.abc import Callable
from threading import Event
from typing import Any

from PySide6.QtCore import QObject, QThreadPool
from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.cancellation import cancellation_checkpoint
from pixelscope.remote.iqa_client import IqaClientErrorKind, IqaCreateOutcomeUnknown
from pixelscope.ui.iqa_submission_lifecycle import (
    AMBIGUOUS_CREATE_MESSAGE,
    SUBMISSION_BUSY_MESSAGE,
    install_remote_iqa_submission_lifecycle,
)
from pixelscope.workers.task_worker import TaskWorker


class _Workspace(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.current_submit = QPushButton(self)
        self.folder_submit = QPushButton(self)
        self.jobs_status = QLabel(self)
        self.current_submit.setEnabled(True)
        self.folder_submit.setEnabled(True)

    def show_submission_error(self, message: str) -> None:
        self.jobs_status.setText(message)

    def set_configuration_state(self, _settings: object) -> None:
        self.folder_submit.setEnabled(True)

    def set_current_pair_state(
        self,
        _summary: str,
        eligible: bool,
        _reason: str | None,
    ) -> None:
        self.current_submit.setEnabled(eligible)


class _Controller(QObject):
    def __init__(self, workspace: _Workspace, work: Callable[[], object]) -> None:
        super().__init__(workspace)
        self.workspace = workspace
        self.work = work
        self._active = True
        self._workers: dict[str, TaskWorker] = {}
        self._last_pair_identity: tuple[object, ...] | None = None
        self.started_count = 0
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

    def _start_submission(self, *_args: Any, **_kwargs: Any) -> None:
        worker = TaskWorker(self.work)
        self._track_worker(worker)

    def _track_worker(self, worker: TaskWorker) -> None:
        self.started_count += 1
        self._workers[worker.task_id] = worker
        worker.signals.finished.connect(self._worker_finished)
        self._pool.start(worker)

    def _worker_finished(self, task_id: str) -> None:
        self._workers.pop(task_id, None)

    def refresh_setup_state(self) -> None:
        self.workspace.set_configuration_state(object())
        self.workspace.set_current_pair_state("ready", True, None)

    def shutdown(self) -> None:
        self._active = False
        for worker in tuple(self._workers.values()):
            worker.cancel()
        self._pool.clear()


def _install(
    qtbot: Any,
    work: Callable[[], object],
) -> tuple[QWidget, _Controller, Any]:
    window = QWidget()
    qtbot.addWidget(window)
    workspace = _Workspace()
    workspace.setParent(window)
    controller = _Controller(workspace, work)
    window.remote_iqa_controller = controller  # type: ignore[attr-defined]
    guard = install_remote_iqa_submission_lifecycle(window)
    return window, controller, guard


def test_single_in_flight_submission_blocks_duplicate_until_finished(qtbot: Any) -> None:
    entered = Event()
    release = Event()

    def work() -> None:
        entered.set()
        while not release.is_set():
            cancellation_checkpoint()
            time.sleep(0.005)

    _window, controller, guard = _install(qtbot, work)

    controller._start_submission("current_pair", object(), object())
    qtbot.waitUntil(entered.is_set, timeout=1000)
    assert guard.submission_in_flight
    assert not controller.workspace.current_submit.isEnabled()
    assert not controller.workspace.folder_submit.isEnabled()

    controller._start_submission("current_pair", object(), object())
    assert controller.started_count == 1
    assert controller.workspace.jobs_status.text() == SUBMISSION_BUSY_MESSAGE

    release.set()
    qtbot.waitUntil(lambda: not guard.submission_in_flight, timeout=1000)
    assert controller.workspace.current_submit.isEnabled()
    assert controller.workspace.folder_submit.isEnabled()


def test_ambiguous_create_blocks_further_submission_for_process(qtbot: Any) -> None:
    def work() -> None:
        raise IqaCreateOutcomeUnknown(
            IqaClientErrorKind.TIMEOUT,
            "create outcome unknown",
        )

    _window, controller, guard = _install(qtbot, work)

    controller._start_submission("current_pair", object(), object())
    qtbot.waitUntil(lambda: guard.ambiguous_create_blocked, timeout=1000)
    qtbot.waitUntil(lambda: not guard.submission_in_flight, timeout=1000)
    assert controller.workspace.jobs_status.text() == AMBIGUOUS_CREATE_MESSAGE
    assert not controller.workspace.current_submit.isEnabled()
    assert not controller.workspace.folder_submit.isEnabled()

    controller._start_submission("current_pair", object(), object())
    assert controller.started_count == 1
    assert controller.workspace.jobs_status.text() == AMBIGUOUS_CREATE_MESSAGE


def test_shutdown_stops_running_cooperative_submission(qtbot: Any) -> None:
    entered = Event()

    def work() -> None:
        entered.set()
        while True:
            cancellation_checkpoint()
            time.sleep(0.005)

    _window, controller, guard = _install(qtbot, work)
    controller._start_submission("folder_pair", object(), object())
    qtbot.waitUntil(entered.is_set, timeout=1000)

    controller.shutdown()

    qtbot.waitUntil(lambda: not guard.submission_in_flight, timeout=1000)
    qtbot.waitUntil(lambda: not controller._workers, timeout=1000)
    assert not controller.workspace.current_submit.isEnabled()
    assert not controller.workspace.folder_submit.isEnabled()


def test_production_composition_installs_submission_lifecycle_guard(qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    _compose_main_window_presentation(window)

    assert window.remote_iqa_submission_lifecycle.controller is window.remote_iqa_controller
    window.close()
