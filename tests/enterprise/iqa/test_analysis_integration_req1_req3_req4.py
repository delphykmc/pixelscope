"""Combined requests 1+3+4: role-aware captions, hotspot states and neutral tint."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from pixelscope_enterprise.iqa.analysis_model import (
    NEUTRAL_PRESENTATION_RGB,
    SpatialMap,
    colorize_spatial_rgba,
    colorize_spatial_tint_rgba,
)
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow
from pixelscope_enterprise.iqa.demo import make_synthetic_result
from pixelscope_enterprise.iqa.spatial_dock import NO_CANDIDATE_TEXT, StitchedRoiCanvas


def test_role_aware_long_caption_swap_keeps_slots_and_resize_center(qtbot: object) -> None:
    filename = "reference_" + "long-scene-variant_" * 25 + ".png"
    result = replace(
        make_synthetic_result("req1-3-4-long-caption"),
        source_a_label=filename,
        source_b_label="target.png",
        source_a_role="Reference",
        source_b_role="Target",
    )
    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.resize(1440, 800)
    window.present_result(result)
    window.show()
    qtbot.waitUntil(lambda: window._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]
    splitter = window._image_split
    splitter.setSizes([250, 390, 280])
    QApplication.processEvents()
    slots = splitter.sizes()
    caption = window._pane_labels[0]
    full_text = f"REFERENCE  ·  {filename}"
    assert caption.toolTip() == full_text
    assert "…" in caption.text()

    for view in window._views:
        view.apply_navigation(2.0, 1024.25, 768.75)
    window._sync_views(window._views[0], 2.0, 1024.25, 768.75)
    navigation_events: list[tuple[float, float, float]] = []
    for view in window._views:
        view.navigation_changed.connect(lambda *values: navigation_events.append(values))
    for _ in range(4):
        window.swap_sources_action.trigger()
        QApplication.processEvents()
        assert all(abs(now - old) <= 2 for now, old in zip(splitter.sizes(), slots, strict=True))
        assert caption.toolTip() == full_text
        assert "…" in caption.text()

        window.resize(1530, 850)
        qtbot.wait(5)  # type: ignore[attr-defined]
        window.resize(1440, 800)
        qtbot.wait(5)  # type: ignore[attr-defined]
    assert navigation_events == []
    assert all(view._navigation_center == QPointF(1024.25, 768.75) for view in window._views)
    window.close()


def test_role_changes_preserve_hotspot_candidate_vs_source_unavailable(qtbot: object) -> None:
    canvas = StitchedRoiCanvas()
    qtbot.addWidget(canvas)  # type: ignore[attr-defined]
    canvas.set_source_roles("Reference", "Target")
    assert not canvas._has_candidate
    assert canvas.toolTip() == NO_CANDIDATE_TEXT

    canvas.set_patches(None, None, (64, 64))
    assert canvas._has_candidate
    assert "Reference left | Target right" in canvas.toolTip()
    canvas.set_source_roles("Base", "Candidate")
    assert canvas._has_candidate
    assert "Base left | Candidate right" in canvas.toolTip()

    canvas.clear_candidate()
    canvas.set_source_roles("Reference", "Target")
    assert not canvas._has_candidate
    assert canvas.toolTip() == NO_CANDIDATE_TEXT


def test_dark_neutral_palette_survives_reference_tint_without_changing_data() -> None:
    result = make_synthetic_result("req1-3-4-neutral")
    grid = SpatialMap(
        values=np.array([[10.0, 0.0], [-10.0, 10.0]]),
        valid_mask=np.array([[True, True], [True, False]]),
        image_width=128,
        image_height=128,
        block_width=64,
        block_height=64,
    )
    attr = replace(result.attributes[10], spatial=grid, quality_oriented=False)
    values_before = grid.values.copy()
    mask_before = grid.valid_mask.copy()

    normal = colorize_spatial_rgba(attr, 10.0)
    tinted = colorize_spatial_tint_rgba(attr, 10.0)
    assert normal is not None and tinted is not None
    assert tuple(normal[0, 0, :3]) == NEUTRAL_PRESENTATION_RGB
    assert tuple(normal[1, 0, :3]) == NEUTRAL_PRESENTATION_RGB
    np.testing.assert_array_equal(tinted[..., :3], normal[..., :3])
    assert tinted[0, 0, 3] == 176
    assert tinted[1, 0, 3] == 176
    assert tinted[0, 1, 3] == 0  # signed zero exposes the reference image
    assert tinted[1, 1, 3] == 0  # invalid mask exposes the reference image
    np.testing.assert_array_equal(grid.values, values_before)
    np.testing.assert_array_equal(grid.valid_mask, mask_before)
