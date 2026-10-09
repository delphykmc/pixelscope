"""UX-2C Qt-native bottom dock, stitched source crops and scan lifecycle gates."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QDockWidget, QMainWindow

from pixelscope_enterprise.iqa.analysis_window import AnalysisWindow, AnalysisWindowManager
from pixelscope_enterprise.iqa.demo import make_synthetic_result


def _image(path: Path, color: QColor) -> None:
    picture = QImage(3840, 2160, QImage.Format.Format_RGB32)
    picture.fill(color)
    assert picture.save(str(path))


def _loaded_window(qtbot: object, tmp_path: Path) -> AnalysisWindow:
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _image(a, QColor(190, 70, 60))
    _image(b, QColor(70, 95, 190))
    from dataclasses import replace

    result = replace(make_synthetic_result("ux2c-rgb"), source_a=a, source_b=b)
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(result)
    win.show()
    win.spatial_dock.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed is not None and win._fit_pending_result_id is None,
        timeout=5000,
    )
    return win


def test_spatial_dock_owned_only_by_iqa_window_and_toggles(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    assert isinstance(win, QMainWindow)
    assert isinstance(win.spatial_dock, QDockWidget)
    assert win.spatial_dock.parent() is win
    assert win.dockWidgetArea(win.spatial_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
    assert win.spatial_dock.objectName() == "enterpriseIqaSpatialCandidatesDock"
    assert win.spatial_dock.features() & QDockWidget.DockWidgetFeature.DockWidgetFloatable
    assert win.spatial_dock.toggleViewAction() in win.menuBar().actions()[1].menu().actions()
    assert [win.spatial_panel.stride_selector.itemData(i) for i in range(3)] == [
        64, 128, 256
    ]
    assert win.spatial_panel.stride_selector.currentData() == 128
    assert not any(card.isEnabled() for card in win.spatial_panel.buttons)
    win.close()
    win._shutdown_spatial_worker()


def test_spatial_cards_pixel_aligned_native_crops_and_focus(
    qtbot: object, tmp_path: Path
) -> None:
    win = _loaded_window(qtbot, tmp_path)
    assert len(win.spatial_panel.buttons) == 3
    assert all(button.isEnabled() for button in win.spatial_panel.buttons)
    assert win.spatial_panel.previews[0][0].pixmap() is not None
    assert win.spatial_panel.previews[0][1].pixmap() is not None
    original = tuple(view.scene() for view in win._views)
    key = win._spatial_key()
    assert key is not None
    candidate = win._spatial_cache[key][0]
    assert candidate.width == candidate.height == 512
    win.spatial_panel.buttons[0].click()
    assert win.current_roi == candidate.roi
    assert win.spatial_panel.buttons[0].isChecked()
    assert tuple(view.scene() for view in win._views) == original
    assert win.current_analysis_state()["viewport"]["center_x"] == (
        candidate.x + candidate.width / 2
    )

    win.hotspot_overlay_action.setChecked(True)
    assert any(rect.isVisible() for rect, _ in win._candidate_overlay_items[0])
    win.hotspot_overlay_action.setChecked(False)
    assert not any(rect.isVisible() for rect, _ in win._candidate_overlay_items[0])

    win.spatial_panel.stride_selector.setCurrentIndex(0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed is not None and win._spatial_displayed[2] == 64,
        timeout=5000,
    )
    assert win.current_roi == candidate.roi
    assert tuple(view.scene() for view in win._views) == original
    win.close()
    win._shutdown_spatial_worker()


def test_spatial_dock_without_source_still_shows_grid_provenance(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(make_synthetic_result("ux2c-no-rgb"))
    win.show()
    win.spatial_dock.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed is not None, timeout=5000
    )
    assert win.spatial_panel.buttons[0].isEnabled()
    assert "GRID mean" in win.spatial_panel.details[0].text()
    assert win.spatial_panel.previews[0][0].pixmap() is None
    assert "unavailable" in win.spatial_panel.previews[0][0].text()
    win.hotspot_overlay_action.setChecked(True)
    assert not any(rect.isVisible() for rect, _ in win._candidate_overlay_items[0])
    assert not any(rect.isVisible() for rect, _ in win._candidate_overlay_items[1])
    assert any(rect.isVisible() for rect, _ in win._candidate_overlay_items[2])
    win.close()
    win._shutdown_spatial_worker()


def test_spatial_dock_result_switch_and_close_reopen(qtbot: object) -> None:
    manager = AnalysisWindowManager()
    win = manager.show(make_synthetic_result("ux2c-first"))
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.spatial_dock.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed is not None, timeout=5000
    )
    first_key = win._spatial_displayed
    win.present_result(make_synthetic_result("ux2c-second"))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed is not None
        and win._spatial_displayed[0] == "ux2c-second",
        timeout=5000,
    )
    assert win._spatial_displayed != first_key
    win.close()
    manager.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed is not None, timeout=5000
    )
    manager.shutdown()
