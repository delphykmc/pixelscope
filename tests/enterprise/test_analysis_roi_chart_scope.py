"""Issue #155 Slice B: explicit full-pair vs provisional ROI grid chart semantics."""

from __future__ import annotations

import numpy as np
import pytest

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay, SpatialMap
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow
from pixelscope_enterprise.iqa.attribute_chart import (
    ATTRIBUTE_ROLE,
    CHART_MEASUREMENT_ROLE,
    DISPLAY_RANGE_ROLE,
    ChartMeasurement,
)
from pixelscope_enterprise.iqa.measurement_export import build_measurements_csv


def _result(result_id: str = "roi-scope") -> AnalysisResult:
    grid = SpatialMap(
        values=np.array([[4.0, -4.0], [0.0, 0.0]]),
        valid_mask=np.array([[True, True], [True, False]]),
        image_width=128,
        image_height=128,
        block_width=64.0,
        block_height=64.0,
    )
    return AnalysisResult(
        result_id,
        128,
        128,
        "Source A",
        "Source B",
        (
            AttributeDisplay(
                "metric",
                "Metric",
                "dB",
                "SNR",
                1.5,
                "available",
                True,
                6.0,
                grid,
                chart_axis_range=6.0,
            ),
            AttributeDisplay("without_grid", "No map", "dB", "SNR", -2.0, "available", True, 6.0),
            AttributeDisplay(
                "partial",
                "Partial",
                "delta",
                "signed",
                3.0,
                "partial",
                False,
                5.0,
                grid,
                chart_axis_range=5.0,
            ),
        ),
    )


def _chart(win: AnalysisWindow, unit: str, row: int) -> ChartMeasurement | None:
    value = win._group_tables[unit].item(row, 1).data(CHART_MEASUREMENT_ROLE)
    assert value is None or isinstance(value, ChartMeasurement)
    return value


def test_first_roi_autoselects_signed_grid_scope_and_clear_restores_full(
    qtbot: object,
) -> None:
    result = _result()
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(result)
    assert win.chart_scope_combo.currentData() == "full_pair"
    assert not win.chart_scope_combo.model().item(1).isEnabled()
    assert _chart(win, "dB", 0) is None
    assert win.chart_scope_combo.currentText() == "Full"
    before_csv = build_measurements_csv(result)

    win._set_roi(0, 0, 64, 64)
    assert win.chart_scope_combo.currentData() == "roi_grid"
    assert win.chart_scope_combo.model().item(1).isEnabled()
    assert win.chart_scope_combo.currentText() == "ROI · grid"
    assert "not validated local quality scores" in win.chart_scope_combo.toolTip()
    assert win._group_tables["dB"].horizontalHeaderItem(1).text() == "ROI Δ (grid)"
    roi = _chart(win, "dB", 0)
    assert roi is not None and roi.value == pytest.approx(4.0)
    assert roi.availability == "available"
    assert roi.valid_coverage == pytest.approx(1.0)
    assert "no regional quality winner" in win._group_tables["dB"].item(0, 1).toolTip()
    assert _chart(win, "dB", 1) == ChartMeasurement(None, "missing", 0.0)
    assert _chart(win, "delta", 0).value == pytest.approx(4.0)
    assert win._group_tables["dB"].item(0, 1).data(ATTRIBUTE_ROLE) is result.attributes[0]

    win._update_group_range("dB", 10.0)
    assert win._group_tables["dB"].item(0, 1).data(DISPLAY_RANGE_ROLE) == 10.0
    win.gain_editor.setValue(2.0)
    assert _chart(win, "dB", 0) == roi  # Map gain and Range do not change science
    assert result.attributes[0].official_value == 1.5
    assert build_measurements_csv(result) == before_csv

    win._set_roi(64, 0, 64, 64)
    moved = _chart(win, "dB", 0)
    assert moved is not None and moved.value == pytest.approx(-4.0)
    assert win._state().chart_scope == "roi_grid"
    win.clear_roi_button.click()
    assert win.current_roi is None
    assert win.chart_scope_combo.currentData() == "full_pair"
    assert not win.chart_scope_combo.model().item(1).isEnabled()
    assert _chart(win, "dB", 0) is None
    assert win._group_tables["dB"].horizontalHeaderItem(1).text() == "Pair Δ"
    win.close()


