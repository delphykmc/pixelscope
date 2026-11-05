"""W06 layout-only preset and W05 presentation coexistence regression tests."""

from __future__ import annotations

import gc
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDockWidget, QWidget

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_presets import ComparisonPreset
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.workspace_presets import WorkspacePreset, WorkspacePresetController

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object, *, show: bool = True) -> tuple[MainWindow, WorkspacePresetController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    owner = window.beta_workspace_hardening_controller.workspace_presets
    assert isinstance(owner, WorkspacePresetController)
    if show:
        window.show()
        qtbot.wait(40)  # type: ignore[attr-defined]
    return window, owner


def _sources(window: MainWindow, root: Path, count: int) -> list[ImageDocument]:
    result = [
        ImageDocument.from_array(
            np.full((48, 64), 20 + index, dtype=np.uint8),
            "한글_very_long_comparison_source_" * 3 + ".png",
            source_path=root / str(index) / "한글_same.png",
        )
        for index in range(count)
    ]
    for document in result:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in result])
    return result


def _identity(window: MainWindow) -> tuple[object, ...]:
    """Only the actual canonical owners (not a W06 copy) are sampled."""

    w05 = window.quick_compare_controller.comparison_presets
    return (
        tuple(window.documents),
        tuple(d.document_id for d in window.selected_documents),
        tuple(d.document_id for d in window.current_comparison_documents()),
        window._page_start,
        window._active_document_id,
        window._primary_page_slot,
        window._comparison_plan,
        w05.preset,
        w05.pair,
        window._shared_roi,
        window._shared_line,
        window._difference_source_ids,
        window._difference_document,
        window.multi_compare_view.sync_enabled,
    )


