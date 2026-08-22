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
    """Debug detail panel; visible only after an explicit inspect action."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("DEBUG · Request JSON", parent)
        self.setObjectName("remoteIqaRequestInspector")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        status_row = QHBoxLayout()
        self.status = QLabel("No HTTP request will be sent.", self)
        self.status.setObjectName("remoteIqaDebugRequestStatus")
        self.status.setWordWrap(True)
        self.copy_button = QPushButton("Copy JSON", self)
        self.copy_button.setObjectName("remoteIqaDebugCopyRequest")
        self.copy_button.setEnabled(False)
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.copy_button)
        layout.addLayout(status_row)

        self.request_text = QPlainTextEdit(self)
        self.request_text.setObjectName("remoteIqaDebugRequestJson")
        self.request_text.setReadOnly(True)
        self.request_text.setPlaceholderText("Prepared request JSON appears here.")
        self.request_text.setMinimumHeight(180)
        layout.addWidget(self.request_text)

        self.copy_button.clicked.connect(self.copy_json)  # type: ignore[attr-defined]

    def show_loading(self, label: str) -> None:
        self.show()
        self.request_text.clear()
        self.status.setText(f"Preparing {label} · hashing/staging only · no HTTP POST")
        self.copy_button.setEnabled(False)

    def show_request(self, payload: str) -> None:
        self.show()
        self.request_text.setPlainText(payload)
        self.status.setText("Production request prepared · HTTP POST was not attempted")
        self.copy_button.setEnabled(True)

    def show_error(self, message: str) -> None:
        self.show()
        self.status.setText(f"Blocked · {message}")
        self.copy_button.setEnabled(bool(self.request_text.toPlainText()))

    @Slot()
    def copy_json(self) -> None:
        payload = self.request_text.toPlainText()
        if payload:
            QApplication.clipboard().setText(payload)


class RemoteIqaRequestInspectorController(QObject):
    """Bounded debug worker owner that has no HTTP client or remote-job lifecycle."""

    def __init__(
        self,
        window: Any,
        panel: RemoteIqaRequestInspector,
        current_button: QPushButton,
        folder_button: QPushButton,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.panel = panel
        self.current_button = current_button
        self.folder_button = folder_button
        self.workspace = window.remote_iqa_workspace
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(REQUEST_DEBUG_WORKER_LIMIT)
        self._workers: dict[str, TaskWorker] = {}
        self._generation = 0
        self._active = True

        current_button.clicked.connect(self.prepare_current)  # type: ignore[attr-defined]
        folder_button.clicked.connect(self.prepare_folder)  # type: ignore[attr-defined]

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
            self.panel.show_error("validate the current Folder Pair before inspecting its request")
            return
        folder_a, folder_b = identity

        def entries() -> tuple[FolderPairEntry, ...]:
            current = pair_folders(folder_a, folder_b)
            if current != preview:
                raise PreflightError(
                    "Folder Pair changed after preview; validate again before "
                    "inspecting its request"
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
        self._set_actions_enabled(False)

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
            self._set_actions_enabled(True)

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
            self._set_actions_enabled(True)

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

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.current_button.setEnabled(enabled)
        self.folder_button.setEnabled(enabled)


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
    """Install secondary inspect actions after the production Setup presentation exists."""

    if not request_debug_enabled():
        return None
    workspace = getattr(window, "remote_iqa_workspace", None)
    if workspace is None:
        raise RuntimeError("Remote IQA must be installed before its request debug harness")
    setup_layout = getattr(workspace, "remote_iqa_setup_layout", None)
    current_actions = getattr(workspace, "remote_iqa_current_actions", None)
    folder_actions = getattr(workspace, "remote_iqa_folder_actions", None)
    if not isinstance(setup_layout, QVBoxLayout):
        raise RuntimeError("Remote IQA Setup presentation must be installed before debug")
    if not isinstance(current_actions, QHBoxLayout) or not isinstance(
        folder_actions,
        QHBoxLayout,
    ):
        raise RuntimeError("Remote IQA action rows are unavailable for debug inspection")

    current_button = QPushButton("Inspect JSON · DEBUG", workspace.setup_page)
    current_button.setObjectName("remoteIqaDebugInspectCurrent")
    current_button.setToolTip("Build the exact Current Pair request JSON but do not POST it.")
    folder_button = QPushButton("Inspect JSON · DEBUG", workspace.setup_page)
    folder_button.setObjectName("remoteIqaDebugInspectFolder")
    folder_button.setToolTip("Build the validated Folder Pair request JSON but do not POST it.")
    current_actions.addWidget(current_button)
    folder_actions.addWidget(folder_button)

    panel = RemoteIqaRequestInspector(workspace.setup_page)
    panel.hide()
    setup_layout.addWidget(panel)
    controller = RemoteIqaRequestInspectorController(
        window,
        panel,
        current_button,
        folder_button,
    )
    close_filter = _RequestInspectorCloseFilter(controller, window)
    window.installEventFilter(close_filter)
    window.remote_iqa_request_inspector = panel
    window.remote_iqa_request_inspect_current = current_button
    window.remote_iqa_request_inspect_folder = folder_button
    window.remote_iqa_request_inspector_controller = controller
    window._remote_iqa_request_inspector_close_filter = close_filter
    return controller


def _task_error_message(value: object) -> str:
    if isinstance(value, TaskError):
        clean = " ".join(value.message.split())
        return (clean or value.exception_type)[:512]
    clean = " ".join(str(value).split())
    return (clean or "unexpected Remote IQA request-inspection error")[:512]
