from __future__ import annotations

import logging
import os

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication, QWidget

LOGGER = logging.getLogger("pixelscope.dnd")
_TRACE_ENV = "PIXELSCOPE_DND_TRACE"
_TRACE_EVENT_TYPES = {
    QEvent.Type.DragEnter,
    QEvent.Type.DragMove,
    QEvent.Type.DragLeave,
    QEvent.Type.Drop,
}


class DndTraceFilter(QObject):
    """Read-only QApplication trace for native drag/drop routing diagnostics."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() not in _TRACE_EVENT_TYPES:
            return False
        chain: list[str] = []
        current: QObject | None = watched if isinstance(watched, QObject) else None
        while current is not None and len(chain) < 8:
            name = current.objectName() if hasattr(current, "objectName") else ""
            chain.append(f"{type(current).__name__}({name})")
            current = current.parent()

        has_urls = False
        local_paths: list[str] = []
        proposed = None
        possible = None
        drop_action = None
        if isinstance(event, QDropEvent):
            mime = event.mimeData()
            has_urls = mime.hasUrls()
            local_paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
            proposed = event.proposedAction()
            possible = event.possibleActions()
            drop_action = event.dropAction()

        LOGGER.info(
            "DND pre type=%s watched=%s widget=%s chain=%s has_urls=%s local_paths=%s "
            "proposed=%s possible=%s drop_action=%s accepted=%s",
            event.type().name,
            type(watched).__name__,
            isinstance(watched, QWidget),
            " -> ".join(chain),
            has_urls,
            local_paths,
            proposed,
            possible,
            drop_action,
            event.isAccepted(),
        )
        return False


def install_dnd_trace(app: QApplication) -> DndTraceFilter | None:
    """Install native D&D tracing only when explicitly enabled for diagnosis."""

    if os.environ.get(_TRACE_ENV, "").strip() not in {"1", "true", "TRUE", "yes", "YES"}:
        return None
    existing = getattr(app, "_pixelscope_dnd_trace_filter", None)
    if isinstance(existing, DndTraceFilter):
        return existing
    trace = DndTraceFilter(app)
    app.installEventFilter(trace)
    setattr(app, "_pixelscope_dnd_trace_filter", trace)
    LOGGER.info("Native D&D trace enabled via %s", _TRACE_ENV)
    return trace
