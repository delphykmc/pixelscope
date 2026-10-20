"""Fixed-pitch, column-stable RGB hover presentation for the IQA Analysis Window.

These display helpers are independent of the hover producer (#195) and the
bounded status-bar labels (#201). No source pixels or IQA values are modified.
"""

from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase


def hover_fixed_pitch_font() -> QFont:
    """Use the platform's actual fixed-pitch font, including Windows/Qt 6.4."""

    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font


def format_source_rgb_field(
    role: str,
    rgb: tuple[int, int, int] | None,
    *,
    bit_depth: int | None,
) -> str:
    """Pad *every* source slot to its full RGB width for stable later columns.

    Missing sources have no trustworthy bit depth, so reserve the worst
    supported (16-bit) value width. A result's role and source availability
    remain unchanged while the pointer moves. The status-label owner may
    further reserve overall pixel/map width and elide only on the right.
    """

    if bit_depth not in (None, 8, 16):
        raise ValueError("RGB hover supports only 8/16-bit source displays")
    if rgb is not None and bit_depth is None:
        raise ValueError("available RGB needs an explicit source bit depth")
    depth = bit_depth or 16
    maximum = (1 << depth) - 1
    digits = len(str(maximum))
    full_example = f"{role} RGB{depth}: {maximum}, {maximum}, {maximum}"
    if rgb is None:
        value = f"{role} RGB: unavailable"
    else:
        if len(rgb) != 3 or any(channel < 0 or channel > maximum for channel in rgb):
            raise ValueError("RGB hover values exceed the declared source bit depth")
        value = (
            f"{role} RGB{depth}: "
            f"{rgb[0]:>{digits}}, {rgb[1]:>{digits}}, {rgb[2]:>{digits}}"
        )
    return value.ljust(len(full_example))
