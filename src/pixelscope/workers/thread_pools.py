from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

ANALYSIS_MAX_THREADS = 2
_ANALYSIS_POOL_ATTRIBUTE = "_pixelscope_analysis_thread_pool"
_DISPLAY_PREVIEW_POOL_ATTRIBUTE = "_pixelscope_display_preview_thread_pool"
_BACKGROUND_POOL_SHUTDOWN_HOOK_ATTRIBUTE = (
    "_pixelscope_background_thread_pool_shutdown_hook"
)


def _shutdown_pool(attribute: str, timeout_ms: int) -> bool:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return True
    pool = getattr(app, attribute, None)
    if not isinstance(pool, QThreadPool):
        return True
    pool.clear()
    return pool.waitForDone(timeout_ms)


def shutdown_analysis_thread_pool(timeout_ms: int = 3000) -> bool:
    """Clear queued analysis work and wait briefly for running calculations."""

    return _shutdown_pool(_ANALYSIS_POOL_ATTRIBUTE, timeout_ms)


def shutdown_background_thread_pools(timeout_ms: int = 3000) -> bool:
    """Finish the app-owned full-frame analysis and display-render pools."""

    analysis_done = shutdown_analysis_thread_pool(timeout_ms)
    display_done = _shutdown_pool(_DISPLAY_PREVIEW_POOL_ATTRIBUTE, timeout_ms)
    return analysis_done and display_done


def analysis_thread_pool() -> QThreadPool:
    """Return the app-owned pool for full-frame Statistics and Difference work."""

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("Analysis workers require QApplication")
    pool = getattr(app, _ANALYSIS_POOL_ATTRIBUTE, None)
    if not isinstance(pool, QThreadPool):
        pool = QThreadPool(app)
        pool.setMaxThreadCount(ANALYSIS_MAX_THREADS)
        setattr(app, _ANALYSIS_POOL_ATTRIBUTE, pool)
    if not bool(getattr(app, _BACKGROUND_POOL_SHUTDOWN_HOOK_ATTRIBUTE, False)):
        # PySide6 6.4.2's type stubs omit QApplication.aboutToQuit even though
        # the inherited QCoreApplication signal is present at runtime.
        cast(Any, app).aboutToQuit.connect(shutdown_background_thread_pools)
        setattr(app, _BACKGROUND_POOL_SHUTDOWN_HOOK_ATTRIBUTE, True)
    return pool
