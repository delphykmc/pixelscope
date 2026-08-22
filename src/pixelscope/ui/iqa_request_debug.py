"""Debug-only manual inspection of the exact Remote IQA submission payload."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, QThreadPool, Slot
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.remote.iqa_settings import RemoteIqaSettings
from pixelscope.remote.iqa_submission import (
    FolderPairEntry,
    PreflightError,
    build_request,
    pair_current_paths,
    pair_folders,
)
from pixelscope.workers.task_worker import TaskError, TaskWorker

REQUEST_DEBUG_ENV = "PIXELSCOPE_REMOTE_IQA_DEBUG"
REQUEST_DEBUG_WORKER_LIMIT = 1
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def request_debug_enabled(environment: Mapping[str, str] | None = None) -> bool:
    """Return whether the explicit Remote IQA debug UI opt-in is active."""

    source = os.environ if environment is None else environment
    return source.get(REQUEST_DEBUG_ENV, "").strip().casefold() in _TRUE_VALUES


def format_request_json(
    entries: tuple[FolderPairEntry, ...],
    settings: RemoteIqaSettings,
    submission_kind: str,
) -> str:
    """Serialize the same request object used by production POST without sending it."""

    request = build_request(entries, settings, submission_kind=submission_kind)
    return json.dumps(request.to_json(), ensure_ascii=False, indent=2) + "\n"


class RemoteIqaRequestInspector(QGroupBox):
    """Visible only under an explicit debug opt-in; never performs an HTTP request."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Request Inspector (Debug)", parent)
        self.setObjectName("remoteIqaRequestInspector")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        explanation = QLabel(
            "Builds the production request through preflight, hashing, and staging, "
            "then stops before HTTP POST.",
            self,
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        actions = QHBoxLayout()
        self.current_button = QPushButton("Prepare Current JSON", self)
        self.current_button.setObjectName("remoteIqaDebugPrepareCurrent")
        self.folder_button = QPushButton("Prepare Folder JSON", self)
        self.folder_button.setObjectName("remoteIqaDebugPrepareFolder")
        self.copy_button = QPushButton("Copy JSON", self)
        self.copy_button.setObjectName("remoteIqaDebugCopyRequest")
        self.copy_button.setEnabled(False)
        actions.addWidget(self.current_button)
        actions.addWidget(self.folder_button)
        actions.addWidget(self.copy_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.status = QLabel("DEBUG · no HTTP request will be sent.", self)
        self.status.setObjectName("remoteIqaDebugRequestStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.request_text = QPlainTextEdit(self)
        self.request_text.setObjectName("remoteIqaDebugRequestJson")
        self.request_text.setReadOnly(True)
        self.request_text.setPlaceholderText("Prepared request JSON appears here.")
        self.request_text.setMinimumHeight(180)
        layout.addWidget(self.request_text)

        self.copy_button.clicked.connect(self.copy_json)  # type: ignore[attr-defined]

    def show_loading(self, label: str) -> None:
        self.status.setText(f"Preparing {label} · hashing/staging may write to the staging root...")
        self.current_button.setEnabled(False)
        self.folder_button.setEnabled(False)
        self.copy_button.setEnabled(False)

    def show_request(self, payload: str) -> None:
        self.request_text.setPlainText(payload)
        self.status.setText(
            "Prepared with the production request builder · HTTP POST was not attempted."
        )
        self.current_button.setEnabled(True)
        self.folder_button.setEnabled(True)
        self.copy_button.setEnabled(True)

    def show_error(self, message: str) -> None:
        self.status.setText(f"Blocked · {message}")
        self.current_button.setEnabled(True)
        self.folder_button.setEnabled(True)
        self.copy_button.setEnabled(bool(self.request_text.toPlainText()))

    @Slot()
    def copy_json(self) -> None:
        payload = self.request_text.toPlainText()
        if payload:
            QApplication.clipboard().setText(payload)


class RemoteIqaRequestInspectorController(QObject):
    """Bounded debug worker owner that has no HTTP client or remote-job lifecycle."""

    def __init__(self, window: Any, panel: RemoteIqaRequestInspector) -> None:
        super().__init__(window)
        self.window = window
        self.panel = panel
        self.workspace = window.remote_iqa_workspace
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(REQUEST_DEBUG_WORKER_LIMIT)
        self._workers: dict[str, TaskWorker] = {}
        self._generation = 0
        self._active = True

        panel.current_button.clicked.connect(self.prepare_current)  # type: ignore[attr-defined]
        panel.folder_button.clicked.connect(self.prepare_folder)  # type: ignore[attr-defined]

    @Slot()
    def prepare_current(self) -> None:
        if not self._active:
            return
        documents = list(self.window.current_comparison_documents())
        if len(documents) != 2:
            self.panel.show_error("Current Comparison Page must contain exactly two images")
            return
        path_a = getattr(documents[0], "source_path", None)
        path_b = getattr(documents[1], "source_path", None)
        if not isinstance(path_a, Path) or not isinstance(path_b, Path):
            self.panel.show_error("Current Pair is not backed by two native source paths")
            return
        self._start(
            "Current Pair",
            "current_pair",
            lambda: pair_current_paths(path_a, path_b),
        )

    @Slot()
    def prepare_folder(self) -> None:
        if not self._active:
            return
        identity = self.workspace.preview_identity
        preview = self.workspace.preview_entries
        if identity is None or not preview:
            self.panel.show_error("validate the current Folder Pair before preparing JSON")
            return
        folder_a, folder_b = identity

        def entries() -> tuple[FolderPairEntry, ...]:
            current = pair_folders(folder_a, folder_b)
            if current != preview:
                raise PreflightError(
                    "Folder Pair changed after preview; validate again before preparing JSON"
                )
            return current

        self._start("Folder Pair", "folder_pair", entries)

    def _start(
        self,
        label: str,
        submission_kind: str,
        entries_factory: Callable[[], tuple[FolderPairEntry, ...]],
    ) -> None:
        settings = self.window.application_settings.remote_iqa
        if not settings.submission_configured:
            self.panel.show_error("Remote IQA server URL and storage roots must be configured")
            return
        self.panel.show_loading(label)

        def prepare() -> str:
            return format_request_json(entries_factory(), settings, submission_kind)

        worker = TaskWorker(prepare, generation=self._generation)
        worker.signals.succeeded.connect(self._request_ready)
        worker.signals.failed.connect(self._request_failed)
        worker.signals.finished.connect(self._worker_finished)
        self._workers[worker.task_id] = worker
        self._pool.start(worker)

    @Slot(str, object, int, object)
    def _request_ready(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if self._accept_generation(generation) and isinstance(value, str):
            self.panel.show_request(value)

    @Slot(str, object, int, object)
    def _request_failed(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if self._accept_generation(generation):
            self.panel.show_error(_task_error_message(value))

    @Slot(str)
    def _worker_finished(self, task_id: str) -> None:
        self._workers.pop(task_id, None)

    def shutdown(self) -> None:
        if not self._active:
            return
        self._active = False
        self._generation += 1
        for worker in tuple(self._workers.values()):
            worker.cancel()
        self._workers.clear()
        self._pool.clear()

    def _accept_generation(self, generation: int) -> bool:
        return self._active and generation == self._generation


class _RequestInspectorCloseFilter(QObject):
    def __init__(
        self,
        controller: RemoteIqaRequestInspectorController,
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self.controller = controller

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() is QEvent.Type.Close:
            self.controller.shutdown()
        return super().eventFilter(watched, event)


def install_remote_iqa_request_debug(
    window: Any,
) -> RemoteIqaRequestInspectorController | None:
    """Install the opt-in Request Inspector after the production IQA shell exists."""

    if not request_debug_enabled():
        return None
    workspace = getattr(window, "remote_iqa_workspace", None)
    if workspace is None:
        raise RuntimeError("Remote IQA must be installed before its request debug harness")
    layout = workspace.setup_page.layout()
    if not isinstance(layout, QVBoxLayout):
        raise RuntimeError("Remote IQA Setup page layout is unavailable")

    panel = RemoteIqaRequestInspector(workspace.setup_page)
    layout.insertWidget(max(0, layout.count() - 1), panel)
    controller = RemoteIqaRequestInspectorController(window, panel)
    close_filter = _RequestInspectorCloseFilter(controller, window)
    window.installEventFilter(close_filter)
    window.remote_iqa_request_inspector = panel
    window.remote_iqa_request_inspector_controller = controller
    window._remote_iqa_request_inspector_close_filter = close_filter
    return controller


def _task_error_message(value: object) -> str:
    if isinstance(value, TaskError):
        clean = " ".join(value.message.split())
        return (clean or value.exception_type)[:512]
    clean = " ".join(str(value).split())
    return (clean or "unexpected Remote IQA request-inspection error")[:512]
