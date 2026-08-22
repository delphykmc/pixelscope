"""P5-C submission lifecycle guard around the existing Remote IQA controller."""

from __future__ import annotations

from types import MethodType
from typing import Any

from PySide6.QtCore import QObject, Slot

from pixelscope.workers.task_worker import TaskError, TaskWorker

AMBIGUOUS_CREATE_MESSAGE = (
    "Create outcome unknown · the server may already have accepted this job. "
    "Further submissions are blocked in this PixelScope process; check server jobs, "
    "then restart PixelScope before submitting again."
)
SUBMISSION_BUSY_MESSAGE = "A Remote IQA submission is already preparing/submitting."


class RemoteIqaSubmissionLifecycle(QObject):
    """Own one local in-flight create attempt and conservative ambiguous-create recovery."""

    def __init__(self, controller: Any, parent: QObject) -> None:
        super().__init__(parent)
        self.controller = controller
        self.workspace = controller.workspace
        self._submission_worker_id: str | None = None
        self._starting_submission = False
        self._ambiguous_create = False

        self._original_start_submission = controller._start_submission
        self._original_track_worker = controller._track_worker
        self._original_set_configuration_state = self.workspace.set_configuration_state
        self._original_set_current_pair_state = self.workspace.set_current_pair_state

        def guarded_start(_controller: Any, *args: Any, **kwargs: Any) -> None:
            self._guarded_start_submission(*args, **kwargs)

        def guarded_track(_controller: Any, worker: TaskWorker) -> None:
            self._guarded_track_worker(worker)

        def guarded_configuration(_workspace: Any, *args: Any, **kwargs: Any) -> None:
            self._original_set_configuration_state(*args, **kwargs)
            self._apply_submit_gate()

        def guarded_current_pair(_workspace: Any, *args: Any, **kwargs: Any) -> None:
            self._original_set_current_pair_state(*args, **kwargs)
            self._apply_submit_gate()

        controller._start_submission = MethodType(guarded_start, controller)
        controller._track_worker = MethodType(guarded_track, controller)
        self.workspace.set_configuration_state = MethodType(
            guarded_configuration,
            self.workspace,
        )
        self.workspace.set_current_pair_state = MethodType(
            guarded_current_pair,
            self.workspace,
        )

    @property
    def submission_in_flight(self) -> bool:
        return self._submission_worker_id is not None

    @property
    def ambiguous_create_blocked(self) -> bool:
        return self._ambiguous_create

    def _guarded_start_submission(self, *args: Any, **kwargs: Any) -> None:
        if self._ambiguous_create:
            self.workspace.show_submission_error(AMBIGUOUS_CREATE_MESSAGE)
            self._apply_submit_gate()
            return
        if self._submission_worker_id is not None or self._starting_submission:
            self.workspace.show_submission_error(SUBMISSION_BUSY_MESSAGE)
            self._apply_submit_gate()
            return

        self._starting_submission = True
        self._apply_submit_gate()
        try:
            self._original_start_submission(*args, **kwargs)
        finally:
            self._starting_submission = False

        if self._submission_worker_id is None:
            self._refresh_submit_state()

    def _guarded_track_worker(self, worker: TaskWorker) -> None:
        if self._starting_submission and self._submission_worker_id is None:
            self._submission_worker_id = worker.task_id
            worker.signals.failed.connect(self._submission_failed)
            worker.signals.finished.connect(self._submission_finished)
            self._apply_submit_gate()
        self._original_track_worker(worker)

    @Slot(str, object, int, object)
    def _submission_failed(
        self,
        _task_id: str,
        _document_id: object,
        _generation: int,
        value: object,
    ) -> None:
        if isinstance(value, TaskError) and value.exception_type == "IqaCreateOutcomeUnknown":
            self._ambiguous_create = True
            self.workspace.jobs_status.setText(AMBIGUOUS_CREATE_MESSAGE)
            self._apply_submit_gate()

    @Slot(str)
    def _submission_finished(self, task_id: str) -> None:
        if task_id != self._submission_worker_id:
            return
        self._submission_worker_id = None
        self._refresh_submit_state()

    def _refresh_submit_state(self) -> None:
        if not getattr(self.controller, "_active", False):
            self._apply_submit_gate()
            return
        if self._ambiguous_create:
            self.workspace.jobs_status.setText(AMBIGUOUS_CREATE_MESSAGE)
            self._apply_submit_gate()
            return
        self.controller._last_pair_identity = None
        self.controller.refresh_setup_state()
        self._apply_submit_gate()

    def _apply_submit_gate(self) -> None:
        blocked = (
            self._starting_submission
            or self._submission_worker_id is not None
            or self._ambiguous_create
            or not getattr(self.controller, "_active", False)
        )
        if blocked:
            self.workspace.current_submit.setEnabled(False)
            self.workspace.folder_submit.setEnabled(False)


def install_remote_iqa_submission_lifecycle(window: Any) -> RemoteIqaSubmissionLifecycle:
    """Install lifecycle hardening without creating a second job/result authority."""

    controller = getattr(window, "remote_iqa_controller", None)
    if controller is None:
        raise RuntimeError("Remote IQA must be installed before submission lifecycle hardening")
    guard = RemoteIqaSubmissionLifecycle(controller, window)
    window.remote_iqa_submission_lifecycle = guard
    return guard
