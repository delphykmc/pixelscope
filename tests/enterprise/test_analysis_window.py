"""Focus: extension-owned QMainWindow is independent from MainWindow and provider jobs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QWheelEvent
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QGraphicsRectItem

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
        "unchanged",
        128,
        128,
        "Synthetic A",
        "Synthetic B",
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
    # No layout exists pre-show: retain selections but NOT invented navigation.
    assert state["viewport"] == {"scale": None, "center_x": None, "center_y": None}
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


def test_qt_map_pixmap_respects_non_oriented_signed_polarity(qtbot: object) -> None:
    grid = SpatialMap(
        values=np.array([[4.0, -4.0, np.nan]]),
        valid_mask=np.array([[True, True, False]]),
        image_width=192,
        image_height=64,
        block_width=64.0,
        block_height=64.0,
    )
    signed = AttributeDisplay(
        "signed_only",
        "Signed only",
        "delta",
        "signed",
        0.0,
        "available",
        False,
        4.0,
        grid,
    )
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(AnalysisResult("pure-signed-pair", 192, 64, "A", "B", (signed,)))
    assert "NO quality winner" in win.clamp_label.text()
    assert "neutral / no winner inferred" in win.official_label.text()
    scene = win._views[2].scene()
    assert scene is not None
    images = [item for item in scene.items() if isinstance(item, QGraphicsPixmapItem)]
    assert len(images) == 1
    raster = images[0].pixmap().toImage()
    assert raster.pixelColor(0, 0).getRgb() == (181, 72, 193, 255)
    assert raster.pixelColor(1, 0).getRgb() == (35, 145, 148, 255)
    assert raster.pixelColor(2, 0).alpha() == 0
    win.close()


def test_manager_shutdown_is_idempotent_after_multiple_empty_open_cycles(
    qtbot: object,
) -> None:
    for _ in range(4):
        manager = AnalysisWindowManager()
        win = manager.show()
        qtbot.addWidget(win)  # type: ignore[attr-defined]
        win.close()
        assert manager.show() is win
        manager.shutdown()
        manager.shutdown()
        with pytest.raises(RuntimeError, match="shut down"):
            manager.show()


def test_first_fit_uses_visible_4k_layout_and_wheel_dispatch(qtbot: object) -> None:
    from pixelscope_enterprise.iqa.demo import make_synthetic_result

    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    result = make_synthetic_result("4k-visible")
    win.present_result(result)
    assert win.current_analysis_state()["viewport"] == {
        "scale": None,
        "center_x": None,
        "center_y": None,
    }
    win.show()
    qtbot.waitUntil(lambda: win._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]
    view = win._views[0]
    initial = view.transform().m11()
    assert initial > 0.0
    assert win._state().scale == pytest.approx(initial)  # type: ignore[union-attr]

    # A real viewport-targeted Qt wheel event, not a direct private zoom helper.
    midpoint = view.viewport().rect().center()
    wheel = QWheelEvent(
        QPointF(midpoint),
        QPointF(view.viewport().mapToGlobal(midpoint)),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(view.viewport(), wheel)
    assert view.transform().m11() > initial
    assert win._state().scale == pytest.approx(view.transform().m11())  # type: ignore[union-attr]
    for other in win._views[1:]:
        assert other.transform().m11() == pytest.approx(view.transform().m11())
    win.close()


def test_shift_drag_on_real_viewport_selects_and_draws_linked_roi(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(_result("mouse-roi"))
    win.show()
    qtbot.waitUntil(lambda: win._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]

    source = win._views[2]  # Spatial-map viewport also supports Shift+drag.
    a = source.mapFromScene(QPointF(16.0, 16.0))
    b = source.mapFromScene(QPointF(96.0, 96.0))
    assert source.viewport().rect().contains(a)
    assert source.viewport().rect().contains(b)
    qtbot.mousePress(  # type: ignore[attr-defined]
        source.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        pos=a,
    )
    qtbot.mouseMove(source.viewport(), pos=b)  # type: ignore[attr-defined]
    assert source._rubber_band.isVisible()
    qtbot.mouseRelease(  # type: ignore[attr-defined]
        source.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        pos=b,
    )
    assert not source._rubber_band.isVisible()
    roi = win.current_roi
    assert roi is not None
    x, y, width, height = roi
    assert 0 <= x < x + width <= 128
    assert 0 <= y < y + height <= 128
    assert width >= 40 and height >= 40
    assert "GRID-DERIVED ROI" in win.roi_label.text()

    # Original RGB is deliberately absent; only the spatial map is annotated.
    assert [item.isVisible() for item in win._roi_items] == [False, False, True]
    for rect_item in win._roi_items:
        rect = rect_item.rect()
        assert rect.x() == pytest.approx(x)
        assert rect.y() == pytest.approx(y)
        assert rect.width() == pytest.approx(width)
        assert rect.height() == pytest.approx(height)

    win.attribute_table.selectRow(1)
    assert win.current_roi == roi
    assert not any(item.isVisible() for item in win._roi_items)
    win.close()


def test_visible_navigation_round_trip_and_bounded_overscan(qtbot: object) -> None:
    source = AnalysisWindow()
    qtbot.addWidget(source)  # type: ignore[attr-defined]
    result = _result("visible-state")
    source.present_result(result)
    source.show()
    qtbot.waitUntil(lambda: source._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]
    # Source coordinates can extend beyond a tiny image when the viewport is larger.
    scale = source._views[0].transform().m11()
    source._sync_views(source._views[0], scale, -154.6667, -288.0)
    state = source.current_analysis_state()
    source.close()

    target = AnalysisWindow()
    qtbot.addWidget(target)  # type: ignore[attr-defined]
    target.present_result(result, analysis_state=state)
    restored = target.current_analysis_state()["viewport"]
    assert isinstance(restored, dict)
    assert restored["center_x"] == pytest.approx(-154.6667)
    assert restored["center_y"] == pytest.approx(-288.0)
    assert restored["scale"] == pytest.approx(scale)
    bad = dict(state)
    bad["viewport"] = {"scale": scale, "center_x": -1e9, "center_y": 0.0}
    with pytest.raises(ValueError, match="bounded source overscan"):
        target.present_result(result, analysis_state=bad)
    bad["viewport"] = {"scale": float("nan"), "center_x": 0.0, "center_y": 0.0}
    with pytest.raises(ValueError, match="non-finite"):
        target.present_result(result, analysis_state=bad)
    target.close()


def _drag_map_roi(
    qtbot: object, view: object, top_left: tuple[int, int], bottom_right: tuple[int, int]
) -> None:
    a = view.mapFromScene(QPointF(float(top_left[0]), float(top_left[1])))  # type: ignore[attr-defined]
    b = view.mapFromScene(QPointF(float(bottom_right[0]), float(bottom_right[1])))  # type: ignore[attr-defined]
    viewport = view.viewport()  # type: ignore[attr-defined]
    assert viewport.rect().contains(a)
    assert viewport.rect().contains(b)
    qtbot.mousePress(  # type: ignore[attr-defined]
        viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, pos=a
    )
    qtbot.mouseMove(viewport, pos=b)  # type: ignore[attr-defined]
    assert view._rubber_band.isVisible()  # type: ignore[attr-defined]
    qtbot.mouseRelease(  # type: ignore[attr-defined]
        viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, pos=b
    )
    assert not view._rubber_band.isVisible()  # type: ignore[attr-defined]


def _visible_roi_yellow(view: object, x: float, y: float) -> bool:
    """Sample painted viewport pixels, not just GraphicsScene item metadata."""

    point = view.mapFromScene(QPointF(x, y))  # type: ignore[attr-defined]
    viewport = view.viewport()  # type: ignore[attr-defined]
    dpr = viewport.devicePixelRatioF()
    image = viewport.grab().toImage()
    px, py = round(point.x() * dpr), round(point.y() * dpr)
    for iy in range(max(0, py - 4), min(image.height(), py + 5)):
        for ix in range(max(0, px - 4), min(image.width(), px + 5)):
            color = image.pixelColor(ix, iy)
            if color.red() > 235 and 165 <= color.green() <= 232 and color.blue() < 75:
                return True
    return False


def test_repeated_mouse_roi_replaces_actual_viewport_pixels_without_resize(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(_result("repeat-pixels"))
    win.show()
    qtbot.waitUntil(lambda: win._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]
    view = win._views[2]
    scene = view.scene()
    assert scene is not None
    base_items = len(scene.items())
    assert len([i for i in scene.items() if isinstance(i, QGraphicsRectItem)]) == 1
    assert not _visible_roi_yellow(view, 25, 8)

    # Each ROI is disjoint. We inspect painted pixels after release, with no
    # resize or attribute switch that might incidentally cure stale outlines.
    selections = [
        ((8, 8), (43, 43), (25, 8)),
        ((68, 68), (110, 110), (85, 68)),
        ((10, 75), (43, 112), (25, 75)),
    ]
    for index, (start, end, edge) in enumerate(selections):
        _drag_map_roi(qtbot, view, start, end)
        QApplication.processEvents()
        assert _visible_roi_yellow(view, *edge)
        for _, _, previous_edge in selections[:index]:
            assert not _visible_roi_yellow(view, *previous_edge)
        assert len(scene.items()) == base_items
        assert len([i for i in scene.items() if isinstance(i, QGraphicsRectItem)]) == 1
        assert [item.isVisible() for item in win._roi_items] == [False, False, True]

    win.clear_roi_action.trigger()
    QApplication.processEvents()
    assert win.current_roi is None
    assert not view._rubber_band.isVisible()
    assert not any(item.isVisible() for item in win._roi_items)
    assert not win.clear_roi_action.isEnabled()
    assert not win.clear_roi_button.isEnabled()
    for _, _, edge in selections:
        assert not _visible_roi_yellow(view, *edge)
    win.close()


def test_roi_source_panels_only_when_rgb_exists_and_stats_include_pixel_area(
    qtbot: object, tmp_path: Path
) -> None:
    rgb = tmp_path / "synthetic-source.png"
    image = QImage(128, 128, QImage.Format.Format_RGB32)
    image.fill(QColor(200, 200, 200))
    assert image.save(str(rgb))
    original = _result("original")
    mixed = AnalysisResult(
        "mixed-sources",
        128,
        128,
        "Synthetic A",
        "Synthetic B",
        original.attributes,
        source_a=rgb,
        source_b=tmp_path / "missing-b.png",
    )
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(mixed)
    win.show()
    qtbot.waitUntil(lambda: win._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]
    win._set_roi(0, 0, 64, 64)
    assert [i.isVisible() for i in win._roi_items] == [True, False, True]
    assert "(0, 0, 64, 64)" in win.roi_label.text()
    assert "4,096 px²" in win.roi_label.text()
    assert "GRID-DERIVED ROI mean" in win.roi_label.text()
    assert "Grid valid area" in win.roi_label.text()
    assert "NOT official" in win.roi_label.text()

    win.attribute_table.selectRow(1)  # no spatial grid for second metric
    assert win._state().attribute_id == "metric_delta"  # type: ignore[union-attr]
    assert win.attribute_table.selectionModel().selectedRows()[0].row() == 1
    assert [i.isVisible() for i in win._roi_items] == [True, False, False]
    assert "spatial statistics unavailable" in win.roi_label.text()
    win.attribute_table.selectRow(0)
    assert win._state().attribute_id == "metric_db"  # type: ignore[union-attr]
    assert [i.isVisible() for i in win._roi_items] == [True, False, True]
    # Repeat without changing results/ROI to catch a stale currentRow race.
    win.attribute_table.selectRow(1)
    assert win._state().attribute_id == "metric_delta"  # type: ignore[union-attr]
    assert [i.isVisible() for i in win._roi_items] == [True, False, False]
    assert win.current_roi == (0, 0, 64, 64)
    win.attribute_table.selectRow(0)
    assert win._state().attribute_id == "metric_db"  # type: ignore[union-attr]
    assert [i.isVisible() for i in win._roi_items] == [True, False, True]
    win.close()


def test_clear_roi_keyboard_alias_and_per_result_independence(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    first, second = _result("roi-one"), _result("roi-two")
    win.present_result(first)
    win.show()
    qtbot.waitUntil(lambda: win._fit_pending_result_id is None, timeout=3000)  # type: ignore[attr-defined]
    assert not win.clear_roi_action.isEnabled()
    assert [shortcut.toString() for shortcut in win.clear_roi_action.shortcuts()] == [
        "Esc",
        "Shift+Esc",
    ]
    qtbot.keyPress(win.attribute_table, Qt.Key.Key_Shift)  # type: ignore[attr-defined]
    assert all(
        view.viewport().cursor().shape() == Qt.CursorShape.CrossCursor for view in win._views
    )
    qtbot.keyRelease(win.attribute_table, Qt.Key.Key_Shift)  # type: ignore[attr-defined]
    assert all(
        view.viewport().cursor().shape() != Qt.CursorShape.CrossCursor for view in win._views
    )

    win._set_roi(10, 20, 45, 50)
    assert win.clear_roi_action.isEnabled() and win.clear_roi_button.isEnabled()
    win.present_result(second)
    win._set_roi(1, 2, 30, 40)
    win.clear_roi_button.click()
    assert win.current_roi is None
    assert not any(item.isVisible() for item in win._roi_items)
    win.present_result(first)
    assert win.current_roi == (10, 20, 45, 50)
    # Explicit action works regardless of which of the three panes had focus.
    win.clear_roi_action.trigger()
    assert win.current_roi is None
    assert "ROI: none" in win.roi_label.text()
    assert win._states["roi-two"].roi is None
    win.close()
