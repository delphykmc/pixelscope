from __future__ import annotations

import ctypes
import logging
import sys

from PySide6.QtWidgets import QApplication

LOGGER = logging.getLogger(__name__)


def _running_on_windows() -> bool:
    return sys.platform == "win32"


def _flush_windows_ole_clipboard() -> int | None:
    """Materialize Qt delayed-render clipboard data and release OLE ownership."""

    loader = getattr(ctypes, "WinDLL", None)
    if loader is None:
        LOGGER.warning("Windows clipboard flush API is unavailable")
        return None

    try:
        ole32 = loader("ole32")
        flush = ole32.OleFlushClipboard
        flush.argtypes = []
        flush.restype = ctypes.c_long
        return int(flush())
    except (AttributeError, OSError):
        LOGGER.warning(
            "Unable to flush Windows OLE clipboard ownership",
            exc_info=True,
        )
        return None


def set_clipboard_text(text: str) -> None:
    """Copy text while avoiding deferred Windows OLE ownership at teardown."""

    QApplication.clipboard().setText(text)

    if not _running_on_windows():
        return

    hresult = _flush_windows_ole_clipboard()
    if hresult is not None and hresult < 0:
        LOGGER.warning(
            "OleFlushClipboard failed with HRESULT 0x%08X",
            hresult & 0xFFFFFFFF,
        )
