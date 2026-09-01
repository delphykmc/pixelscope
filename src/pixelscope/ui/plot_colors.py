from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPen

_CHANNEL_COLORS = {
    "R": "#ff3b30",
    "G": "#24b34b",
    "Gr": "#35d05b",
    "Gb": "#168f38",
    "B": "#2684ff",
    "Y": "#d5d5d5",
    "U": "#00a7c4",
    "V": "#c75bdb",
    "A": "#b56cff",
    "Gray": "#d5d5d5",
}

_DASH_PATTERNS = (
    (),
    (14.0, 7.0),
    (2.0, 6.0),
    (14.0, 6.0, 2.0, 6.0),
    (14.0, 5.0, 2.0, 4.0, 2.0, 5.0),
    (24.0, 5.0, 4.0, 5.0),
)

_IMAGE_MARKER_SYMBOLS = ("o", "s", "t", "d", "+", "x")


def channel_color(channel_name: str) -> str:
    """Return one stable semantic color per channel."""

    return _CHANNEL_COLORS.get(channel_name, _CHANNEL_COLORS["Gray"])


def comparison_pen(channel_name: str, image_index: int, width: float = 0.9) -> QPen:
    """Differentiate up to six images by line style while keeping channel colors fixed."""

    pen = QPen(channel_color(channel_name))
    pen.setWidthF(width)
    pen.setCosmetic(True)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pattern = _DASH_PATTERNS[image_index % len(_DASH_PATTERNS)]
    if pattern:
        pen.setStyle(Qt.PenStyle.CustomDashLine)
        pen.setDashPattern(list(pattern))
    else:
        pen.setStyle(Qt.PenStyle.SolidLine)
    return pen


def line_profile_pen(channel_name: str, width: float = 0.8) -> QPen:
    """Keep profile trends continuous; image identity is encoded by markers."""

    pen = QPen(channel_color(channel_name))
    pen.setWidthF(width)
    pen.setCosmetic(True)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setStyle(Qt.PenStyle.SolidLine)
    return pen


def image_marker_symbol(image_index: int) -> str:
    """Return a stable marker symbol for one of the six comparison images."""

    return _IMAGE_MARKER_SYMBOLS[image_index % len(_IMAGE_MARKER_SYMBOLS)]
