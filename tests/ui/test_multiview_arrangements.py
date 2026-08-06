from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.main_window import MainWindow, SixImageDiffRestoreState
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.multi_compare_view import MultiCompareView


@pytest.fixture(autouse=True)
def isolated_ui_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    QSettings().clear()


def _documents(count: int) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((24, 36, 3), index * 10, dtype=np.uint8),
            f"layout-{index + 1}.png",
        )
        for index in range(count)
    ]


def _layout_snapshot(view: MultiCompareView) -> tuple[tuple[int, int, int, int], ...]:
    return tuple(
        view._layout.getItemPosition(view._layout.indexOf(viewer))
        for viewer in view.occupied_viewers
    )


def _range_center(viewer: object) -> tuple[float, float]:
    ranges = viewer.view_box.viewRange()  # type: ignore[attr-defined]
    return (
        (float(ranges[0][0]) + float(ranges[0][1])) / 2.0,
        (float(ranges[1][0]) + float(ranges[1][1])) / 2.0,
    )


FIXED_GEOMETRY = {
    1: (((0, 0, 1, 1),), (1, 0, 0), (1, 0, 0)),
    2: (((0, 0, 1, 1), (0, 1, 1, 1)), (1, 0, 0), (1, 1, 0)),
    3: (((0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1)), (1, 1, 0), (1, 1, 0)),
    4: (
        ((0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)),
        (1, 1, 0),
        (1, 1, 0),
    ),
    5: (
        (
            (0, 0, 2, 1),
            (0, 1, 1, 1),
            (1, 1, 1, 1),
            (2, 0, 1, 1),
            (2, 1, 1, 1),
        ),
        (1, 1, 1),
        (1, 1, 0),
    ),
    6: (
        (
            (0, 0, 1, 1),
            (0, 1, 1, 1),
            (1, 0, 1, 1),
            (1, 1, 1, 1),
            (2, 0, 1, 1),
            (2, 1, 1, 1),
        ),
        (1, 1, 1),
        (1, 1, 0),
    ),
}


@pytest.mark.parametrize("count", range(1, 7))
def test_fixed_geometry_and_primary_visibility(qtbot: object, count: int) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    view.show()
    documents = _documents(count)
    capacity = 2 if count <= 2 else 4 if count <= 4 else 6
    view.set_capacity(capacity)
    view.set_layout_kind("Multi View", documents[0].document_id)
    view.set_documents(documents, 0, count, None, None)

    placements, row_stretches, column_stretches = FIXED_GEOMETRY[count]
    assert _layout_snapshot(view) == placements
    assert tuple(view._layout.rowStretch(index) for index in range(3)) == row_stretches
    assert tuple(view._layout.columnStretch(index) for index in range(3)) == column_stretches
    assert all(
        viewer.header.focus.isHidden() is (count == 1) for viewer in view.occupied_viewers
    )


def test_three_view_real_geometry_uses_equal_columns_and_two_row_primary(qtbot: object) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    documents = _documents(3)
    view.set_capacity(4)
    view.set_layout_kind("Multi View", documents[0].document_id)
    view.set_documents(documents, 0, 3, None, None)
    view.resize(1200, 720)
    view.show()
    qtbot.wait(40)  # type: ignore[attr-defined]

    primary, upper_right, lower_right = (viewer.geometry() for viewer in view.occupied_viewers)
    spacing = view._layout.spacing()
    assert abs(primary.width() - upper_right.width()) <= 3
    assert abs(upper_right.width() - lower_right.width()) <= 3
    assert abs(upper_right.height() - lower_right.height()) <= 3
    assert abs(primary.height() - (upper_right.height() + lower_right.height() + spacing)) <= 4


def test_five_view_real_geometry_extends_three_view_with_equal_bottom_row(
    qtbot: object,
) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    documents = _documents(5)
    view.set_capacity(6)
    view.set_layout_kind("Multi View", documents[0].document_id)
    view.set_documents(documents, 0, 5, None, None)
    view.resize(1200, 900)
    view.show()
    qtbot.wait(40)  # type: ignore[attr-defined]

    primary, upper_right, middle_right, lower_left, lower_right = (
        viewer.geometry() for viewer in view.occupied_viewers
    )
    spacing = view._layout.spacing()
    widths = [
        primary.width(),
        upper_right.width(),
        middle_right.width(),
        lower_left.width(),
        lower_right.width(),
    ]
    assert max(widths) - min(widths) <= 3
    row_heights = [upper_right.height(), middle_right.height(), lower_left.height()]
    assert max(row_heights) - min(row_heights) <= 3
    assert abs(lower_left.height() - lower_right.height()) <= 3
    assert abs(primary.height() - (upper_right.height() + middle_right.height() + spacing)) <= 4


