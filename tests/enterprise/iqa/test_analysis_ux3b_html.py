"""UX-3B HTML action: genuine offline export and cancel/no-clobber Qt behavior."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QFileDialog, QInputDialog

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay, SpatialMap
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow


def _result(source: Path | None = None) -> AnalysisResult:
    grid = SpatialMap(
        values=np.array([[1.0, -2.0], [0.0, 0.5]], dtype=np.float64),
        valid_mask=np.array([[True, False], [True, True]]),
        image_width=16,
        image_height=12,
        block_width=8.0,
        block_height=6.0,
    )
    attr = AttributeDisplay(
        attribute_id="signed",
        label="Difference",
        unit="dB",
        group="Noise",
        official_value=0.75,
        official_availability="available",
        quality_oriented=False,
        fixed_range=4.0,
        spatial=grid,
    )
    return AnalysisResult(
        result_id="html-synthetic",
        image_width=16,
        image_height=12,
        source_a_label="A",
        source_b_label="B",
        attributes=(attr,),
        source_a=source,
    )


def test_html_menu_can_export_roi_and_preserves_live_state(
    qtbot: object, monkeypatch: object, tmp_path: Path
) -> None:
    rgb = tmp_path / "source.png"
    image = QImage(16, 12, QImage.Format.Format_RGB32)
    image.fill(QColor(40, 60, 80))
    assert image.save(str(rgb))
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    assert not win.report_export_action.isEnabled()
    win.present_result(_result(rgb))
    win.show()
    assert win.report_export_action.isEnabled()
    assert win.export_menu.actions() == [
        win.export_action, win.image_export_action, win.report_export_action,
    ]
    win._set_roi(2.0, 2.0, 6.0, 5.0)
    win._swap_sources()
    state_before = win.current_analysis_state().copy()
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda *_args, **_kwargs: ("Both", True)
    )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *_args, **_kwargs: str(tmp_path)
    )
    win.report_export_action.trigger()
    dest = tmp_path / "iqa-report-html-synthetic"
    assert (dest / "index.html").is_file(), win.statusBar().currentMessage()
    assert (dest / "source_A_roi.png").is_file()
    assert (dest / "selected_map_full.png").is_file()
    assert not (dest / "source_B_roi.png").exists()
    doc = (dest / "index.html").read_text(encoding="utf-8")
    assert "Source A" in doc
    assert "GRID-derived" in doc
    meta = json.loads((dest / "export_info.json").read_text(encoding="utf-8"))
    assert meta["regions"]["roi"]["xywh_px"] == [2, 2, 6, 5]
    assert win.current_analysis_state() == state_before
    win.report_export_action.trigger()
    assert "destination exists" in win.statusBar().currentMessage()
    win.close()
    win._shutdown_spatial_worker()


def test_html_cancel_and_map_only_without_source(
    qtbot: object, monkeypatch: object, tmp_path: Path
) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(_result())
    win.show()
    assert win.report_export_action.isEnabled()
    win._set_roi(1.0, 1.0, 5.0, 4.0)
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda *_args, **_kwargs: ("Active ROI", False)
    )
    win.report_export_action.trigger()
    assert not list(tmp_path.glob("iqa-report-*"))
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda *_args, **_kwargs: ("Active ROI", True)
    )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *_args, **_kwargs: str(tmp_path)
    )
    win.report_export_action.trigger()
    dest = tmp_path / "iqa-report-html-synthetic"
    assert (dest / "selected_map_roi.png").is_file(), win.statusBar().currentMessage()
    assert not (dest / "source_A_roi.png").exists()
    assert (dest / "index.html").is_file()
    win.close()
    win._shutdown_spatial_worker()
