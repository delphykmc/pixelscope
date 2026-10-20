"""Combined handoff requests 1+3: title, roles, reference tint and linked views.

Only these two PRs are present. Quality policy and fixed hover widgets belong
to separately reviewed later integrations; their contracts are not guessed here.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay, SpatialMap
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow
from pixelscope_enterprise.iqa.visual_export import write_visual_pngs


def _write_source(path: Path, rgb: tuple[int, int, int]) -> None:
    image = QImage(128, 128, QImage.Format.Format_RGB32)
    image.fill(QColor(*rgb))
    assert image.save(str(path))


def _role_result(tmp_path: Path) -> AnalysisResult:
    a = tmp_path / "ref.png"
    b = tmp_path / "target.png"
    _write_source(a, (17, 33, 65))
    _write_source(b, (111, 127, 201))
    spatial = SpatialMap(
        values=np.array([[3.0, 0.0], [-2.0, 7.0]]),
        valid_mask=np.array([[True, True], [True, False]]),
        image_width=128,
        image_height=128,
        block_width=64,
        block_height=64,
    )
    metric = AttributeDisplay(
        "detail",
        "Detail",
        "dB",
        "Detail",
        1.5,
        "available",
        True,
        5.0,
        spatial,
        chart_axis_range=5.0,
        summary_signal_gate=True,
    )
    return AnalysisResult(
        "integrated-pair",
        128,
        128,
        "ref.png",
        "target.png",
        (metric,),
        source_a=a,
        source_b=b,
        source_a_role="Reference",
        source_b_role="Target",
    )


def test_roles_and_reference_tint_keep_hover_science_and_exports(
    qtbot: object, tmp_path: Path
) -> None:
    result = _role_result(tmp_path)
    attr = result.attributes[0]
    assert attr.spatial is not None
    values_before = attr.spatial.values.copy()
    mask_before = attr.spatial.valid_mask.copy()
    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    hover: list[tuple[str, str, str, str]] = []
    window.hover_readout_changed.connect(lambda *fields: hover.append(fields))
    window.present_result(result)
    window.show()
    qtbot.waitUntil(lambda: window._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]

    assert window.windowTitle() == "IQA Analysis — Reference: ref.png vs Target: target.png"
    assert window._pane_labels[0].text().startswith("REFERENCE")
    assert window._pane_labels[1].text().startswith("TARGET")
    assert "Reference: ref.png" in window.pair_summary.text()
    assert window.map_reference_action.isEnabled()
    assert not window.map_reference_action.isChecked()
    assert window._map_reference_item is None

    window._set_roi(0, 0, 64, 64)
    roi_before = window.current_roi
    stats_before = window.roi_label.text()
    state_before = window.current_analysis_state()
    state = window._state()
    assert state is not None
    images = (QImage(str(result.source_a)), QImage(str(result.source_b)))
    export_options = dict(
        scope="both",
        roi=roi_before,
        display_range=window._display_range(attr, state),
        display_gain=state.display_gain,
    )
    before = write_visual_pngs(
        result,
        attr,
        images,
        tmp_path / "export-before",
        **export_options,  # type: ignore[arg-type]
    )

    window.map_reference_action.setChecked(True)
    assert window._map_reference_item is not None
    assert window._map_reference_item.isVisible()
    underlay = window._map_reference_item.pixmap().toImage()
    pixel = underlay.pixelColor(16, 16)
    assert pixel.red() == pixel.green() == pixel.blue()
    assert window._map_item is not None
    tinted = window._map_item.pixmap().toImage()
    assert 0 < tinted.pixelColor(0, 0).alpha() < 255
    assert tinted.pixelColor(1, 0).alpha() == 0  # signed zero reveals source A
    assert tinted.pixelColor(1, 1).alpha() == 0  # invalid mask reveals source A

    for view in window._views:
        position = view.mapFromScene(QPointF(16.5, 16.5))
        assert view.viewport().rect().contains(position)
        qtbot.mouseMove(view.viewport(), pos=position)  # type: ignore[attr-defined]
        assert hover[-1] == (
            "Pixel (16, 16)",
            "Reference RGB8: 17, 33, 65",
            "Target RGB8: 111, 127, 201",
            "Detail Map [0, 0]: +3.0000 dB",
        )
        assert len(window._guide_items) == 3
        assert all(v.isVisible() and h.isVisible() for v, h in window._guide_items)

    window._show_hover_pixel(80, 16)
    assert hover[-1][3] == "Detail Map [0, 1]: +0.0000 dB"
    window._show_hover_pixel(80, 80)
    assert hover[-1][3] == "Detail Map [1, 1]: invalid"
    window.swap_sources_action.trigger()
    assert window.windowTitle() == "IQA Analysis — Reference: ref.png vs Target: target.png"
    assert window._map_reference_item.isVisible()
    assert window.current_roi == roi_before
    assert window.roi_label.text() == stats_before
    assert window.current_analysis_state() == state_before
    np.testing.assert_array_equal(attr.spatial.values, values_before)
    np.testing.assert_array_equal(attr.spatial.valid_mask, mask_before)

    after = write_visual_pngs(
        result,
        attr,
        images,
        tmp_path / "export-after",
        **export_options,  # type: ignore[arg-type]
    )
    names = sorted(path.name for path in before.iterdir())
    assert names == sorted(path.name for path in after.iterdir())
    assert all((before / name).read_bytes() == (after / name).read_bytes() for name in names)
    window.close()


def test_missing_source_label_uses_result_id_without_losing_role_or_rgb(
    qtbot: object, tmp_path: Path
) -> None:
    original = _role_result(tmp_path)
    missing_b = replace(original, result_id="missing-target", source_b_label="", source_b=None)
    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    hover: list[tuple[str, str, str, str]] = []
    window.hover_readout_changed.connect(lambda *fields: hover.append(fields))
    window.present_result(missing_b)
    assert window.windowTitle() == "IQA Analysis — missing-target"
    assert window._pane_labels[0].text().startswith("REFERENCE")
    assert window._pane_labels[1].text().startswith("TARGET")
    assert window.map_reference_action.isEnabled()  # source A still exists
    window.map_reference_action.setChecked(True)
    window._show_hover_pixel(16, 16)
    assert hover[-1][1] == "Reference RGB8: 17, 33, 65"
    assert hover[-1][2] == "Target RGB: unavailable"

    partial = replace(original, result_id="missing-reference-label", source_a_label=" ")
    window.present_result(partial)
    assert window.windowTitle() == "IQA Analysis — missing-reference-label"
    assert window._pane_labels[0].text().startswith("REFERENCE")
    assert window._map_reference_item is not None
    assert window._map_reference_item.isVisible()
    window._show_hover_pixel(16, 16)
    assert hover[-1][2] == "Target RGB8: 111, 127, 201"
    window.close()


def test_tinted_map_preserves_linked_center_with_unequal_view_widths(
    qtbot: object, tmp_path: Path
) -> None:
    window = AnalysisWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.present_result(_role_result(tmp_path))
    window.show()
    qtbot.waitUntil(lambda: window._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]
    window.map_reference_action.setChecked(True)
    for view in window._views:
        view.apply_navigation(2.0, 63.25, 70.75)
    signals: list[tuple[float, float, float]] = []
    for view in window._views:
        view.navigation_changed.connect(lambda *values: signals.append(values))
    for _ in range(6):
        window._image_split.setSizes([230, 360, 250])
        window.resize(1530, 850)
        qtbot.wait(5)  # type: ignore[attr-defined]
        window._image_split.setSizes([350, 220, 270])
        window.resize(1380, 780)
        qtbot.wait(5)  # type: ignore[attr-defined]
    assert signals == []
    assert all(view._navigation_center == QPointF(63.25, 70.75) for view in window._views)
    assert window._map_reference_item is not None
    assert window._map_reference_item.isVisible()
    window.close()
