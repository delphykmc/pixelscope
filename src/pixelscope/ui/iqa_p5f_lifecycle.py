"""P5-F lifetime glue for bounded reusable Remote IQA transport clients."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QObject

from pixelscope.remote.iqa_transport_pool import ReusableIqaClientPool


class _RemoteIqaTransportCloseFilter(QObject):
    def __init__(
        self,
        pool: ReusableIqaClientPool,
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._pool = pool

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() is QEvent.Type.Close:
            self._pool.close()
        return super().eventFilter(watched, event)


def install_remote_iqa_transport_lifecycle(
    window: Any,
    pool: ReusableIqaClientPool,
) -> None:
    """Close idle transport resources with the owning MainWindow, never remote jobs."""

    close_filter = _RemoteIqaTransportCloseFilter(pool, window)
    window.installEventFilter(close_filter)
    window._remote_iqa_transport_close_filter = close_filter