def test_legacy_arrangement_setting_is_ignored_without_runtime_state(qtbot: object) -> None:
    settings = QSettings()
    legacy_value = "Left Focus · 3 Columns"
    settings.setValue("ui/multiview_arrangement", legacy_value)

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _documents(3)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")

    assert _layout_snapshot(window.multi_compare_view) == FIXED_GEOMETRY[3][0]
    assert not hasattr(window, "_multiview_arrangement")
    assert not hasattr(window, "multiview_arrangement_group")
    assert not hasattr(window, "multiview_arrangement_actions")
    assert not hasattr(window, "set_multiview_arrangement")
    assert not hasattr(window.multi_compare_view, "arrangement")
    assert not hasattr(window.multi_compare_view, "set_arrangement")

    view_action = next(action for action in window.menuBar().actions() if action.text() == "&View")
    view_menu = view_action.menu()
    assert view_menu is not None
    menu_texts = {action.text() for action in view_menu.actions()}
    assert "Top Focus · 2 Columns" not in menu_texts
    assert "Left Focus · 3 Columns" not in menu_texts

    window._save_ui_state()
    assert settings.value("ui/multiview_arrangement") == legacy_value
    settings.remove("ui/multiview_arrangement")
    window._save_ui_state()
    assert settings.value("ui/multiview_arrangement") is None
    window.close()