@pytest.mark.parametrize("count", [2, 4, 6])
def test_workspace_roundtrip_preserves_w05_sources_and_roi(
    qtbot: object,
    tmp_path: Path,
    count: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, workspace = _window(qtbot)
    _sources(window, tmp_path, count)
    w05 = window.quick_compare_controller.comparison_presets
    w05.set_preset(ComparisonPreset.ORIGINAL_2)
    window._shared_roi = RoiBounds(3, 4, 20, 18)
    # Layout changes can legitimately change the visible bounds. W01 physical
    # scale and reference-space center, not the full ViewBox ranges, are stable.
    window.multi_compare_view.zoom_100_percent()
    qtbot.wait(60)  # type: ignore[attr-defined]
    zoom_before = tuple(
        (
            viewer.document.document_id,
            viewer.zoom_percent,
            tuple((axis[0] + axis[1]) * 0.5 for axis in viewer.view_box.viewRange()),
        )
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    )

    def no_calculate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Workspace switch must not calculate a Difference")

    monkeypatch.setattr(window.difference_panel, "calculate_difference", no_calculate)
    identity_before = _identity(window)
    for preset in (
        WorkspacePreset.ANALYZE,
        WorkspacePreset.REVIEW,
        WorkspacePreset.COMPARE,
    ):
        workspace.select(preset)
        assert workspace.preset is preset
        assert _identity(window) == identity_before
        qtbot.wait(60)  # type: ignore[attr-defined]
        zoom_after = tuple(
            (
                viewer.document.document_id,
                viewer.zoom_percent,
                tuple((axis[0] + axis[1]) * 0.5 for axis in viewer.view_box.viewRange()),
            )
            for viewer in window.multi_compare_view.occupied_viewers
            if viewer.document is not None
        )
        assert len(zoom_after) == len(zoom_before)
        for (source_id, scale, center), (after_id, after_scale, after_center) in zip(
            zoom_before, zoom_after, strict=True
        ):
            assert after_id == source_id
            if scale is not None and after_scale is not None:
                assert after_scale == pytest.approx(scale, rel=0.025)
            assert after_center == pytest.approx(center, abs=3.0)
    assert w05.preset is ComparisonPreset.ORIGINAL_2
    window.close()


@pytest.mark.parametrize("size", [(1400, 880), (1920, 1080), (3440, 1392)])
def test_analyze_keeps_statistics_and_plot_surfaces_accessible(
    qtbot: object,
    size: tuple[int, int],
) -> None:
    window, workspace = _window(qtbot)
    # A zero-source Statistics table has no numeric rows to read. Use actual
    # multichannel results to assert three fully visible native metrics rows.
    documents = [
        ImageDocument.from_array(
            np.full((48, 64, 3), 20 + index, dtype=np.uint8),
            f"analyze_rgb_{index}.png",
        )
        for index in range(2)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 2,
        timeout=3000,
    )
    window.resize(*size)
    workspace.select(WorkspacePreset.ANALYZE)
    table = window.comparison_analysis_panel.table
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: table.rowCount() >= 3 and table.viewport().height() > 0,
        timeout=3000,
    )
    qtbot.wait(60)  # type: ignore[attr-defined]

    assert not window.bottom_dock.isHidden()
    assert window.sidebar_splitter.widget(1).isVisible()
    assert table.verticalScrollBar() is not None
    assert table.horizontalScrollBar() is not None
    assert table.item(2, 4) is not None  # A real native Mean cell in row 3.
    visible_rows_height = sum(table.rowHeight(row) for row in range(3))
    assert table.viewport().height() >= visible_rows_height, (
        "Statistics must show three actual rows",
        size,
        table.viewport().size(),
        window.sidebar_splitter.sizes(),
        window.comparison_analysis_panel.image_summary_group.height(),
        window.bottom_dock.height(),
    )
    assert (
        window.comparison_analysis_panel.image_summary.verticalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
    assert window.main_splitter.widget(1).width() > window.main_splitter.widget(0).width()
    window.close()


@pytest.mark.parametrize(
    "presentation",
    [
        ComparisonPreset.ORIGINAL_2,
        ComparisonPreset.ORIGINAL_4,
        ComparisonPreset.AB_DIFF,
        ComparisonPreset.DIFF_FOCUS,
    ],
)
def test_w05_presentation_and_w06_workspace_orthogonal(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    presentation: ComparisonPreset,
) -> None:
    window, workspace = _window(qtbot)
    _sources(window, tmp_path, 4)
    w05 = window.quick_compare_controller.comparison_presets

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Workspace preset cannot calculate Difference")

    monkeypatch.setattr(window.difference_panel, "calculate_difference", forbidden)
    w05.set_preset(presentation)
    before = _identity(window)
    for name in (WorkspacePreset.ANALYZE, WorkspacePreset.REVIEW, WorkspacePreset.COMPARE):
        workspace.select(name)
        assert _identity(window) == before
    window.close()


def test_command_hierarchy_preserves_single_existing_actions(qtbot: object) -> None:
    window, workspace = _window(qtbot)
    toolbar = window.main_toolbar
    actions = toolbar.actions()
    w05 = window.quick_compare_controller.comparison_presets
    w05_group_action = next(
        action for action in actions if toolbar.widgetForAction(action) is w05.group
    )
    workspace_group_action = next(
        action
        for action in actions
        if toolbar.widgetForAction(action) is window.workspace_preset_control
    )
    existing_open = window.action_map["Open Images..."]
    assert actions.count(existing_open) == 1
    assert actions.index(existing_open) < actions.index(workspace_group_action)
    assert actions.index(workspace_group_action) < actions.index(w05_group_action)
    assert actions.index(w05_group_action) < actions.index(window.action_map["Fit Image"])
    assert actions.index(window.action_map["Fit Image"]) < actions.index(window.diff_action)
    assert actions.index(window.diff_action) < actions.index(window.export_toolbar_action)
    assert workspace.selector.accessibleName() == "Workspace layout preset"
    window.close()


@pytest.mark.parametrize("width", [960, 1400])
def test_compact_toolbar_keeps_critical_commands_and_pair_visible(
    qtbot: object,
    width: int,
) -> None:
    window, workspace = _window(qtbot)
    window.resize(width, 880)
    qtbot.wait(80)  # type: ignore[attr-defined]
    toolbar = window.main_toolbar
    w05 = window.quick_compare_controller.comparison_presets
    assert w05.group.isVisibleTo(toolbar)
    assert workspace.selector.isVisibleTo(toolbar)
    assert w05.reference_combo.isVisibleTo(toolbar)
    assert w05.target_combo.isVisibleTo(toolbar)
    for action in (
        window.action_map["Open Images..."],
        window.action_map["Fit Image"],
        window.action_map["100% Zoom"],
        window.sync_action,
        window.diff_action,
    ):
        rect = toolbar.actionGeometry(action)
        assert not rect.isEmpty()
        assert toolbar.rect().contains(rect), (
            width,
            action.text(),
            toolbar.size(),
            rect,
        )
    if width == 960:
        assert toolbar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    window.close()


def test_manual_splitters_are_restored_for_each_preset(qtbot: object) -> None:
    window, workspace = _window(qtbot)
    workspace.select(WorkspacePreset.ANALYZE)
    window.main_splitter.setSizes([470, 930])
    window.sidebar_splitter.setSizes([210, 410])
    recorded_main = window.main_splitter.sizes()
    recorded_sidebar = window.sidebar_splitter.sizes()

    workspace.select(WorkspacePreset.REVIEW)
    workspace.select(WorkspacePreset.ANALYZE)
    assert all(
        abs(a - b) <= 8 for a, b in zip(window.main_splitter.sizes(), recorded_main, strict=True)
    ), (recorded_main, window.main_splitter.sizes())
    assert all(
        abs(a - b) <= 8
        for a, b in zip(window.sidebar_splitter.sizes(), recorded_sidebar, strict=True)
    ), (recorded_sidebar, window.sidebar_splitter.sizes())
    window.close()


def test_floating_hidden_close_reopen_and_preset_restore(qtbot: object) -> None:
    window, workspace = _window(qtbot)
    workspace.select(WorkspacePreset.ANALYZE)
    dock = window.bottom_dock
    assert isinstance(dock, QDockWidget)
    dock.setFloating(True)
    dock.show()
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    workspace.select(WorkspacePreset.REVIEW)
    assert dock.isHidden()
    workspace.select(WorkspacePreset.ANALYZE)
    assert dock.isFloating()
    assert not dock.isHidden()
    dock.hide()
    dock.show()
    assert dock.isFloating()
    window.close()


def test_floating_maximize_and_redock_remain_native(qtbot: object) -> None:
    window, workspace = _window(qtbot)
    workspace.select(WorkspacePreset.ANALYZE)
    dock = window.bottom_dock
    dock.setFloating(True)
    qtbot.waitUntil(dock.isFloating)  # type: ignore[attr-defined]
    dock.showMaximized()
    qtbot.waitUntil(dock.isMaximized)  # type: ignore[attr-defined]
    dock.showNormal()
    qtbot.waitUntil(lambda: not dock.isMaximized())  # type: ignore[attr-defined]
    window._redock_plots()
    assert not dock.isFloating()
    assert not dock.isHidden()
    workspace.select(WorkspacePreset.REVIEW)
    workspace.select(WorkspacePreset.ANALYZE)
    assert not dock.isFloating()
    window.close()


def test_restart_restores_preset_and_reset_clears_w06_keys(qtbot: object) -> None:
    window, workspace = _window(qtbot)
    workspace.select(WorkspacePreset.REVIEW)
    window.close()

    restored, owner = _window(qtbot)
    assert owner.preset is WorkspacePreset.REVIEW
    assert owner.selector.currentData() == WorkspacePreset.REVIEW.value
    assert not any(
        dock.objectName().lower().startswith("finding")
        for dock in restored.findChildren(QDockWidget)
    )
    restored.action_map["Reset Workspace Layout"].trigger()
    assert owner.preset is WorkspacePreset.COMPARE
    sizes = restored.sidebar_splitter.sizes()
    assert sizes[0] / max(1, sum(sizes)) == pytest.approx(0.68, abs=0.08)
    owner.select(WorkspacePreset.COMPARE)
    assert restored.sidebar_splitter.sizes() == sizes
    assert QSettings().value("ui/workspace_preset") is None
    assert not QSettings().contains("ui/workspace_layouts/v1/review/dock_state")
    restored.close()


def test_corrupt_workspace_settings_fall_back_without_changing_sources(
    qtbot: object,
    tmp_path: Path,
) -> None:
    settings = QSettings()
    settings.setValue("ui/workspace_preset", "Analyze")
    for name in ("dock_state", "main_splitter", "sidebar_splitter"):
        settings.setValue(f"ui/workspace_layouts/v1/analyze/{name}", "not a Qt byte array")

    window, owner = _window(qtbot)
    _sources(window, tmp_path, 2)
    before = _identity(window)
    owner.select(WorkspacePreset.REVIEW)
    owner.select(WorkspacePreset.ANALYZE)
    assert owner.preset is WorkspacePreset.ANALYZE
    assert _identity(window) == before
    assert window.main_splitter.widget(1).width() > 0
    window.close()


def test_partial_offscreen_title_region_is_recovered(qtbot: object) -> None:
    window, workspace = _window(qtbot)
    primary = QGuiApplication.primaryScreen()
    assert primary is not None
    screen = primary.availableGeometry()
    window.move(screen.right() - 8, screen.top() + 40)
    workspace._recover_windows()
    assert window.frameGeometry().x() < screen.right() - 8
    window.close()


def test_offscreen_geometry_recovers_on_present_screen(qtbot: object) -> None:
    window, owner = _window(qtbot)
    window.move(50000, 50000)
    owner._recover_windows()
    assert window.geometry().x() < 50000
    assert window.geometry().y() < 50000
    window.close()


def test_existing_actions_and_recent_menu_are_reused(qtbot: object, tmp_path: Path) -> None:
    window, workspace = _window(qtbot)
    assert window.action_map["Open Images..."] in window.main_toolbar.actions()
    assert window.action_map["Open Images..."].shortcut().toString() == "Ctrl+O"
    recent = window.empty_workspace.open_recent_button
    assert recent.menu() is not None
    assert len(recent.menu().actions()) == 3

    _sources(window, tmp_path, 2)
    combo = window.quick_compare_controller.comparison_presets.reference_combo
    assert "한글" in combo.toolTip()
    assert "Reference A" in combo.accessibleDescription()
    assert combo.width() <= combo.maximumWidth()
    assert isinstance(workspace.selector, QWidget)
    picks = window.review_selection_controller
    assert picks.clear_button.text() == "Clear Picks"
    assert picks.keep_button.text() == "Keep Picks"
    assert picks.clear_button.accessibleName() == "Clear Selection"
    assert "temporary Picks" in picks.clear_button.accessibleDescription()
    assert "Files Selected" in picks.keep_button.accessibleDescription()
    window.close()


def test_normal_gc_close_stops_workspace_callbacks(qtbot: object) -> None:
    window, workspace = _window(qtbot)
    workspace.select(WorkspacePreset.ANALYZE)
    gc.collect()
    window.close()
    assert workspace._quiescing
    assert not workspace._capture_timer.isActive()
    assert not workspace._recover_timer.isActive()
    assert not workspace._density_timer.isActive()
    gc.collect()
