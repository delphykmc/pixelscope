from __future__ import annotations

from PySide6.QtCore import Qt

from pixelscope.ui.plot_colors import (
    comparison_pen,
    image_marker_symbol,
    line_profile_pen,
)


def test_comparison_pen_keeps_channel_color_and_varies_six_line_styles() -> None:
    pens = [comparison_pen("R", index) for index in range(6)]
    assert {pen.color().name() for pen in pens} == {"#ff3b30"}
    assert pens[0].style() == Qt.PenStyle.SolidLine
    assert all(pen.style() == Qt.PenStyle.CustomDashLine for pen in pens[1:])
    assert len({tuple(pen.dashPattern()) for pen in pens[1:]}) == 5
    assert all(pen.widthF() <= 1.0 for pen in pens)
    assert all(pen.isCosmetic() for pen in pens)


def test_line_profile_uses_solid_channel_lines_and_stable_image_markers() -> None:
    pens = [line_profile_pen(channel) for channel in ("R", "G", "B")]
    assert [pen.color().name() for pen in pens] == ["#ff3b30", "#24b34b", "#2684ff"]
    assert all(pen.style() == Qt.PenStyle.SolidLine for pen in pens)
    assert all(pen.widthF() <= 1.0 for pen in pens)
    assert [image_marker_symbol(index) for index in range(6)] == [
        "o",
        "s",
        "t",
        "d",
        "+",
        "x",
    ]
