"""Product UX-1 gates: chart semantics and cheap Map-only repaint."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QGraphicsPixmapItem, QWidget

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, official_chart_fraction
from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow
from pixelscope_enterprise.iqa.attribute_chart import (
    ATTRIBUTE_ROLE,
    DISPLAY_RANGE_ROLE,
    RelativeDifferenceDelegate,
)
from pixelscope_enterprise.iqa.demo import make_synthetic_result


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
    assert chart.rowCount() == 12
    assert chart.columnCount() == 2
    assert isinstance(chart.itemDelegateForColumn(1), RelativeDifferenceDelegate)
    assert win.pair_summary.text().startswith("A:")
    assert win.fit_button.isEnabled()
    assert "Shift+drag" in win.roi_hint.text()
    assert [chart.item(row, 0).data(ATTRIBUTE_ROLE).attribute_id for row in range(12)] == [
        a.attribute_id for a in result.attributes
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
    chart.selectRow(10)
    assert not result.attributes[10].quality_oriented
    assert "NO quality winner" in win.clamp_label.text()
    chart.selectRow(11)
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
        win.attribute_table.selectRow(row)
        if win.range_editor.isEnabled():
            win.range_editor.setValue(2.5)
            win.range_editor.setValue(3.5)
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
        win.attribute_table.selectRow(i)
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
    assert win._state().ranges["synthetic_04"] == 10.0  # type: ignore[union-attr]
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
    panes = win._pane_wrappers
    splitter = win._image_split
    assert [splitter.widget(i) for i in range(3)] == [panes[0], panes[2], panes[1]]
    assert win.swap_sources_action.shortcut().toString() == "Alt+X"
    scenes = [view.scene() for view in win._views]
    win._set_roi(100.2, 400.3, 511.4, 511.4)
    assert win.current_roi == (100, 400, 512, 512)
    win.swap_sources_action.trigger()
    assert [splitter.widget(i) for i in range(3)] == [panes[1], panes[2], panes[0]]
    assert win.current_roi == (100, 400, 512, 512)
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
    assert all(win.attribute_table.rowHeight(i) == 36 for i in range(12))
    assert win.findChild(QWidget, "enterpriseIqaInspectorDetails") is not None
    assert win.findChild(QWidget, "enterpriseIqaRoiCard") is not None
    assert win.findChild(QWidget, "enterpriseIqaMapCard") is not None
    assert win.findChild(QWidget, "enterpriseIqaOfficialCard") is not None
    assert win._views[0].scene().backgroundBrush().color().name() == TOKENS.workspace_background
    assert "B better" in win.findChild(type(win.roi_hint), "enterpriseIqaChartHelp").text()
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
