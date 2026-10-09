"""Product UX-1 gates: chart semantics and cheap Map-only repaint."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QWidget

from pixelscope_enterprise.iqa.analysis_model import (
    AnalysisResult,
    official_chart_fraction,
    spatial_display_half_range,
)
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow
from pixelscope_enterprise.iqa.attribute_chart import (
    ATTRIBUTE_ROLE,
    DISPLAY_RANGE_ROLE,
    RelativeDifferenceDelegate,
)
from pixelscope_enterprise.iqa.demo import make_synthetic_result


def _select_attribute(win: AnalysisWindow, global_index: int) -> None:
    """Select an attribute by supplier index across unit-grouped Qt tables."""

    result = win._results[win.active_result_id]
    target = result.attributes[global_index]
    table = win._group_tables[target.unit]
    row = [attr.attribute_id for attr in result.attributes if attr.unit == target.unit].index(
        target.attribute_id
    )
    table.selectRow(row)


def test_ux1_chart_uses_official_axis_and_preserves_supplier_order(qtbot: object) -> None:
    result = make_synthetic_result("ux1-first-insight")
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(result)
    win.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._fit_pending_result_id is None, timeout=3000
    )
    chart = win.attribute_table
    assert chart.rowCount() == 10
    assert win._group_tables["delta"].rowCount() == 2
    assert set(win._range_editors) == {"dB", "delta"}
    assert chart.columnCount() == 2
    assert isinstance(chart.itemDelegateForColumn(1), RelativeDifferenceDelegate)
    assert win.pair_summary.text().startswith("A:")
    assert win.fit_button.isEnabled()
    assert "Shift+drag" in win.roi_hint.text()
    assert [chart.item(row, 0).data(ATTRIBUTE_ROLE).attribute_id for row in range(10)] == [
        a.attribute_id for a in result.attributes if a.unit == "dB"
    ]
    assert chart.item(0, 1).data(ATTRIBUTE_ROLE).fixed_range == 6.0
    assert chart.item(0, 1).data(ATTRIBUTE_ROLE).chart_axis_range == 4.0
    assert result.attributes[0].spatial is None
    assert result.attributes[0].official_value is not None
    assert win._state().attribute_id == "synthetic_02"  # type: ignore[union-attr]
    assert win._map_item.isVisible()  # type: ignore[union-attr]
    chart.selectRow(0)  # official-only entry remains selectable
    assert not win._map_item.isVisible()  # type: ignore[union-attr]

    # Missing official / valid Map is not rendered as a zero bar.
    chart.selectRow(1)
    assert result.attributes[1].official_value is None
    assert result.attributes[1].spatial is not None
    assert win._map_item.isVisible()  # type: ignore[union-attr]
    chart.setCurrentCell(2, 0)
    assert result.attributes[2].official_value == 0.0
    chart.setFocus()
    qtbot.keyClick(chart, Qt.Key.Key_Down)  # type: ignore[attr-defined]
    assert win._state().attribute_id == "synthetic_03"  # type: ignore[union-attr]
    _select_attribute(win, 10)
    assert not result.attributes[10].quality_oriented
    assert "NO quality winner" in win.clamp_label.text()
    _select_attribute(win, 11)
    assert "not zero" in win.official_label.text()
    assert "Map missing" in win.clamp_label.text()
    assert not win._map_item.isVisible()  # type: ignore[union-attr]
    win.close()


def test_ux1_switches_and_range_edits_never_recreate_scenes(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(make_synthetic_result("ux1-preserve"))
    win.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._fit_pending_result_id is None, timeout=3000
    )
    win._set_roi(800, 450, 512, 512)
    roi = win.current_roi
    state = win.current_analysis_state()["viewport"]
    scenes = [v.scene() for v in win._views]
    overlays = list(win._roi_items)
    map_item = win._map_item
    placeholder = win._map_placeholder

    # Repeated switching and spinbox ticks exercise the operator's hot path.
    for row in (1, 2, 4, 5, 10, 11, 3, 7, 0, 1, 5):
        _select_attribute(win, row)
        editor = win._range_editors[win._attribute().unit]
        if editor.isEnabled():
            editor.setValue(2.5)
            editor.setValue(3.5)
        assert all(v.scene() is sc for v, sc in zip(win._views, scenes, strict=True))
        assert all(a is b for a, b in zip(win._roi_items, overlays, strict=True))
        assert win._map_item is map_item
        assert win._map_placeholder is placeholder
        assert win.current_roi == roi
        assert win.current_analysis_state()["viewport"] == state
    # User explicitly invokes Fit; only then navigation is reset.
    win.fit_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._fit_pending_result_id is None, timeout=3000
    )
    assert all(v.scene() is sc for v, sc in zip(win._views, scenes, strict=True))
    win.close()


def test_ux1_4k_rgb_source_preservation_and_nearest_grid(qtbot: object, tmp_path: Path) -> None:
    image_path = tmp_path / "public-safe-4k-flat.png"
    image = QImage(3840, 2160, QImage.Format.Format_RGB32)
    image.fill(QColor(120, 135, 145))
    assert image.save(str(image_path))
    fixture = make_synthetic_result("ux1-4k-rgb")
    result = AnalysisResult(
        fixture.result_id,
        fixture.image_width,
        fixture.image_height,
        fixture.source_a_label,
        fixture.source_b_label,
        fixture.attributes,
        source_a=image_path,
        source_b=image_path,
    )
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.resize(1920, 1080)
    win.present_result(result)
    win.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._fit_pending_result_id is None, timeout=5000
    )
    before = [v.scene() for v in win._views]
    win._set_roi(1000, 500, 512, 512)
    for i in range(12):
        _select_attribute(win, i)
    assert all(v.scene() is s for v, s in zip(win._views, before, strict=True))
    assert win._roi_items[0].isVisible()
    assert win._roi_items[1].isVisible()
    assert not win._views[2].renderHints() & QPainter.RenderHint.SmoothPixmapTransform
    assert isinstance(win._map_item, QGraphicsPixmapItem)
    assert win._map_item.transformationMode() == Qt.TransformationMode.FastTransformation
    assert win.current_roi == (1000, 500, 512, 512)
    # Capture screenshot in native Windows validation without committing pixels.
    screenshot = win.grab().toImage()
    assert screenshot.width() > 500 and screenshot.height() > 400
    win.close()


def test_ux1_shared_display_range_restores_clipped_bar_and_map(qtbot: object) -> None:
    fixture = make_synthetic_result("ux1-shared-display")
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(fixture)
    win.attribute_table.selectRow(4)  # verified +7 dB, originally clipped at ±4
    attribute = fixture.attributes[4]
    assert win.range_editor.value() == 4.0
    assert official_chart_fraction(attribute, win.range_editor.value()) == 1.0
    assert "clipped" not in win.official_label.text().lower()
    assert "Clamped:" in win.clamp_label.text()
    before = win._map_item.pixmap().toImage().pixelColor(12, 5)  # type: ignore[union-attr]
    scenes = [view.scene() for view in win._views]

    win.range_editor.setValue(10.0)
    assert win.range_editor.value() == 10.0
    assert official_chart_fraction(attribute, win.range_editor.value()) == 0.7
    assert win.attribute_table.item(4, 1).data(DISPLAY_RANGE_ROLE) == 10.0
    assert win._state().ranges["dB"] == 10.0  # type: ignore[union-attr]
    after = win._map_item.pixmap().toImage().pixelColor(12, 5)  # type: ignore[union-attr]
    assert before != after
    assert all(view.scene() is scene for view, scene in zip(win._views, scenes, strict=True))
    assert attribute.official_value == 7.0
    assert attribute.chart_axis_range == 4.0  # the immutable source default
    assert attribute.fixed_range == 6.0  # independent immutable map fallback
    win.close()


def test_ux1_a_map_b_swap_changes_placement_not_scientific_identity(qtbot: object) -> None:
    fixture = make_synthetic_result("ux1-swappable")
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(fixture)
    win.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._fit_pending_result_id is None, timeout=3000
    )
    viewport_before = win.current_analysis_state()["viewport"]
    panes = win._pane_wrappers
    splitter = win._image_split
    assert [splitter.widget(i) for i in range(3)] == [panes[0], panes[2], panes[1]]
    assert [key.toString() for key in win.swap_sources_action.shortcuts()] == [
        "T",
        "Alt+X",
    ]
    scenes = [view.scene() for view in win._views]
    win._set_roi(100.2, 400.3, 511.4, 511.4)
    assert win.current_roi == (100, 400, 512, 512)
    win.swap_sources_action.trigger()
    assert [splitter.widget(i) for i in range(3)] == [panes[1], panes[2], panes[0]]
    assert win.current_roi == (100, 400, 512, 512)
    assert win.current_analysis_state()["viewport"] == viewport_before
    assert all(view.scene() is scene for view, scene in zip(win._views, scenes, strict=True))
    assert win._views[0].objectName() == "enterpriseIqaViewImageA"
    assert win._views[1].objectName() == "enterpriseIqaViewImageB"
    win.swap_button.click()
    assert [splitter.widget(i) for i in range(3)] == [panes[0], panes[2], panes[1]]
    assert win.active_result_id == fixture.result_id
    win.close()


def test_ux1_visual_rows_and_structured_details(qtbot: object) -> None:
    from pixelscope.ui.design_tokens import TOKENS

    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(make_synthetic_result("ux1-compact"))
    assert all(win.attribute_table.rowHeight(i) == 36 for i in range(10))
    assert all(win._group_tables["delta"].rowHeight(i) == 36 for i in range(2))
    assert win.findChild(QWidget, "enterpriseIqaGroupScroll") is not None
    assert win.findChild(QWidget, "enterpriseIqaInspectorDetails") is not None
    assert win.findChild(QWidget, "enterpriseIqaRoiCard") is not None
    assert win.findChild(QWidget, "enterpriseIqaMapCard") is not None
    assert win.findChild(QWidget, "enterpriseIqaOfficialCard") is not None
    assert win._views[0].scene().backgroundBrush().color().name() == TOKENS.workspace_background
    assert "B better" in win.findChild(type(win.roi_hint), "enterpriseIqaChartHelp").text()
    win.close()


def test_ux1_fhd_inspector_splitter_and_metric_explanations(qtbot: object) -> None:
    """The chart/details share spare screen space and can be resized by drag."""

    from PySide6.QtWidgets import QApplication, QLabel

    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.resize(1600, 800)
    win.present_result(make_synthetic_result("fhd-inspector"))
    win.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win.inspector_splitter.height() > 350 and win._fit_pending_result_id is None,
        timeout=4000,
    )
    splitter = win.inspector_splitter
    initial_height = splitter.height()
    win.resize(1920, 1080)
    QApplication.processEvents()
    assert splitter.height() > initial_height
    assert splitter.orientation() == Qt.Orientation.Vertical
    assert splitter.childrenCollapsible() is False
    assert splitter.widget(0) is win.group_scroll
    assert splitter.widget(1).objectName() == "enterpriseIqaInspectorDetails"
    assert splitter.handleWidth() >= 6
    assert splitter.widget(0).height() >= 140
    assert splitter.widget(1).height() >= 175
    for name, phrase in (
        ("enterpriseIqaOfficialExplanation", "entire image pair"),
        ("enterpriseIqaRoiExplanation", "not an official score"),
        ("enterpriseIqaMapExplanation", "clipped cells"),
    ):
        label = win.findChild(QLabel, name)
        assert label is not None
        assert phrase.lower() in label.text().lower()
        assert label.wordWrap()
    assert "Synthetic attribute" in win.detail_context.text()

    # Splitter resize is independent of selection, ROI and analysis data.
    state = win.current_analysis_state()
    splitter.setSizes([520, 180])
    QApplication.processEvents()
    chart_large = splitter.sizes()
    assert chart_large[0] > chart_large[1]
    splitter.setSizes([180, 520])
    QApplication.processEvents()
    detail_large = splitter.sizes()
    assert detail_large[1] > detail_large[0]
    assert win.current_analysis_state() == state

    # A different result/metric still updates the detail context.
    _select_attribute(win, 10)
    assert "Synthetic attribute 11" in win.detail_context.text()
    assert splitter.widget(0) is win.group_scroll
    win.close()


def test_ux1_qss_braces_and_standalone_swap_shortcut(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    style = win.styleSheet()
    assert style.count("{") == style.count("}")
    assert "font-weight: 700; }" in style
    assert "font-weight: 700; }}" not in style
    assert win.swap_sources_action.shortcutContext() == Qt.ShortcutContext.WindowShortcut
    assert [key.toString() for key in win.swap_sources_action.shortcuts()] == [
        "T",
        "Alt+X",
    ]
    win.present_result(make_synthetic_result("qss-and-t"))
    win.show()
    # QTest sends directly to the widget; WindowShortcut requires an active
    # top-level and a focused descendant. Showing alone does not ensure this.
    win.raise_()
    win.activateWindow()
    QApplication.setActiveWindow(win)
    view = win._views[0]
    view.setFocus()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: QApplication.activeWindow() is win and view.hasFocus(), timeout=3000
    )
    assert not win._sources_swapped
    qtbot.keyClick(view, Qt.Key.Key_T)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: win._sources_swapped, timeout=1000)  # type: ignore[attr-defined]
    # The secondary shortcut must reach the *same* action without a second
    # activation from the primary key.
    qtbot.keyClick(view, Qt.Key.Key_X, Qt.KeyboardModifier.AltModifier)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: not win._sources_swapped, timeout=1000)  # type: ignore[attr-defined]
    # Verify the menu action itself remains a valid explicit UI command.
    win.swap_sources_action.trigger()
    assert win._sources_swapped
    win.close()


def test_ux1_patterned_rgb_demo_has_spatial_landmarks(tmp_path: Path) -> None:
    from pixelscope_enterprise.iqa.demo import create_synthetic_rgb

    a, b = tmp_path / "a.png", tmp_path / "b.png"
    create_synthetic_rgb(a)
    create_synthetic_rgb(b, source_b=True)
    image_a, image_b = QImage(str(a)), QImage(str(b))
    assert image_a.size() == image_b.size()
    assert (image_a.width(), image_a.height()) == (3840, 2160)
    # Geometry grid and gradient make visual pan/zoom test possible; A/B differ.
    assert image_a.pixelColor(40, 40) != image_a.pixelColor(1800, 900)
    assert image_a.pixelColor(40, 40) != image_b.pixelColor(40, 40)


def test_ux1_unit_ranges_and_global_map_gain_isolate_measurement(
    qtbot: object,
) -> None:
    result = make_synthetic_result("unit-gain")
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(result)
    assert list(win._group_tables) == ["dB", "delta"]
    assert win._group_tables["dB"].rowCount() == 10
    assert win._group_tables["delta"].rowCount() == 2
    assert win._range_editors["dB"].value() == 4.0
    assert win._range_editors["delta"].value() == 2.0
    assert win.gain_editor.value() == 1.0

    _select_attribute(win, 4)  # +7 dB official, nonzero signed spatial
    official = result.attributes[4].official_value
    win._set_roi(800, 500, 512, 512)
    original_roi = win.roi_label.text()
    win._range_editors["dB"].setValue(10.0)
    assert official_chart_fraction(result.attributes[4], 10.0) == 0.7
    assert all(
        win._group_tables["dB"].item(i, 1).data(DISPLAY_RANGE_ROLE) == 10.0 for i in range(10)
    )
    assert all(
        win._group_tables["delta"].item(i, 1).data(DISPLAY_RANGE_ROLE) == 2.0 for i in range(2)
    )
    before = win._map_item.pixmap().toImage().pixelColor(12, 5)  # type: ignore[union-attr]
    win.gain_editor.setValue(2.0)
    after = win._map_item.pixmap().toImage().pixelColor(12, 5)  # type: ignore[union-attr]
    assert before != after
    assert spatial_display_half_range(10.0, 2.0) == 5.0
    assert official_chart_fraction(result.attributes[4], 10.0) == 0.7
    assert win._group_tables["dB"].item(4, 1).data(DISPLAY_RANGE_ROLE) == 10.0
    assert result.attributes[4].official_value == official
    assert win.roi_label.text() == original_roi
    assert "gain ×2" in win.clamp_label.text()

    _select_attribute(win, 10)
    win._range_editors["delta"].setValue(3.0)
    assert win._range_editors["dB"].value() == 10.0
    assert "Group ±3 delta" in win.clamp_label.text()
    assert win.gain_editor.value() == 2.0
    state = win.current_analysis_state()
    assert state["ranges"] == {"dB": 10.0, "delta": 3.0}
    assert state["display_gain"] == 2.0
    win.close()

    restored = AnalysisWindow()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    restored.present_result(result, analysis_state=state)
    assert restored._state().attribute_id == "synthetic_10"  # type: ignore[union-attr]
    assert restored._range_editors["dB"].value() == 10.0
    assert restored._range_editors["delta"].value() == 3.0
    assert restored.gain_editor.value() == 2.0
    restored.close()


def test_ux1_saved_legacy_range_migrates_and_unknown_unit_is_dynamic(
    qtbot: object,
) -> None:
    result = make_synthetic_result("legacy-groups")
    extra = replace(
        result.attributes[6],
        attribute_id="third_unit",
        label="Third unit",
        unit="score",
        group="Additional metric family",
        chart_axis_range=2.5,
    )
    result = replace(result, attributes=(*result.attributes, extra))
    legacy: dict[str, object] = {
        "attribute_id": "synthetic_04",
        "roi": None,
        "ranges": {
            "synthetic_00": 5.0,
            "synthetic_04": 7.0,
            "synthetic_10": 2.5,
        },
        "viewport": {"scale": None, "center_x": None, "center_y": None},
    }
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(result, analysis_state=legacy)
    assert list(win._group_tables) == ["dB", "delta", "score"]
    assert win.current_analysis_state()["ranges"] == {"dB": 7.0, "delta": 2.5}
    assert win.current_analysis_state()["display_gain"] == 1.0
    state = win.current_analysis_state()
    state["display_gain"] = 0.7
    with pytest.raises(ValueError, match="display gain"):
        win.present_result(result, analysis_state=state)
    assert win.current_analysis_state()["display_gain"] == 1.0
    win.close()
