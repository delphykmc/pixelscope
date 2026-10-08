"""Focus: extension-owned QMainWindow is independent from MainWindow and provider jobs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    LoadedAnalysis,
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
    result = _result("opened")
    win.install_file_handlers(load=lambda _: LoadedAnalysis(result))
    assert win.open_action.isEnabled()
    assert not win.save_action.isEnabled()
    win.present_result(result)
    win.install_file_handlers(save=lambda _result, _state, _path: None)
    assert win.save_action.isEnabled()
    win.close()


def test_qt_runtime_exists_for_smoke(qtbot: object) -> None:
    assert QApplication.instance() is not None


def test_duplicate_result_identity_must_not_mutate_visible_result(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    first = _result("same")
    win.present_result(first)
    win._set_roi(0, 0, 64, 64)
    assert win.active_result_id == "same"
    with pytest.raises(ValueError, match="immutable result ID"):
        win.present_result(_result("same"))  # new object, potentially changed content
    assert win._results["same"] is first
    assert win.current_roi == (0, 0, 64, 64)
    # The same validated immutable object may be selected again.
    win.present_result(first)
    assert win._results["same"] is first
    assert win.result_combo.count() == 1
    win.close()


def test_duplicate_id_changed_attribute_set_or_sources_is_rejected(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    original = _result("unchanged")
    win.present_result(original)
    changed = AnalysisResult(
        "unchanged", 128, 128, "Synthetic A", "Synthetic B",
        attributes=(original.attributes[1],),
        source_a=Path("different-a.png"),
        source_b=Path("different-b.png"),
    )
    with pytest.raises(ValueError, match="immutable result ID"):
        win.present_result(changed)
    assert win._results["unchanged"] is original
    assert win._state().attribute_id == "metric_db"  # type: ignore[union-attr]
    assert win._source_result_id == "unchanged"
    win.close()


def test_saved_analysis_state_validation_and_restoration(qtbot: object) -> None:
    source = AnalysisWindow()
    qtbot.addWidget(source)  # type: ignore[attr-defined]
    result = _result("saved-identity")
    source.present_result(result)
    source._set_roi(0, 0, 64, 64)
    source.range_editor.setValue(2.0)
    source.attribute_table.selectRow(1)
    state = source.current_analysis_state()
    assert state["attribute_id"] == "metric_delta"
    source.close()

    target = AnalysisWindow()
    qtbot.addWidget(target)  # type: ignore[attr-defined]
    target.present_result(result, analysis_state=state)
    assert target.current_roi == (0.0, 0.0, 64.0, 64.0)
    assert target.current_analysis_state()["ranges"] == {"metric_db": 2.0}
    assert target._state().attribute_id == "metric_delta"  # type: ignore[union-attr]
    assert "neutral / no winner inferred" in target.official_label.text()

    bad = dict(state)
    bad["attribute_id"] = "removed-id"
    with pytest.raises(ValueError, match="unknown saved attribute"):
        target.present_result(result, analysis_state=bad)
    assert target.current_analysis_state()["attribute_id"] == "metric_delta"

    invalid_roi = dict(state)
    invalid_roi["roi"] = [0, 0, 1e9, 64]
    with pytest.raises(ValueError, match="saved ROI"):
        target.present_result(result, analysis_state=invalid_roi)
    target.close()


def test_reader_carries_validated_state_separate_from_official_result(
    qtbot: object, monkeypatch: object, tmp_path: Path
) -> None:
    from PySide6.QtWidgets import QFileDialog

    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    result = _result("reopened")
    state: dict[str, object] = {
        "attribute_id": "metric_delta",
        "roi": [0, 0, 64, 64],
        "ranges": {"metric_db": 3.0},
        "viewport": {"scale": None, "center_x": None, "center_y": None},
    }
    win.install_file_handlers(load=lambda _: LoadedAnalysis(result, state))
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QFileDialog, "getOpenFileName", lambda *_args: (str(tmp_path / "stub"), "")
    )
    win._open_from_dialog()
    assert win.active_result_id == "reopened"
    assert win.current_roi == (0, 0, 64, 64)
    assert win._state().ranges == {"metric_db": 3.0}  # type: ignore[union-attr]
    win.close()
