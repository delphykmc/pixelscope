from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.multi_compare_view import (
    FIXED_MULTIVIEW_ARRANGEMENT,
    MultiCompareView,
)


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
def test_fixed_geometry_and_pin_visibility(qtbot: object, count: int) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    documents = _documents(count)
    capacity = 2 if count <= 2 else 4 if count <= 4 else 6
    view.set_capacity(capacity)
    view.set_layout_kind("Multi View", documents[0].document_id)
    view.set_documents(documents, 0, count, None, None)

    placements, row_stretches, column_stretches = FIXED_GEOMETRY[count]
    actual = tuple(
        view._layout.getItemPosition(view._layout.indexOf(viewer))
        for viewer in view.occupied_viewers
    )
    assert actual == placements
    assert tuple(view._layout.rowStretch(index) for index in range(3)) == row_stretches
    assert tuple(view._layout.columnStretch(index) for index in range(3)) == column_stretches
    assert all(
        viewer.header.focus.isHidden() is (count not in (3, 5)) for viewer in view.occupied_viewers
    )


def test_three_view_real_geometry_uses_equal_columns_and_two_row_focus(qtbot: object) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    documents = _documents(3)
    view.set_capacity(4)
    view.set_layout_kind("Multi View", documents[0].document_id)
    view.set_documents(documents, 0, 3, None, None)
    view.resize(1200, 720)
    view.show()
    qtbot.wait(40)  # type: ignore[attr-defined]

    focus, upper_right, lower_right = (viewer.geometry() for viewer in view.occupied_viewers)
    spacing = view._layout.spacing()
    assert abs(focus.width() - upper_right.width()) <= 3
    assert abs(upper_right.width() - lower_right.width()) <= 3
    assert abs(upper_right.height() - lower_right.height()) <= 3
    assert abs(focus.height() - (upper_right.height() + lower_right.height() + spacing)) <= 4


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

    focus, upper_right, middle_right, lower_left, lower_right = (
        viewer.geometry() for viewer in view.occupied_viewers
    )
    spacing = view._layout.spacing()
    widths = [
        focus.width(),
        upper_right.width(),
        middle_right.width(),
        lower_left.width(),
        lower_right.width(),
    ]
    assert max(widths) - min(widths) <= 3
    row_heights = [upper_right.height(), middle_right.height(), lower_left.height()]
    assert max(row_heights) - min(row_heights) <= 3
    assert abs(lower_left.height() - lower_right.height()) <= 3
    assert abs(focus.height() - (upper_right.height() + middle_right.height() + spacing)) <= 4


def test_arrangement_choices_are_not_exposed_and_legacy_setting_is_normalized(
    qtbot: object,
) -> None:
    QSettings().setValue("ui/multiview_arrangement", "Left Focus · 3 Columns")
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window._multiview_arrangement == FIXED_MULTIVIEW_ARRANGEMENT
    assert window.multi_compare_view.arrangement == FIXED_MULTIVIEW_ARRANGEMENT
    assert window.multiview_arrangement_actions == {}
    view_action = next(action for action in window.menuBar().actions() if action.text() == "&View")
    view_menu = view_action.menu()
    assert view_menu is not None
    menu_texts = {action.text() for action in view_menu.actions()}
    assert "Top Focus · 2 Columns" not in menu_texts
    assert "Left Focus · 3 Columns" not in menu_texts
    window.close()


@pytest.mark.parametrize("source_count", (2, 4))
def test_difference_becomes_focus_for_three_and_five_tiles(
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


def test_focus_pin_reorders_three_view_without_changing_selection_order(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _documents(3)
    for document in documents:
        window.add_document(document, select=False)
    selected_ids = [document.document_id for document in documents]
    window._select_document_ids(selected_ids)
    window.set_layout_mode("Multi View")
    viewer_ids = tuple(id(viewer) for viewer in window.multi_compare_view.viewers)

    window._set_focus_document(documents[2])

    assert window._focus_document_id == documents[2].document_id
    assert window.multi_compare_view.viewers[0].document is documents[2]
    assert [document.document_id for document in window.selected_documents] == selected_ids
    assert tuple(id(viewer) for viewer in window.multi_compare_view.viewers) == viewer_ids
    window.close()


def test_six_source_diff_hide_restores_exact_multiview_state(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _documents(6)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
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
    focus_id = window._focus_document_id
    active_id = window._active_document_id
    display_order = tuple(window._multi_display_order)

    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window.central_stack.currentWidget() is window.viewer,
        timeout=3000,
    )
    assert window.viewer.document is window._difference_document
    window.diff_action.setChecked(False)

    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert window._layout_mode == "Multi View"
    assert window._focus_document_id == focus_id
    assert window._active_document_id == active_id
    assert tuple(window._multi_display_order) == display_order
    restored = window.multi_compare_view.capture_view_state()
    assert restored.active_document_id == before.active_document_id
    assert restored.ranges is not None and before.ranges is not None
    assert np.allclose(restored.ranges, before.ranges)
    window.close()
