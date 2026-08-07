from __future__ import annotations

import logging
from importlib.resources import files

from PySide6.QtGui import QIcon, QPixmap

LOGGER = logging.getLogger(__name__)
_ICON_PARTS = ("assets", "icons", "pixelscope.png")


def load_application_icon() -> QIcon:
    """Load the canonical application icon from packaged resource bytes."""

    resource = files("pixelscope")
    for part in _ICON_PARTS:
        resource = resource.joinpath(part)

    try:
        icon_bytes = resource.read_bytes()
    except OSError:
        LOGGER.warning("PixelScope application icon resource is unavailable")
        return QIcon()

    pixmap = QPixmap()
    if not pixmap.loadFromData(icon_bytes):
        LOGGER.warning("PixelScope application icon resource is invalid")
        return QIcon()
    return QIcon(pixmap)
