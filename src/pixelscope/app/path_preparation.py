"""Bounded filesystem preflight with GUI continuations and deterministic close."""
from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent, QObject, QThreadPool, QTimer, Slot
from PySide6.QtWidgets import QPushButton

from pixelscope.ui.lifecycle_hooks import OwnerCallback
from pixelscope.workers.task_worker import TaskWorker


@dataclass(frozen=True)
class _Request:
    function: Callable[..., Any]
    args: tuple[Any, ...]
    success: OwnerCallback
    failure: OwnerCallback


class PathPreparationController(QObject):
    """One running task and at most one superseding pending request per window.

    Functions/arguments dispatched to workers must contain no UI owner. Callbacks
    stay on this GUI-affine QObject and use weak method edges. A cancelled OS call
    may still be running: keep the owned pool/window alive until physical drain.
    """

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self._window_ref = weakref.ref(window)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._worker: TaskWorker | None = None
        self._request: _Request | None = None
        self._pending: _Request | None = None
        self._authority: str | None = None
        self._closing = False
        self._close_safe = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)  # type: ignore[attr-defined]
        self.cancel_button = QPushButton("Cancel path check", window)
        self.cancel_button.clicked.connect(self.cancel)  # type: ignore[attr-defined]
        self.cancel_button.hide()
        window.statusBar().addPermanentWidget(self.cancel_button)
        window.installEventFilter(self)

    @property
    def is_idle(self) -> bool:
        return self._worker is None and self._pending is None and self.pool.activeThreadCount() == 0

    def submit(
        self,
        function: Callable[..., Any],
        args: tuple[Any, ...],
        success: Callable[..., Any],
        failure: Callable[..., Any],
    ) -> None:
        window = self._window_ref()
        if self._closing or window is None or getattr(window, "_closing", False):
            return
        self.cancel()
        self._pending = _Request(function, args, OwnerCallback(success), OwnerCallback(failure))
        self.cancel_button.show()
        self._advance()

    def cancel(self) -> None:
        # A prepared Session can be waiting for a previous registration worker
        # even after this preparation task has completed.
        window = self._window_ref()
        registration = getattr(window, "large_folder_registration_controller", None)
        invalidate = getattr(registration, "invalidate_pending_session_restore", None)
        if callable(invalidate):
            invalidate()
        self._authority = None
        self._pending = None
        self._request = None
        if self._worker is not None:
            self._worker.cancel()
        self.cancel_button.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() is not QEvent.Type.Close:
            return super().eventFilter(watched, event)
        window = self._window_ref()
        confirm = getattr(window, "_confirm_close_request", None)
        if callable(confirm) and not confirm():
            event.ignore()
            return True
        if self._close_safe:
            return super().eventFilter(watched, event)
        self._closing = True
        self.cancel()
        # Once accepted, revoke the registration owner too; its close filter
        # will await its own physical pool drain before final destruction.
        registration = getattr(window, "large_folder_registration_controller", None)
        shutdown = getattr(registration, "shutdown", None)
        if callable(shutdown):
            shutdown()
        if self.is_idle:
            self._close_safe = True
            return super().eventFilter(watched, event)
        event.ignore()
        self._timer.start(0)
        return True

    def _advance(self) -> None:
        if self._worker is not None:
            # finished will wake us; do not busy-poll a stalled OS call.
            return
        if self.pool.activeThreadCount():
            if self._closing or self._pending is not None:
                self._timer.start(0)
            return
        if self._closing:
            window = self._window_ref()
            if window is not None and not self._close_safe:
                self._close_safe = True
                window.close()
            return
        request = self._pending
        if request is None:
            window = self._window_ref()
            recent = getattr(window, "recent_entries_controller", None)
            if getattr(recent, "_pending_session_restore", None) is None:
                self.cancel_button.hide()
            return
        self._pending = None
        self._request = request
        worker = TaskWorker(request.function, *request.args)
        self._worker = worker
        self._authority = worker.task_id
        worker.signals.succeeded.connect(self._succeeded)
        worker.signals.failed.connect(self._failed)
        worker.signals.finished.connect(self._finished)
        self.pool.start(worker)

    @Slot(str, object, int, object)
    def _succeeded(self, task: str, _document: object, _generation: int, result: object) -> None:
        request = self._request
        if self._closing or task != self._authority or request is None:
            return
        self._authority = None
        self.cancel_button.hide()
        request.success(result)

    @Slot(str, object, int, object)
    def _failed(self, task: str, _document: object, _generation: int, error: object) -> None:
        request = self._request
        if self._closing or task != self._authority or request is None:
            return
        self._authority = None
        self.cancel_button.hide()
        request.failure(error)

    @Slot(str)
    def _finished(self, task: str) -> None:
        if self._worker is None or self._worker.task_id != task:
            return
        self._worker = None
        self._request = None
        self._timer.start(0)


def path_preparation(window: Any) -> PathPreparationController:
    controller = getattr(window, "path_preparation_controller", None)
    if not isinstance(controller, PathPreparationController):
        controller = PathPreparationController(window)
        window.path_preparation_controller = controller
    return controller
