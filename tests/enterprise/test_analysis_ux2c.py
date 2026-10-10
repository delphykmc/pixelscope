"""UX-2C Qt-native bottom dock, stitched source crops and scan lifecycle gates."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow

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
    # Persisted user docking is expected: normalize area before testing defaults.
    win.spatial_dock.setFloating(False)
    win.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, win.spatial_dock)
    assert win.dockWidgetArea(win.spatial_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
    assert win.spatial_dock.objectName() == "enterpriseIqaSpatialCandidatesDock"
    assert win.spatial_dock.features() & QDockWidget.DockWidgetFeature.DockWidgetFloatable
    assert win.spatial_dock.toggleViewAction() in win.menuBar().actions()[1].menu().actions()
    assert [win.spatial_panel.stride_selector.itemData(i) for i in range(3)] == [64, 128, 256]
    assert win.spatial_panel.stride_selector.currentData() == 128
    assert not any(card.isEnabled() for card in win.spatial_panel.buttons)
    win.close()
    win._shutdown_spatial_worker()


def test_spatial_cards_pixel_aligned_native_crops_and_focus(qtbot: object, tmp_path: Path) -> None:
    win = _loaded_window(qtbot, tmp_path)
    assert len(win.spatial_panel.buttons) == 3
    assert all(button.isEnabled() for button in win.spatial_panel.buttons)
    stitched = win.spatial_panel.previews[0]
    assert stitched.has_a and stitched.has_b
    assert stitched._a is not None and stitched._b is not None
    assert stitched._a.width() == stitched._b.width() == 512
    assert stitched._a.height() == stitched._b.height() == 512
    assert win.spatial_panel.rank_badges[0].pixmap() is not None
    assert not win.spatial_panel.rank_badges[0].pixmap().isNull()
    assert win.spatial_panel.titles[0].text().startswith("(")
    assert win.spatial_panel.provenance_badge.text() == "GRID"
    assert "LARGEST LOCAL" not in win.spatial_panel.titles[0].text()
    assert win.spatial_panel.impact_bars[0].value() == 100
    assert win.spatial_panel.impact_bars[1].value() <= 100
    assert win.spatial_panel.buttons[0].property("spatialRankTone") == "top"
    assert "#e5857d" in win.spatial_panel.buttons[0].styleSheet()
    assert "QPushButton:checked" in win.spatial_panel.buttons[0].styleSheet()
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
    assert "Δ " in win.spatial_panel.details[0].text()
    assert "GRID-derived" in win.spatial_panel.details[0].toolTip()
    stitched = win.spatial_panel.previews[0]
    assert not stitched.has_a and not stitched.has_b
    assert "source-pixel ROI" in stitched.toolTip()
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
        lambda: win._spatial_displayed is not None and win._spatial_displayed[0] == "ux2c-second",
        timeout=5000,
    )
    assert win._spatial_displayed != first_key
    win.close()
    manager.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed is not None, timeout=5000
    )
    manager.shutdown()


def test_dock_vertical_growth_enlarges_single_stitch_without_resampling(
    qtbot: object, tmp_path: Path
) -> None:
    """No two independent black-padded panes or per-resize pixmap creation."""

    win = _loaded_window(qtbot, tmp_path)
    win.resize(1600, 950)
    QApplication.processEvents()
    win.resizeDocks([win.spatial_dock], [195], Qt.Orientation.Vertical)
    QApplication.processEvents()
    stitched = win.spatial_panel.previews[0]
    before = stitched.fitted_rect()
    assert stitched.has_a and stitched.has_b
    a = stitched._a
    b = stitched._b
    assert a is not None and b is not None
    a_key, b_key = a.cacheKey(), b.cacheKey()

    win.resizeDocks([win.spatial_dock], [345], Qt.Orientation.Vertical)
    QApplication.processEvents()
    after = stitched.fitted_rect()
    assert after.height() > before.height()
    assert after.width() > before.width()
    assert after.width() == pytest.approx(2.0 * after.height(), rel=0.03)
    # Paint the full composite; both sides must meet at one seam with no
    # independent QLabel black gutters or source resampling on resize.
    painted = QImage(stitched.size(), QImage.Format.Format_RGB32)
    stitched.render(painted)
    y = int(after.center().y())
    seam_x = int(after.center().x())
    left_pixel = painted.pixelColor(seam_x - 5, y)
    right_pixel = painted.pixelColor(seam_x + 5, y)
    assert left_pixel.red() > left_pixel.blue()
    assert right_pixel.blue() > right_pixel.red()
    assert stitched._a is not None and stitched._a.cacheKey() == a_key
    assert stitched._b is not None and stitched._b.cacheKey() == b_key
    assert "A/B ROI" in win.spatial_panel.status_label.text()
    win.close()
    win._shutdown_spatial_worker()


def test_startup_bottom_dock_does_not_collapse_fhd_inspector(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.resize(1600, 800)
    win.present_result(make_synthetic_result("ux2c-fhd-inspector"))
    win.show()
    win.spatial_dock.show()  # explicit despite persisted user visibility state
    # This test checks dock/Inspector layout, not asynchronous source-image fit.
    # At smaller screen heights a requested 1600x800 window can be clamped by
    # the OS; an arbitrary 260px tab threshold is not a reliable acceptance
    # condition. Require a genuinely visible, usable chart viewport instead.
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: (
            win.spatial_dock.isVisible()
            and win.group_scroll.isVisible()
            and win.group_scroll.viewport().height() >= 80
        ),
        timeout=5000,
    )
    assert win.inspector_tabs.currentWidget() is win.group_scroll
    assert win.inspector_tabs.height() >= 140
    assert win.group_scroll.viewport().width() >= 100
    win.close()
    win._shutdown_spatial_worker()


def test_spatial_dock_reopens_visible_after_saved_hidden_layout(qtbot: object) -> None:
    """Reopen should recover the ROI dock even when Qt saved an invisible dock."""

    from PySide6.QtCore import QSettings

    settings = QSettings("PixelScope", "EnterpriseIqa")
    original_state = settings.value("analysis_window_spatial_dock_state")
    try:
        first = AnalysisWindow()
        qtbot.addWidget(first)  # type: ignore[attr-defined]
        first.show()
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: first.spatial_dock.isVisible(), timeout=5000
        )
        first.spatial_dock.setFloating(False)
        first.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, first.spatial_dock)
        first.spatial_dock.hide()
        QApplication.processEvents()
        saved_hidden = first.saveState()
        first.close()
        first._shutdown_spatial_worker()
        settings.setValue("analysis_window_spatial_dock_state", saved_hidden)
        second = AnalysisWindow()
        qtbot.addWidget(second)  # type: ignore[attr-defined]
        second.present_result(make_synthetic_result("ux2c-reopen-dock"))
        second.show()
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: second.spatial_dock.isVisible() and second.spatial_panel.buttons[0].isEnabled(),
            timeout=5000,
        )
        assert second.spatial_dock.toggleViewAction().isChecked()
        assert second.dockWidgetArea(second.spatial_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
        second.close()
        second._shutdown_spatial_worker()
    finally:
        if original_state is None:
            settings.remove("analysis_window_spatial_dock_state")
        else:
            settings.setValue("analysis_window_spatial_dock_state", original_state)


def test_spatial_cards_are_short_ranked_visuals(qtbot: object) -> None:
    """Keep rank icons/relative bars; do not regress to prose-card titles."""

    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(make_synthetic_result("ux2c-compact-ranks"))
    win.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed is not None, timeout=5000
    )
    assert len(win.spatial_panel.rank_badges) == 3
    assert len(win.spatial_panel.impact_bars) == 3
    for title in win.spatial_panel.titles:
        assert len(title.text()) < 35
        assert "STRONGEST" not in title.text()
        assert "LARGEST" not in title.text()
    assert len(win.spatial_panel.status_label.text()) < 45
    assert win.spatial_panel.impact_bars[0].value() == 100
    assert "GRID" in win.spatial_panel.provenance_badge.text()
    win.close()
    win._shutdown_spatial_worker()


def test_roi_dock_uses_native_plot_workspace_title_controls(qtbot: object) -> None:
    """Reuse stable Qt-painted Plot controls, not broken native float glyphs."""

    from pixelscope.ui.plots_dock_title import PlotsDockTitleBar

    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        win.spatial_dock.isVisible, timeout=4000
    )
    title = win.spatial_dock_title
    assert isinstance(title, PlotsDockTitleBar)
    assert win.spatial_dock.titleBarWidget() is title
    assert win._spatial_dock_chrome.parent() is win.spatial_dock
    assert title.title.text() == "Hotspots"
    assert all(
        not button.icon().isNull()
        for button in (title.float_button, title.maximize_button, title.close_button)
    )
    assert title.float_button.toolTip() == "Float Hotspots"
    assert title.maximize_button.toolTip() == "Maximize Hotspots"
    dock_icon = title.float_button.icon().cacheKey()
    title.float_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        win.spatial_dock.isFloating, timeout=4000
    )
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win.spatial_dock.titleBarWidget() is title, timeout=4000
    )
    assert title.float_button.icon().cacheKey() != dock_icon
    title.maximize_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: title._workspace_maximized, timeout=4000
    )
    assert title.maximize_button.toolTip() == "Restore Hotspots"
    title.maximize_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not title._workspace_maximized, timeout=4000
    )
    title.float_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not win.spatial_dock.isFloating(), timeout=4000
    )
    title.close_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        win.spatial_dock.isHidden, timeout=4000
    )
    win.close()
    win._shutdown_spatial_worker()


def test_hotspot_action_is_iconified_and_short(qtbot: object) -> None:
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    action = win.hotspot_overlay_action
    assert action.text() == "Show Hotspot"
    assert not action.icon().isNull()
    assert action.shortcut().toString() == "Alt+H"
    assert action in win.iqa_toolbar.actions()
    assert action.isCheckable()
    win.close()
    win._shutdown_spatial_worker()


def test_hidden_spatial_dock_attribute_switch_clears_previous_map_hotspots(
    qtbot: object,
) -> None:
    """P1: old Attribute GRID boxes must never label a new Attribute Map."""

    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(make_synthetic_result("ux2c-hidden-stale-map"))
    win.show()
    win.spatial_dock.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed is not None
        and len(win._spatial_cache.get(win._spatial_key(), ())) > 0,
        timeout=5000,
    )
    original_attribute = win._state().attribute_id  # type: ignore[union-attr]
    win.hotspot_overlay_action.setChecked(True)
    assert any(rect.isVisible() for rect, _ in win._candidate_overlay_items[2])

    win.spatial_dock.hide()
    win.attribute_table.selectRow(6)
    assert win._state().attribute_id != original_attribute  # type: ignore[union-attr]
    assert win.hotspot_overlay_action.isChecked()
    assert not any(rect.isVisible() for rect, _ in win._candidate_overlay_items[2])
    assert not any(text.isVisible() for _, text in win._candidate_overlay_items[2])

    win.spatial_dock.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed == win._spatial_key(), timeout=5000
    )
    assert any(rect.isVisible() for rect, _ in win._candidate_overlay_items[2])
    win.close()
    win._shutdown_spatial_worker()


def test_spatial_card_tracks_clear_manual_roi_and_changed_stride(
    qtbot: object,
) -> None:
    """P2: a checked card must match the actual source ROI, never stale rank."""

    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(make_synthetic_result("ux2c-roi-identity"))
    win.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: win._spatial_displayed is not None
        and len(win._spatial_cache.get(win._spatial_key(), ())) > 0,
        timeout=5000,
    )
    key = win._spatial_key()
    assert key is not None
    first = win._spatial_cache[key][0]
    win.spatial_panel.buttons[0].click()
    assert win.current_roi == first.roi
    assert win.spatial_panel.buttons[0].isChecked()

    win.clear_roi_action.trigger()
    assert win.current_roi is None
    assert not any(card.isChecked() for card in win.spatial_panel.buttons)

    win.spatial_panel.buttons[0].click()
    assert win.current_roi == first.roi
    view = win._views[2]
    viewport = view.viewport()
    a = view.mapFromScene(QPointF(first.x + 100, first.y + 110))
    b = view.mapFromScene(QPointF(first.x + 180, first.y + 190))
    assert viewport.rect().contains(a) and viewport.rect().contains(b)
    qtbot.mousePress(  # type: ignore[attr-defined]
        viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, pos=a
    )
    qtbot.mouseMove(viewport, pos=b)  # type: ignore[attr-defined]
    qtbot.mouseRelease(  # type: ignore[attr-defined]
        viewport, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, pos=b
    )
    assert win.current_roi is not None and win.current_roi != first.roi
    assert not any(card.isChecked() for card in win.spatial_panel.buttons)

    win.spatial_panel.buttons[0].click()
    old_roi = win.current_roi
    assert old_roi == first.roi
    # Inject one controlled new-stride candidate at different source pixels:
    # deterministic regardless of the particular GRID ranking topology.
    other_x = first.x + 64 if first.x + first.width + 64 <= 3840 else first.x - 64
    new_stride_key = (key[0], key[1], 64)
    win._spatial_cache[new_stride_key] = (replace(first, x=other_x),)
    win.spatial_panel.stride_selector.setCurrentIndex(0)
    assert win._spatial_displayed == new_stride_key
    assert win.current_roi == old_roi
    assert not any(card.isChecked() for card in win.spatial_panel.buttons)

    # Switching back is allowed to rediscover the exact same active ROI.
    win.spatial_panel.stride_selector.setCurrentIndex(1)
    assert win.spatial_panel.buttons[0].isChecked()
    win.close()
    win._shutdown_spatial_worker()


def test_scan_failure_is_terminal_not_perpetual_busy(
    qtbot: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P2: rejected workload or ValueError must clear indeterminate progress."""

    import pixelscope_enterprise.iqa.analysis_window as analysis_module

    def rejected_scan(*_args: object, **_kwargs: object) -> tuple[()]:
        raise ValueError("test-only rejected budget")

    monkeypatch.setattr(analysis_module, "find_spatial_candidates", rejected_scan)
    win = AnalysisWindow()
    qtbot.addWidget(win)  # type: ignore[attr-defined]
    win.present_result(make_synthetic_result("ux2c-failed-scan"))
    win.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: "scan unavailable" in win.spatial_panel.status_label.text().lower(),
        timeout=5000,
    )
    assert win._spatial_pending is None
    assert win._spatial_future is None
    assert not win._spatial_timer.isActive()
    assert not win.spatial_panel.progress.isVisible()
    assert all(not card.isEnabled() for card in win.spatial_panel.buttons)
    win.close()
    win._shutdown_spatial_worker()
