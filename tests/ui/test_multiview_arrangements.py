from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.multi_compare_view import (
    LEFT_FOCUS_ARRANGEMENT,
    TOP_FOCUS_ARRANGEMENT,
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
            f"arrangement-{index + 1}.png",
        )
        for index in range(count)
    ]


TOP_GEOMETRY = {
    1: (((0, 0, 1, 1),), (1, 0, 0), (1, 0, 0)),
    2: (((0, 0, 1, 1), (0, 1, 1, 1)), (1, 0, 0), (1, 1, 0)),
    3: (((0, 0, 1, 2), (1, 0, 1, 1), (1, 1, 1, 1)), (2, 1, 0), (1, 1, 0)),
    4: (
        ((0, 0, 1, 1), (0, 1, 1, 1), (1, 0, 1, 1), (1, 1, 1, 1)),
        (1, 1, 0),
        (1, 1, 0),
    ),
    5: (
        (
            (0, 0, 1, 2),
            (1, 0, 1, 1),
            (1, 1, 1, 1),
            (2, 0, 1, 1),
            (2, 1, 1, 1),
        ),
        (2, 1, 1),
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

LEFT_GEOMETRY = {
    **{count: TOP_GEOMETRY[count] for count in (1, 2, 4)},
    3: (((0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1)), (1, 1, 0), (2, 1, 0)),
    5: (
        (
            (0, 0, 2, 1),
            (0, 1, 1, 1),
            (1, 1, 1, 1),
            (0, 2, 1, 1),
            (1, 2, 1, 1),
        ),
        (1, 1, 0),
        (2, 1, 1),
    ),
    6: (
        (
            (0, 0, 1, 1),
            (0, 1, 1, 1),
            (0, 2, 1, 1),
            (1, 0, 1, 1),
            (1, 1, 1, 1),
            (1, 2, 1, 1),
        ),
        (1, 1, 0),
        (1, 1, 1),
    ),
}


@pytest.mark.parametrize(
    ("arrangement", "expected"),
    (
        (TOP_FOCUS_ARRANGEMENT, TOP_GEOMETRY),
        (LEFT_FOCUS_ARRANGEMENT, LEFT_GEOMETRY),
    ),
)
@pytest.mark.parametrize("count", range(1, 7))
def test_arrangement_geometry_and_pin_visibility(
    qtbot: object,
    arrangement: str,
    expected: dict[
        int, tuple[tuple[tuple[int, int, int, int], ...], tuple[int, ...], tuple[int, ...]]
    ],
    count: int,
) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    documents = _documents(count)
    capacity = 2 if count <= 2 else 4 if count <= 4 else 6
    view.set_capacity(capacity)
    view.set_arrangement(arrangement)
    view.set_layout_kind("Multi View", documents[0].document_id)
    view.set_documents(documents, 0, count, None, None)

    placements, row_stretches, column_stretches = expected[count]
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


def test_arrangement_switch_reuses_viewers_and_preserves_display_state(
    qtbot: object, monkeypatch: object
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _documents(3)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    window._set_focus_document(documents[1])
    window._shared_roi = RoiBounds(2, 3, 10, 8)
    window._shared_line = LineSelection(1, 4, 20)
    window.multi_compare_view.set_shared_roi(window._shared_roi)
    window.multi_compare_view.set_shared_line(window._shared_line)
    for viewer in window.multi_compare_view.occupied_viewers:
        viewer.show_cursor(7, 8)
    active_viewer = window.multi_compare_view.viewers[2]
    window.multi_compare_view._activate_viewer(active_viewer)
    active_id = active_viewer.document.document_id  # type: ignore[union-attr]
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    window.multi_compare_view.viewers[0].view_box.setRange(
        xRange=(4.0, 22.0), yRange=(3.0, 15.0), padding=0
    )
    before_zoom = window.multi_compare_view.viewers[0].zoom_percent
    before_range = window.multi_compare_view.viewers[0].view_box.viewRange()
    before_center = (
        sum(before_range[0]) / 2.0,
        sum(before_range[1]) / 2.0,
    )
    viewer_ids = tuple(id(viewer) for viewer in window.multi_compare_view.viewers)
    selection_order = [document.document_id for document in window.selected_documents]

    for viewer in window.multi_compare_view.viewers:
        monkeypatch.setattr(  # type: ignore[attr-defined]
            viewer,
            "set_document",
            lambda *_args, **_kwargs: pytest.fail("arrangement reloaded an image"),
        )
    window.set_multiview_arrangement(LEFT_FOCUS_ARRANGEMENT)
    qtbot.wait(20)  # type: ignore[attr-defined]

    after_range = window.multi_compare_view.viewers[0].view_box.viewRange()
    after_center = (sum(after_range[0]) / 2.0, sum(after_range[1]) / 2.0)
    assert tuple(id(viewer) for viewer in window.multi_compare_view.viewers) == viewer_ids
    assert window._focus_document_id == documents[1].document_id
    assert window._active_document_id == active_id
    assert [document.document_id for document in window.selected_documents] == selection_order
    assert window.multi_compare_view.viewers[0].zoom_percent == pytest.approx(before_zoom, rel=0.03)
    assert after_center == pytest.approx(before_center, rel=0.03)
    assert all(viewer._roi.isVisible() for viewer in window.multi_compare_view.occupied_viewers)
    assert all(
        viewer._line_item.isVisible() for viewer in window.multi_compare_view.occupied_viewers
    )
    assert all(
        viewer._vertical_cursor.isVisible() and viewer._horizontal_cursor.isVisible()
        for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_arrangement_is_exclusive_and_restored_from_qsettings(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.set_multiview_arrangement(LEFT_FOCUS_ARRANGEMENT)
    assert window.multiview_arrangement_group.isExclusive()
    assert QSettings().value("ui/multiview_arrangement") == LEFT_FOCUS_ARRANGEMENT
    assert window.multiview_arrangement_actions[LEFT_FOCUS_ARRANGEMENT].isChecked()
    assert not window.multiview_arrangement_actions[TOP_FOCUS_ARRANGEMENT].isChecked()

    restored = MainWindow()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    assert restored._multiview_arrangement == LEFT_FOCUS_ARRANGEMENT
    assert restored.multi_compare_view.arrangement == LEFT_FOCUS_ARRANGEMENT
    assert restored.multiview_arrangement_actions[LEFT_FOCUS_ARRANGEMENT].isChecked()
    window.close()
    restored.close()


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


def test_six_source_diff_hide_restores_exact_multiview_state(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _documents(6)
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    window.set_multiview_arrangement(LEFT_FOCUS_ARRANGEMENT)
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
    window.set_multiview_arrangement(TOP_FOCUS_ARRANGEMENT)
    window.diff_action.setChecked(False)

    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert window._layout_mode == "Multi View"
    assert window._multiview_arrangement == LEFT_FOCUS_ARRANGEMENT
    assert window._focus_document_id == focus_id
    assert window._active_document_id == active_id
    assert tuple(window._multi_display_order) == display_order
    restored = window.multi_compare_view.capture_view_state()
    assert restored.active_document_id == before.active_document_id
    assert restored.ranges is not None and before.ranges is not None
    assert np.allclose(restored.ranges, before.ranges)
    window.close()
