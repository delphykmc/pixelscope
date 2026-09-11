from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QBoxLayout, QVBoxLayout, QWidget


_DropEvent = QDragEnterEvent | QDragMoveEvent | QDropEvent
_BLINK_EVENT_TYPES = {
    QEvent.Type.ApplicationDeactivate,
    QEvent.Type.WindowDeactivate,
    QEvent.Type.Close,
    QEvent.Type.KeyPress,
    QEvent.Type.KeyRelease,
}


class PresentationDropHost(QWidget):
    """Single native D&D owner wrapping every Image View presentation state."""

    paths_dropped = Signal(object)

    def __init__(self, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("presentationDropHost")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(content)
        self.content = content
        self.refresh_descendant_ownership()

    def refresh_descendant_ownership(self) -> None:
        """Ensure nested Qt/pyqtgraph widgets cannot become competing native drop targets."""

        self.content.setAcceptDrops(False)
        for child in self.content.findChildren(QWidget):
            child.setAcceptDrops(False)

    @staticmethod
    def local_paths(event: _DropEvent) -> list[Path]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        return [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]

    @staticmethod
    def accept_local_paths(event: _DropEvent, paths: list[Path]) -> bool:
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
        self.accept_local_paths(event, self.local_paths(event))

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        self.accept_local_paths(event, self.local_paths(event))

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = self.local_paths(event)
        if not self.accept_local_paths(event, paths):
            return
        self.paths_dropped.emit(paths)


class _MainWindowDragMoveFilter(QObject):
    """Complete the legacy top-level fallback lifecycle without owning Image View D&D."""

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is not self.window or event.type() != QEvent.Type.DragMove:
            return False
        drag_event = cast(QDragMoveEvent, event)
        paths = PresentationDropHost.local_paths(drag_event)
        if not paths:
            return False
        PresentationDropHost.accept_local_paths(drag_event, paths)
        return True


class _BlinkOnlyApplicationFilter(QObject):
    """Forward only Blink lifecycle events after native D&D leaves the global filter."""

    def __init__(self, controller: QObject, app: QApplication) -> None:
        super().__init__(app)
        self.controller = controller

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() not in _BLINK_EVENT_TYPES:
            return False
        return bool(self.controller.eventFilter(watched, event))


def install_presentation_drop_host(
    window: Any,
    handler: Callable[[list[Path]], None],
    *,
    quick_compare_filter: QObject | None = None,
) -> PresentationDropHost:
    """Wrap the existing central stack in one stable native Image View drop target."""

    existing = getattr(window, "presentation_drop_host", None)
    if isinstance(existing, PresentationDropHost):
        return existing

    stack = window.central_stack
    parent = stack.parentWidget()
    outer_layout = parent.layout() if parent is not None else None
    if parent is None or not isinstance(outer_layout, QBoxLayout):
        raise RuntimeError("Quick Compare presentation stack has no replaceable box layout")

    index = outer_layout.indexOf(stack)
    if index < 0:
        raise RuntimeError("Quick Compare presentation stack is not owned by its presentation layout")
    stretch = outer_layout.stretch(index)
    outer_layout.removeWidget(stack)

    host = PresentationDropHost(stack, parent)
    outer_layout.insertWidget(index, host, stretch)
    host.paths_dropped.connect(handler)

    fallback_filter = _MainWindowDragMoveFilter(window)
    window.installEventFilter(fallback_filter)
    window.__dict__["_presentation_drop_fallback_filter"] = fallback_filter

    app = QApplication.instance()
    if quick_compare_filter is not None and isinstance(app, QApplication):
        app.removeEventFilter(quick_compare_filter)
        blink_filter = _BlinkOnlyApplicationFilter(quick_compare_filter, app)
        app.installEventFilter(blink_filter)
        window.__dict__["_quick_compare_blink_filter"] = blink_filter

    window.__dict__["presentation_drop_host"] = host
    return host
