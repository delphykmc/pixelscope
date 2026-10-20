"""Fixed-pitch, column-stable RGB hover presentation for the IQA Analysis Window.

These display helpers are independent of the hover producer and the
bounded status-bar widgets. No source pixels or IQA values are modified.
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
    """Pad source slots to the maximum channel width, including unavailable.

    Missing sources have no trustworthy bit depth, so reserve the worst
    supported (16-bit) value width. Within a Result the source availability
    and depth are fixed while the pointer moves. This formatter never
    touches the scientific samples and does not elide the original text.
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
        channels = ", ".join(f"{channel:>{digits}}" for channel in rgb)
        value = f"{role} RGB{depth}: {channels}"
    return value.ljust(len(full_example))
