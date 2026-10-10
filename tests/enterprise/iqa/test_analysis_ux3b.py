"""UX-3B native Qt: discoverable functional PNG action, ROI and cancel paths."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QFileDialog, QInputDialog

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay, SpatialMap
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow


def _result(rgb: Path | None) -> AnalysisResult:
    grid = SpatialMap(
        values=np.array([[1.0, -1.0], [0.0, 3.0]]),
        valid_mask=np.array([[True, False], [True, True]]),
        image_width=16,
        image_height=12,
        block_width=8.0,
        block_height=6.0,
    )
    attr = AttributeDisplay(
        attribute_id="signed",
        label="Synthetic signed",
        unit="delta",
        group="synthetic",
        official_value=0.5,
        official_availability="available",
        quality_oriented=False,
        fixed_range=4.0,
        spatial=grid,
        chart_axis_range=4.0,
    )
    return AnalysisResult(
        result_id="ux3b-synthetic",
        image_width=16,
        image_height=12,
        source_a_label="A",
        source_b_label="B",
        attributes=(attr,),
        source_a=rgb,
    )


def _image(path: Path) -> None:
    image = QImage(16, 12, QImage.Format.Format_RGB32)
    image.fill(QColor(15, 100, 190))
    assert image.save(str(path), "PNG")


def test_png_action_outputs_full_and_roi_after_swap(
    qtbot: object, monkeypatch: object, tmp_path: Path
) -> None:
    image_path = tmp_path / "a.png"
    _image(image_path)
    result = _result(image_path)
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(result)
    win.show()
    assert win.image_export_action.isEnabled()
    assert win.export_action.isEnabled()
    assert not win.open_action.isEnabled() and not win.save_action.isEnabled()
    assert win.export_menu.actions() == [win.export_action, win.image_export_action]
    win._set_roi(3.0, 2.0, 5.0, 4.0)
    win._swap_sources()
    before = win.current_analysis_state().copy()
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QInputDialog, "getItem",
        lambda *_args, **_kwargs: ("Both", True),
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QFileDialog, "getExistingDirectory",
        lambda *_args, **_kwargs: str(tmp_path),
    )
    win.image_export_action.trigger()
    dest = tmp_path / "iqa-images-ux3b-synthetic"
    assert (dest / "source_A_full.png").is_file()
    assert (dest / "source_A_roi.png").is_file()
    assert (dest / "selected_map_full.png").is_file()
    assert (dest / "selected_map_roi.png").is_file()
    assert not (dest / "source_B_full.png").exists()
    image = QImage(str(dest / "source_A_roi.png"))
    assert (image.width(), image.height()) == (5, 4)
    info = json.loads((dest / "export_info.json").read_text(encoding="utf-8"))
    assert info["source_a_label"] == "A" and info["source_b_label"] == "B"
    assert info["requested_scope"] == "both"
    assert info["regions"]["roi"]["xywh_px"] == [3, 2, 5, 4]
    assert win.current_analysis_state() == before
    assert "PNG images" in win.statusBar().currentMessage()
    win.close()
    win._shutdown_spatial_worker()


def test_cancel_and_collision_are_non_destructive(
    qtbot: object, monkeypatch: object, tmp_path: Path
) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    result = _result(None)  # No A or B; selected grid alone is exportable.
    win.present_result(result)
    win.show()
    assert win.image_export_action.isEnabled()
    win._set_roi(1.0, 1.0, 4.0, 4.0)
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QInputDialog, "getItem",
        lambda *_args, **_kwargs: ("Both", False),
    )
    win.image_export_action.trigger()
    assert not list(tmp_path.glob("iqa-images-*"))
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QInputDialog, "getItem",
        lambda *_args, **_kwargs: ("Active ROI", True),
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QFileDialog, "getExistingDirectory",
        lambda *_args, **_kwargs: str(tmp_path),
    )
    win.image_export_action.trigger()
    dest = tmp_path / "iqa-images-ux3b-synthetic"
    assert (dest / "selected_map_roi.png").exists()
    assert not (dest / "source_A_roi.png").exists()
    info_before = (dest / "export_info.json").read_bytes()
    win.image_export_action.trigger()
    assert "destination already exists" in win.statusBar().currentMessage()
    assert (dest / "export_info.json").read_bytes() == info_before
    win.close()
    win._shutdown_spatial_worker()
