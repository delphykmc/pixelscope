from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QStackedWidget, QWidget


class PresentationDropStack(QStackedWidget):
    """Single native D&D owner for the Image View presentation surface."""

    paths_dropped = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("presentationDropStack")
        self.setAcceptDrops(True)

    def addWidget(self, widget: QWidget) -> int:  # noqa: N802
        index = super().addWidget(widget)
        self._disable_descendant_drop_targets(widget)
        return index

    @staticmethod
    def _disable_descendant_drop_targets(widget: QWidget) -> None:
        """Keep native target negotiation on this stack, not nested presentation widgets."""

        widget.setAcceptDrops(False)
        for child in widget.findChildren(QWidget):
            child.setAcceptDrops(False)

    @staticmethod
    def _local_paths(event: QDragEnterEvent | QDragMoveEvent | QDropEvent) -> list[Path]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]

    @staticmethod
    def _accept_local_paths(
        event: QDragEnterEvent | QDragMoveEvent | QDropEvent,
        paths: list[Path],
    ) -> bool:
        if not paths:
            event.ignore()
            return False
        if event.possibleActions() & Qt.DropAction.CopyAction:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.acceptProposedAction()
        return True

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        self._accept_local_paths(event, self._local_paths(event))

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        self._accept_local_paths(event, self._local_paths(event))

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = self._local_paths(event)
        if not self._accept_local_paths(event, paths):
            return
        self.paths_dropped.emit(paths)
