"""Scoped contracts for fixed-width hover values and unknown signal tooltips."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow
from pixelscope_enterprise.iqa.hover_status import ReservedHoverPair, ReservedHoverReadout


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
