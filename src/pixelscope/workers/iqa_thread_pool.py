"""Application-owned bounded executor for Remote IQA result/file work."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

REMOTE_IQA_MAX_THREADS = 2
_REMOTE_IQA_POOL_ATTRIBUTE = "_pixelscope_remote_iqa_thread_pool"
_REMOTE_IQA_POOL_SHUTDOWN_HOOK_ATTRIBUTE = "_pixelscope_remote_iqa_pool_shutdown_hook"


def shutdown_remote_iqa_thread_pool(timeout_ms: int = 3000) -> bool:
    """Clear queued Remote IQA work and briefly join running feature-local tasks."""

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return True
    pool = getattr(app, _REMOTE_IQA_POOL_ATTRIBUTE, None)
    if not isinstance(pool, QThreadPool):
        return True
    pool.clear()
    return pool.waitForDone(timeout_ms)


def remote_iqa_thread_pool() -> QThreadPool:
    """Return the feature-owned pool isolated from local Statistics/Difference work."""

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("Remote IQA workers require QApplication")
    pool = getattr(app, _REMOTE_IQA_POOL_ATTRIBUTE, None)
    if not isinstance(pool, QThreadPool):
        pool = QThreadPool(app)
        pool.setMaxThreadCount(REMOTE_IQA_MAX_THREADS)
        setattr(app, _REMOTE_IQA_POOL_ATTRIBUTE, pool)
    if not bool(getattr(app, _REMOTE_IQA_POOL_SHUTDOWN_HOOK_ATTRIBUTE, False)):
        cast(Any, app).aboutToQuit.connect(shutdown_remote_iqa_thread_pool)
        setattr(app, _REMOTE_IQA_POOL_SHUTDOWN_HOOK_ATTRIBUTE, True)
    return pool
