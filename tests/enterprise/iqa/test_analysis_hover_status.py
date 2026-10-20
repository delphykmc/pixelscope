"""Scoped contracts for fixed-width hover values and unknown signal tooltips."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QMainWindow

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    SpatialMap,
    roi_statistics,
)
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow
from pixelscope_enterprise.iqa.hover_fields import format_source_rgb_field
from pixelscope_enterprise.iqa.hover_status import ReservedHoverPair, ReservedHoverReadout
from pixelscope_enterprise.iqa.quality_presentation import verdict_for_value


def test_hover_label_reserves_once_and_elides_right_without_losing_value(qtbot: object) -> None:
    label = ReservedHoverReadout()
    qtbot.addWidget(label)  # type: ignore[attr-defined]
    label.reserve_width(("Position (9999, 9999)", "Position (0, 0)"))
    reserved = label.width()

    label.set_readout("Position (1, 2)")
    assert label.width() == reserved
    assert label.text() == "Position (1, 2)"

    overflowing = "Position (123456789, 987654321) with extra hover details"
    label.set_readout(overflowing)
    assert label.width() == reserved
    assert label.text().endswith("…")
    assert label.text() != overflowing
    assert label.toolTip() == overflowing
    assert label.accessibleName() == overflowing

    label.set_readout("—")
    assert label.width() == reserved
    assert label.text() == "—"

    label.reserve_width(("Position (999999, 999999)",))
    assert label.width() > reserved


def test_hover_label_rejects_empty_reservation(qtbot: object) -> None:
    label = ReservedHoverReadout()
    qtbot.addWidget(label)  # type: ignore[attr-defined]
    with pytest.raises(ValueError, match="at least one"):
        label.reserve_width(())


def test_two_hover_fields_hold_statusbar_geometry_and_do_not_override_errors(
    qtbot: object,
) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.resize(1180, 320)
    status = window.statusBar()
    hover = ReservedHoverPair(status)
    hover.reserve_for_result(
        ("Pixel (9999, 9999)", "Pixel (0, 0)"),
        ("Reference RGB16: 65535, 65535, 65535 · Target RGB16: 65535, 65535, 65535",),
    )
    window.show()
    status.showMessage("Open result failed: saved user-facing error", 0)
    QApplication.processEvents()

    def geometry() -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return (
            (hover.position.x(), hover.position.y(), hover.position.width()),
            (hover.values.x(), hover.values.y(), hover.values.width()),
        )

    initial = geometry()
    for position, values in (
        ("Pixel (1, 2)", "Reference RGB8: 1, 2, 3 · Target RGB: unavailable"),
        ("Pixel (9999, 9999)", "Very long full RGB and map readout " * 9),
        ("Pixel (50, 60)", "Map: invalid"),
    ):
        hover.update(position, values)
        QApplication.processEvents()
        assert geometry() == initial
        assert status.currentMessage() == "Open result failed: saved user-facing error"
        assert hover.position.toolTip() == position
        assert hover.values.toolTip() == values

    assert hover.values.text() == "Map: invalid"
    overflowing = "A large, overflowing value " * 30
    hover.update("Pixel (1, 1)", overflowing)
    assert hover.values.text().endswith("…")
    assert hover.values.toolTip() == overflowing
    assert geometry() == initial

    hover.clear()
    assert geometry() == initial
    assert hover.position.text() == "—"
    assert status.currentMessage() == "Open result failed: saved user-facing error"

    hover.reserve_for_result(("Pixel (999999, 999999)",), ("Map [+999, +999]: +9999.0000",))
    QApplication.processEvents()
    next_result_geometry = geometry()
    hover.update("Pixel (5, 7)", "Map: unavailable")
    QApplication.processEvents()
    assert geometry() == next_result_geometry
    window.close()


def test_unknown_source_signal_is_explained_in_both_attribute_row_cells(
    qtbot: object,
) -> None:
    unknown = AttributeDisplay(
        "unknown_db",
        "Unknown signal",
        "dB",
        "detail",
        1.0,
        "available",
        True,
        5.0,
        summary_signal_gate=None,
    )
    known = AttributeDisplay(
        "known_db",
        "Known signal",
        "dB",
        "detail",
        1.0,
        "available",
        True,
        5.0,
        summary_signal_gate=False,
    )
    result = AnalysisResult("signals", 32, 32, "A", "B", (unknown, known))
    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.present_result(result)
    table = window._group_tables["dB"]

    for column in (0, 1):
        tooltip = table.item(0, column).toolTip()
        assert "Signal level unknown" in tooltip
        assert "no usable original-relative level information" in tooltip
        assert "Signal level unknown" not in table.item(1, column).toolTip()

    window._set_roi(0, 0, 16, 16)
    window.chart_scope_combo.setCurrentIndex(window.chart_scope_combo.findData("roi_grid"))
    assert "Signal level unknown" in table.item(0, 1).toolTip()
    assert "Signal level unknown" not in table.item(1, 1).toolTip()
    window.close()


def test_integrated_hover_layout_and_unknown_quality_tooltips(
    qtbot: object, tmp_path: Path
) -> None:
    """Request 6 consumes request 3's real hover data without changing verdicts."""

    source = tmp_path / "reference.png"
    image = QImage(128, 128, QImage.Format.Format_RGB32)
    image.fill(QColor(17, 33, 65))
    assert image.save(str(source))
    grid = SpatialMap(
        values=np.array([[3.0, -1.0], [0.0, 7.0]]),
        valid_mask=np.array([[True, True], [True, False]]),
        image_width=128,
        image_height=128,
        block_width=64,
        block_height=64,
    )
    unknown = AttributeDisplay(
        "unknown",
        "Unknown level",
        "dB",
        "Detail",
        3.0,
        "available",
        True,
        5.0,
        grid,
        chart_axis_range=5.0,
        summary_signal_gate=None,
        quality_direction="higher_is_better",
    )
    rejected = replace(
        unknown,
        attribute_id="rejected",
        label="Gate rejected",
        summary_signal_gate=False,
    )
    result = AnalysisResult(
        "first-hover",
        128,
        128,
        "reference.png",
        "missing.png",
        (unknown, rejected),
        source_a=source,
        source_a_role="Reference",
        source_b_role="Target",
    )
    original_values = grid.values.copy()
    original_mask = grid.valid_mask.copy()
    original_stats = roi_statistics(grid, (0, 0, 128, 128))

    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.resize(1500, 800)
    window.present_result(result)
    window.show()
    QApplication.processEvents()
    hover = window._hover_readouts
    table = window._group_tables["dB"]

    def geometry() -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        return (
            (hover.position.x(), hover.position.y(), hover.position.width()),
            (hover.values.x(), hover.values.y(), hover.values.width()),
        )

    first_result_geometry = geometry()
    assert first_result_geometry[0][2] > 0
    assert first_result_geometry[1][2] > 0
    assert "Signal level unknown" in table.item(0, 0).toolTip()
    assert "Signal level unknown" in table.item(0, 1).toolTip()
    assert "Signal level unknown" not in table.item(1, 0).toolTip()
    assert "Signal level unknown" not in table.item(1, 1).toolTip()

    window.statusBar().showMessage("Open failed: sanitized user message", 0)
    for x, y in ((1, 1), (65, 1), (65, 65), (1, 65)):
        window._show_hover_pixel(x, y)
        QApplication.processEvents()
        assert geometry() == first_result_geometry
        assert hover.position.toolTip() == f"Pixel ({x}, {y})"
        assert format_source_rgb_field("Reference", (17, 33, 65), bit_depth=8) in (
            hover.values.toolTip()
        )
        assert "Target RGB: unavailable" in hover.values.toolTip()
        assert window.statusBar().currentMessage() == "Open failed: sanitized user message"
        assert len(window._guide_items) == 3
        assert all(vertical.isVisible() for vertical, _ in window._guide_items)

    assert "Unknown level Map [1, 0]: +0.0000 dB" in hover.values.toolTip()
    window.set_quality_presentation(True)
    assert verdict_for_value(unknown, unknown.official_value).verdict == "Not visible"
    assert verdict_for_value(rejected, rejected.official_value).verdict == "Not visible"
    assert "Signal level unknown" in table.item(0, 1).toolTip()
    assert "Signal level unknown" not in table.item(1, 1).toolTip()
    window._set_roi(0, 0, 64, 64)
    window.chart_scope_combo.setCurrentIndex(window.chart_scope_combo.findData("roi_grid"))
    assert "Signal level unknown" in table.item(0, 1).toolTip()
    assert "Signal level unknown" not in table.item(1, 1).toolTip()
    table.setCurrentCell(1, 0)
    QApplication.processEvents()
    assert geometry() == first_result_geometry
    assert "Gate rejected Map" in hover.values.toolTip()
    window._hide_hover_pixel()
    assert hover.position.text() == "—"
    assert window.statusBar().currentMessage() == "Open failed: sanitized user message"

    # Switching results is the one point at which reserved widths may change.
    second = AnalysisResult(
        "second-hover",
        2048,
        1050,
        "another.png",
        "target.png",
        (replace(unknown, spatial=None, summary_signal_gate=True),),
        source_a_role="Long reference role",
        source_b_role="Long target role",
    )
    window.present_result(second)
    QApplication.processEvents()
    second_geometry = geometry()
    assert second_geometry != first_result_geometry
    window._show_hover_pixel(2000, 1024)
    QApplication.processEvents()
    assert geometry() == second_geometry
    assert hover.position.toolTip() == "Pixel (2000, 1024)"
    assert "Map: unavailable" in hover.values.toolTip()

    window.result_combo.setCurrentIndex(window.result_combo.findData("first-hover"))
    QApplication.processEvents()
    assert geometry()[0][2] == first_result_geometry[0][2]
    assert "Signal level unknown" in window._group_tables["dB"].item(0, 1).toolTip()
    np.testing.assert_array_equal(grid.values, original_values)
    np.testing.assert_array_equal(grid.valid_mask, original_mask)
    assert roi_statistics(grid, (0, 0, 128, 128)) == original_stats
    window.close()