def test_manual_full_pair_override_and_per_result_state_roundtrip(qtbot: object) -> None:
    first = _result("first")
    second = _result("second")
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(first)
    win._set_roi(0, 0, 64, 64)
    win.chart_scope_combo.setCurrentIndex(0)
    assert win.current_roi == (0, 0, 64, 64)
    assert win._state().scope_user_override
    assert _chart(win, "dB", 0) is None  # Manual full-pair mode despite ROI
    win._set_roi(64, 0, 64, 64)
    assert win.chart_scope_combo.currentData() == "full_pair"
    assert _chart(win, "dB", 0) is None
    win.chart_scope_combo.setCurrentIndex(1)
    assert _chart(win, "dB", 0).value == pytest.approx(-4.0)

    state = win.current_analysis_state()
    assert state["chart_scope"] == "roi_grid"
    assert state["scope_user_override"] is True
    win.present_result(second)
    assert win.chart_scope_combo.currentData() == "full_pair"
    win.result_combo.setCurrentIndex(win.result_combo.findData("first"))
    assert win.chart_scope_combo.currentData() == "roi_grid"
    assert _chart(win, "dB", 0).value == pytest.approx(-4.0)
    win.close()

    restored = AnalysisWindow()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    restored.present_result(first, analysis_state=state)
    assert restored.chart_scope_combo.currentData() == "roi_grid"
    assert restored.current_roi == (64, 0, 64, 64)
    assert _chart(restored, "dB", 0).value == pytest.approx(-4.0)

    legacy = {k: v for k, v in state.items() if k not in ("chart_scope", "scope_user_override")}
    restored.present_result(first, analysis_state=legacy)
    assert restored.chart_scope_combo.currentData() == "full_pair"
    assert restored.current_roi == (64, 0, 64, 64)
    assert restored.current_analysis_state()["chart_scope"] == "full_pair"
    invalid = dict(state, roi=None)
    with pytest.raises(ValueError, match="requires a saved ROI"):
        restored.present_result(first, analysis_state=invalid)
    assert restored.chart_scope_combo.currentData() == "full_pair"
    invalid = dict(state, scope_user_override="yes")
    with pytest.raises(ValueError, match="invalid chart scope"):
        restored.present_result(first, analysis_state=invalid)
    restored.close()


def test_clear_roi_starts_new_automatic_scope_cycle(qtbot: object) -> None:
    """Manual Full holds only within one ROI selection session."""

    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(_result("fresh-roi"))
    win._set_roi(0, 0, 64, 64)
    assert win.chart_scope_combo.currentData() == "roi_grid"
    win.chart_scope_combo.setCurrentIndex(0)
    assert win._state().scope_user_override
    win._set_roi(64, 0, 64, 64)
    assert win.chart_scope_combo.currentData() == "full_pair"
    win._clear_roi()
    assert win.chart_scope_combo.currentData() == "full_pair"
    assert win._state().scope_user_override is False
    win._set_roi(0, 0, 64, 64)
    assert win.chart_scope_combo.currentData() == "roi_grid"
    assert _chart(win, "dB", 0).value == pytest.approx(4.0)
    win.close()


def test_valid_grid_zero_is_numeric_and_invalid_area_is_missing(qtbot: object) -> None:
    grid = SpatialMap(
        values=np.array([[0.0, np.nan], [5.0, 9.0]]),
        valid_mask=np.array([[True, False], [True, True]]),
        image_width=128,
        image_height=128,
        block_width=64,
        block_height=64,
    )
    result = AnalysisResult(
        "zero-and-missing",
        128,
        128,
        "A",
        "B",
        (AttributeDisplay("m", "M", "dB", "SNR", 1.0, "available", True, 5.0, grid),),
    )
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(result)
    win._set_roi(0, 0, 64, 64)
    zero = _chart(win, "dB", 0)
    assert zero is not None
    assert zero.value == 0.0 and zero.availability == "available"
    win._set_roi(64, 0, 64, 64)
    missing = _chart(win, "dB", 0)
    assert missing is not None
    assert missing.value is None and missing.availability == "missing"
    assert missing.valid_coverage == 0.0
    win.chart_scope_combo.setCurrentIndex(0)
    assert _chart(win, "dB", 0) is None
    assert win.chart_scope_combo.currentText() == "Full"
    win.close()
