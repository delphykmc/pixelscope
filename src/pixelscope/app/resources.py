from __future__ import annotations

import logging
import sys
from importlib.resources import files

from PySide6.QtGui import QIcon, QPixmap

LOGGER = logging.getLogger(__name__)
_ICON_PARTS = ("assets", "icons", "pixelscope.png")


def _icon_failure(message: str) -> QIcon:
    """Keep source-run fallback, but fail frozen startup when a core resource is broken."""

    if getattr(sys, "frozen", False):
        raise RuntimeError(message)
    LOGGER.warning(message)
    return QIcon()


def load_application_icon() -> QIcon:
    """Load the canonical application icon from packaged resource bytes."""

    resource = files("pixelscope")
    for part in _ICON_PARTS:
        resource = resource.joinpath(part)

    try:
        icon_bytes = resource.read_bytes()
    except OSError:
        return _icon_failure("PixelScope application icon resource is unavailable")

    pixmap = QPixmap()
    if not pixmap.loadFromData(icon_bytes):
        return _icon_failure("PixelScope application icon resource is invalid")
    return QIcon(pixmap)
