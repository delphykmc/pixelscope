"""Enterprise post-integration #203: reproduce field feedback on the Handoff seam."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QFileDialog

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    AttributeDisplay,
    SpatialMap,
)
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow, ResultFileType
from pixelscope_enterprise.iqa.insights import rank_top_differences


def _attribute(identifier: str, value: float, *, gate: bool | None = True) -> AttributeDisplay:
    return AttributeDisplay(
        attribute_id=identifier,
        label=identifier,
        unit="dB",
        group="Detail",
        official_value=value,
        official_availability="available",
        quality_oriented=True,
        fixed_range=4.0,
        spatial=SpatialMap(
            np.array([[2.0]], dtype=np.float64),
            np.array([[True]], dtype=np.bool_),
            image_width=64,
            image_height=64,
            block_width=64.0,
            block_height=64.0,
        ),
        chart_axis_range=4.0,
        summary_signal_gate=gate,
        quality_direction="higher_is_better",
    )


def _result(result_id: str = "feedback") -> AnalysisResult:
    return AnalysisResult(
        result_id,
        64,
        64,
        "A",
        "B",
        (_attribute("detail", 2.0),),
    )


def _source(path: Path, gray: int) -> None:
    image = QImage(64, 64, QImage.Format.Format_RGB32)
    image.fill(QColor(gray, gray, gray))
    assert image.save(str(path))


def test_existing_suffixed_destination_does_not_call_injected_writer(
    qtbot: object, monkeypatch: object, tmp_path: Path
) -> None:
    destination = tmp_path / "pair.pxiqa"
    destination.write_bytes(b"existing portable bytes")
    writes: list[Path] = []

    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.install_file_handlers(
        save=lambda _result, _state, path: writes.append(path),
        file_type=ResultFileType("PixelScope IQA result", ".pxiqa"),
    )
    window.present_result(_result())

    # The native dialog only confirmed "pair", whereas the injected writer
    # would receive "pair.pxiqa" after the app adds the suffix.
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_args: (str(tmp_path / "pair"), "PixelScope IQA result (*.pxiqa)"),
    )
    window.save_action.trigger()
    assert not writes
    assert destination.read_bytes() == b"existing portable bytes"
    assert "already exists" in window.statusBar().currentMessage()
    window.close()


def test_final_result_close_disables_roi_clear_and_stale_callback_is_safe(
    qtbot: object,
) -> None:
    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.present_result(_result())
    window._set_roi(0, 0, 16, 16)
    assert window.clear_roi_action.isEnabled()
    assert window.clear_roi_button.isEnabled()
    window.close_result_action.trigger()
    assert window.active_result_id is None
    assert window._roi_items == []
    assert not window.clear_roi_action.isEnabled()
    assert not window.clear_roi_button.isEnabled()
    window._clear_roi()  # A stale external Qt slot call must not raise.
    window._draw_roi(None)
    assert not window.clear_roi_action.isEnabled()
    window.close()


def test_reference_tint_tracks_role_b_and_keeps_semantic_source_after_swap(
    qtbot: object, tmp_path: Path
) -> None:
    a, b = tmp_path / "target.png", tmp_path / "reference.png"
    _source(a, 20)
    _source(b, 210)
    result = replace(
        _result(),
        source_a=a,
        source_b=b,
        source_a_role="Target",
        source_b_role="Reference",
    )
    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.present_result(result)
    assert window.map_reference_action.isEnabled()
    assert "Reference B" in window.map_reference_action.text()
    window.map_reference_action.setChecked(True)
    assert window._map_reference_item is not None
    pixel = window._map_reference_item.pixmap().toImage().pixelColor(4, 4)
    assert pixel.red() > 190  # Underlay is the lighter B, not the darker A.
    window.swap_sources_action.trigger()
    assert "Reference B" in window.map_reference_action.text()
    assert window._map_reference_item is not None
    pixel_after = window._map_reference_item.pixmap().toImage().pixelColor(4, 4)
    assert pixel_after.red() > 190

    no_roles = replace(result, result_id="legacy-no-roles", source_a_role=None, source_b_role=None)
    window.present_result(no_roles)
    assert "Reference A" in window.map_reference_action.text()
    assert window._map_reference_item is not None
    fallback = window._map_reference_item.pixmap().toImage().pixelColor(4, 4)
    assert fallback.red() < 40
    window.close()


def test_quality_top3_filters_untrusted_and_below_threshold_before_ranking(
    qtbot: object,
) -> None:
    attrs = (
        _attribute("untrusted", 100.0, gate=None),
        _attribute("false", -90.0, gate=False),
        _attribute("below", 0.4999),
        _attribute("edge", 0.5),
        _attribute("visible", -2.0),
    )
    result = replace(_result(), attributes=attrs)
    assert [item.attribute_id for item in rank_top_differences(result, quality_policy=True)] == [
        "visible",
        "edge",
    ]
    assert [
        item.attribute_id
        for item in rank_top_differences(result, quality_policy=True, visibility_threshold=2.1)
    ] == []
    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.present_result(result)
    window.set_quality_presentation(True)
    assert window._top3_attribute_ids == ["visible", "edge"]
    assert not window.top3_buttons[2].isEnabled()
    window.set_quality_presentation(True, threshold=2.1)
    assert not any(card.isEnabled() for card in window.top3_buttons)
    window.close()
