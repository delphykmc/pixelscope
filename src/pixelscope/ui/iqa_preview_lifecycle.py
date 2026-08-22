"""Own Folder Pair preview workers so stale validation cannot strand the UI."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Slot

from pixelscope.remote.iqa_submission import pair_folders
from pixelscope.ui.iqa_submission import _FolderPreviewPayload
from pixelscope.workers.task_worker import TaskWorker


class RemoteIqaPreviewLifecycle(QObject):
    """Keep exactly the latest Folder Pair preview authoritative for Setup UI state."""

    def __init__(self, controller: Any, parent: QObject) -> None:
        super().__init__(parent)
        self.controller = controller
        self.workspace = controller.workspace
        self._revision = 0
        self._active_revision: int | None = None
        self._workers: dict[str, tuple[int, str, str]] = {}

        self.workspace.preview_requested.disconnect(controller.preview_folders)
        self.workspace.preview_requested.connect(self.preview_folders)

    @property
    def active_revision(self) -> int | None:
        return self._active_revision

    @Slot(str, str)
    def preview_folders(self, folder_a: str, folder_b: str) -> None:
        if not getattr(self.controller, "_active", False):
            return
        self._revision += 1
        revision = self._revision
        self._active_revision = revision
        self.workspace.show_preview_loading()
        worker = TaskWorker(
            lambda: _FolderPreviewPayload(
                folder_a,
                folder_b,
                pair_folders(folder_a, folder_b),
            ),
            document_id=revision,
            generation=self.controller._generation,
        )
        self._workers[worker.task_id] = (revision, folder_a, folder_b)
        worker.signals.succeeded.connect(self._preview_ready)
        worker.signals.failed.connect(self._preview_failed)
        worker.signals.finished.connect(self._preview_finished)
        self.controller._track_worker(worker)

    @Slot(str, object, int, object)
    def _preview_ready(
        self,
        task_id: str,
        document_id: object,
        generation: int,
        value: object,
    ) -> None:
        ownership = self._workers.get(task_id)
        if ownership is None:
            return
        revision, folder_a, folder_b = ownership
        if revision != self._active_revision or document_id != revision:
            return
        current_identity = (
            self.workspace.folder_a.text().strip(),
            self.workspace.folder_b.text().strip(),
        )
        if current_identity != (folder_a, folder_b):
            return
        self.controller._preview_ready(
            task_id,
            document_id,
            generation,
            value,
        )

    @Slot(str, object, int, object)
    def _preview_failed(
        self,
        task_id: str,
        document_id: object,
        generation: int,
        value: object,
    ) -> None:
        ownership = self._workers.get(task_id)
        if ownership is None:
            return
        revision, folder_a, folder_b = ownership
        if revision != self._active_revision or document_id != revision:
            return
        current_identity = (
            self.workspace.folder_a.text().strip(),
            self.workspace.folder_b.text().strip(),
        )
        if current_identity != (folder_a, folder_b):
            return
        self.controller._preview_failed(
            task_id,
            document_id,
            generation,
            value,
        )

    @Slot(str)
    def _preview_finished(self, task_id: str) -> None:
        ownership = self._workers.pop(task_id, None)
        if ownership is None:
            return
        revision, _folder_a, _folder_b = ownership
        if revision != self._active_revision:
            return
        self._active_revision = None
        if getattr(self.controller, "_active", False):
            self.workspace.preview_button.setEnabled(True)


def install_remote_iqa_preview_lifecycle(window: Any) -> RemoteIqaPreviewLifecycle:
    """Install bounded Folder Pair preview ownership on the existing P5-C controller."""

    controller = getattr(window, "remote_iqa_controller", None)
    if controller is None:
        raise RuntimeError("Remote IQA must be installed before preview lifecycle hardening")
    guard = RemoteIqaPreviewLifecycle(controller, window)
    window.remote_iqa_preview_lifecycle = guard
    return guard
