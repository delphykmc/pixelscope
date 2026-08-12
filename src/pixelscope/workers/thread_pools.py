from __future__ import annotations

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

ANALYSIS_MAX_THREADS = 2
_ANALYSIS_POOL_ATTRIBUTE = "_pixelscope_analysis_thread_pool"
_ANALYSIS_POOL_SHUTDOWN_HOOK_ATTRIBUTE = "_pixelscope_analysis_thread_pool_shutdown_hook"


def shutdown_analysis_thread_pool(timeout_ms: int = 3000) -> bool:
    """Clear queued analysis work and wait briefly for running calculations."""

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return True
    pool = getattr(app, _ANALYSIS_POOL_ATTRIBUTE, None)
    if not isinstance(pool, QThreadPool):
        return True
    pool.clear()
    return pool.waitForDone(timeout_ms)


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
    if not bool(getattr(app, _ANALYSIS_POOL_SHUTDOWN_HOOK_ATTRIBUTE, False)):
        app.aboutToQuit.connect(shutdown_analysis_thread_pool)
        setattr(app, _ANALYSIS_POOL_SHUTDOWN_HOOK_ATTRIBUTE, True)
    return pool