@pytest.mark.parametrize("count", (2, 3, 4, 5, 6))
def test_primary_reordering_preserves_fixed_layout_and_document_contracts(
    qtbot: object,
    count: int,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.resize(1200, 900)
    window.show()
    documents = _documents(count)
    for document in documents:
        window.add_document(document, select=False)
    selected_ids = [document.document_id for document in documents]
    logical_slots = {
        document.document_id: str(index + 1)
        for index, document in enumerate(documents)
    }
    window._select_document_ids(selected_ids)
    window.set_layout_mode("Multi View")
    qtbot.wait(40)  # type: ignore[attr-defined]

    viewer_ids = tuple(id(viewer) for viewer in window.multi_compare_view.viewers)
    before_geometry = _layout_snapshot(window.multi_compare_view)
    anchor = window.multi_compare_view.occupied_viewers[0]
    anchor.view_box.setRange(xRange=(3.0, 21.0), yRange=(2.0, 14.0), padding=0)
    qtbot.wait(20)  # type: ignore[attr-defined]
    before_state = window.multi_compare_view.capture_view_state()

    primary = documents[-1]
    window._set_focus_document(primary)
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert window._focus_document_id == primary.document_id
    assert window.multi_compare_view.viewers[0].document is primary
    assert [document.document_id for document in window.selected_documents] == selected_ids
    assert tuple(id(viewer) for viewer in window.multi_compare_view.viewers) == viewer_ids
    assert _layout_snapshot(window.multi_compare_view) == before_geometry
    assert before_geometry == FIXED_GEOMETRY[count][0]
    assert {
        viewer.document.document_id: viewer.header.badge.text()
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    } == logical_slots

    after_state = window.multi_compare_view.capture_view_state()
    assert before_state.ranges is not None and after_state.ranges is not None
    assert np.allclose(after_state.ranges, before_state.ranges)
    centers = [_range_center(viewer) for viewer in window.multi_compare_view.occupied_viewers]
    pixel_sizes = [
        viewer.view_box.viewPixelSize() for viewer in window.multi_compare_view.occupied_viewers
    ]
    assert all(np.allclose(center, centers[0]) for center in centers[1:])
    assert all(np.allclose(pixel_size, pixel_sizes[0]) for pixel_size in pixel_sizes[1:])
    window.close()


@pytest.mark.parametrize("source_count", (2, 4))
def test_difference_becomes_primary_for_three_and_five_tiles(
    qtbot: object, source_count: int
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _documents(source_count)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and len(window.multi_compare_view.occupied_viewers) == source_count + 1,
        timeout=3000,
    )
    assert window.multi_compare_view.viewers[0].document is window._difference_document
    assert window._focus_document_id == window._difference_document.document_id
    assert all(
        not viewer.header.focus.isHidden() for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_reset_workspace_removes_legacy_setting_and_restores_fixed_geometry(
    qtbot: object,
) -> None:
    settings = QSettings()
    settings.setValue("ui/multiview_arrangement", "Left Focus · 3 Columns")
    settings.setValue("analysis/bottom_tab", 1)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _documents(3)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")

    window.reset_workspace_layout()

    assert settings.value("ui/multiview_arrangement") is None
    assert settings.value("analysis/bottom_tab") is None
    assert window._layout_mode == "Auto"
    assert _layout_snapshot(window.multi_compare_view) == FIXED_GEOMETRY[3][0]
    window.close()


def test_six_source_diff_restore_state_has_only_required_fields() -> None:
    assert [field.name for field in fields(SixImageDiffRestoreState)] == [
        "layout_mode",
        "focus_document_id",
        "active_document_id",
        "page_start",
        "current_index",
        "display_order",
        "view_state",
    ]


def test_six_source_diff_hide_restores_exact_multiview_state(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _documents(6)
    for document in documents:
        window.add_document(document, select=False)
    selected_ids = [document.document_id for document in documents]
    logical_slots = {
        document.document_id: str(index + 1)
        for index, document in enumerate(documents)
    }
    window._select_document_ids(selected_ids)
    window.set_layout_mode("Multi View")
    window._set_focus_document(documents[2])
    active_viewer = next(
        viewer
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is documents[4]
    )
    window.multi_compare_view._activate_viewer(active_viewer)
    window.multi_compare_view.viewers[0].view_box.setRange(
        xRange=(3.0, 21.0), yRange=(2.0, 14.0), padding=0
    )
    before = window.multi_compare_view.capture_view_state()
    layout_mode = window._layout_mode
    focus_id = window._focus_document_id
    active_id = window._active_document_id
    page_start = window._page_start
    current_index = window._current_index
    display_order = tuple(window._multi_display_order)
    badge_by_id = {
        viewer.document.document_id: viewer.header.badge.text()
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    }

    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window.central_stack.currentWidget() is window.viewer,
        timeout=3000,
    )
    assert window.viewer.document is window._difference_document
    window.diff_action.setChecked(False)

    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert window._layout_mode == layout_mode == "Multi View"
    assert window._focus_document_id == focus_id
    assert window._active_document_id == active_id
    assert window._page_start == page_start
    assert window._current_index == current_index
    assert tuple(window._multi_display_order) == display_order
    assert [document.document_id for document in window.selected_documents] == selected_ids
    assert {
        viewer.document.document_id: viewer.header.badge.text()
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    } == badge_by_id == logical_slots
    restored = window.multi_compare_view.capture_view_state()
    assert restored.active_document_id == before.active_document_id
    assert restored.ranges is not None and before.ranges is not None
    assert np.allclose(restored.ranges, before.ranges)
    window.close()


def test_obsolete_arrangement_symbols_are_absent_from_runtime_source() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    multi_source = (repository_root / "src/pixelscope/ui/multi_compare_view.py").read_text(
        encoding="utf-8"
    )
    main_source = (repository_root / "src/pixelscope/app/main_window.py").read_text(
        encoding="utf-8"
    )
    runtime_source = multi_source + main_source

    for symbol in (
        "_FixedArrangementRegistry",
        "MULTIVIEW_ARRANGEMENTS",
        "FIXED_MULTIVIEW_ARRANGEMENT",
        "TOP_FOCUS_ARRANGEMENT",
        "_multiview_arrangement",
        "multiview_arrangement_group",
        "multiview_arrangement_actions",
        "set_multiview_arrangement",
        "set_arrangement(",
    ):
        assert symbol not in runtime_source
    assert 'self.settings.value("ui/multiview_arrangement"' not in main_source
    assert 'self.settings.setValue("ui/multiview_arrangement"' not in main_source
    assert main_source.count('"ui/multiview_arrangement"') == 1
