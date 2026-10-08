"""Focus: extension-owned QMainWindow is independent from MainWindow and provider jobs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QApplication

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    SpatialMap,
)
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow, AnalysisWindowManager


def _result(result_id: str) -> AnalysisResult:
    grid = SpatialMap(
        values=np.array([[3.0, -3.0], [0.0, 0.0]]),
        valid_mask=np.array([[True, True], [True, False]]),
        image_width=128,
        image_height=128,
        block_width=64,
        block_height=64,
    )
    attributes = (
        AttributeDisplay(
            "metric_db", "Example dB", "dB", "power", 1.5, "available", True, 5.0, grid
        ),
        AttributeDisplay(
            "metric_delta", "Example delta", "delta", "signed", None, "missing", False, 2.0, None
        ),
    )
    return AnalysisResult(
        result_id,
        128,
        128,
        "Synthetic A",
        "Synthetic B",
        attributes,
        source_a=Path("not-installed-a.png"),
        source_b=Path("not-installed-b.png"),
    )


def test_empty_window_nonmodal_and_file_operations_gated(qtbot: object) -> None:
    manager = AnalysisWindowManager()
    win = manager.show()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    assert isinstance(win, AnalysisWindow)
    assert not win.isModal()
    assert win.active_result_id is None
    assert not win.open_action.isEnabled()
    assert not win.save_action.isEnabled()
    assert win.export_action.isEnabled() is False
    assert manager.show() is win
    win.close()
    assert manager.show() is win
    manager.shutdown()


def test_window_preserves_roi_and_per_result_state(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.show()
    win.present_result(_result("one"))
    win._set_roi(0, 0, 64, 64)
    assert win.current_roi == (0, 0, 64, 64)
    assert "GRID-DERIVED" in win.roi_label.text()
    win.range_editor.setValue(2.0)
    assert "Clamped: 2/3" in win.clamp_label.text()

    win.attribute_table.selectRow(1)
    assert win.current_roi == (0, 0, 64, 64)
    assert "not zero" in win.official_label.text()
    win.present_result(_result("two"))
    assert win.current_roi is None
    win.result_combo.setCurrentIndex(win.result_combo.findData("one"))
    assert win.active_result_id == "one"
    assert win.current_roi == (0, 0, 64, 64)
    assert win._state().ranges["metric_db"] == 2.0  # type: ignore[union-attr]
    assert win._state().attribute_id == "metric_delta"  # type: ignore[union-attr]
    assert win.current_analysis_state()["roi"] == [0, 0, 64, 64]
    win.close()


def test_missing_sources_do_not_invalidate_spatial_analysis(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(_result("missing_sources"))
    assert win.active_result_id == "missing_sources"
    assert "OFFICIAL full-pair" in win.official_label.text()
    assert "Clamped:" in win.clamp_label.text()
    assert win._views[0].scene().items()  # type: ignore[union-attr]
    assert win._views[1].scene().items()  # type: ignore[union-attr]
    win.close()


def test_explicit_open_handler_does_not_derive_result_from_job(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    assert not win.open_action.isEnabled()
    win.install_file_handlers(load=lambda _: _result("opened"))
    assert win.open_action.isEnabled()
    assert not win.save_action.isEnabled()
    win.present_result(_result("opened"))
    win.install_file_handlers(save=lambda _result, _state, _path: None)
    assert win.save_action.isEnabled()
    win.close()


def test_qt_runtime_exists_for_smoke(qtbot: object) -> None:
    assert QApplication.instance() is not None
