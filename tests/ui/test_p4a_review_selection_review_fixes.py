from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QSettings, Qt

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.design_tokens import TOKENS, tile_style
from pixelscope.ui.review_selection import ReviewSelectionController


def _ready_documents(tmp_path: Path, count: int) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((8, 8), index, dtype=np.uint8),
            f"review{index + 1:02d}.png",
            source_path=tmp_path / f"review{index + 1:02d}.png",
        )
        for index in range(count)
    ]


def _production_window(qtbot: object) -> tuple[MainWindow, ReviewSelectionController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window, window.review_selection_controller


def _register_and_select(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])


def _click(qtbot: object, widget: object) -> None:
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]


def _selected_tree_ids(window: MainWindow) -> list[str]:
    return [
        str(item.data(0, Qt.ItemDataRole.UserRole))
        for item in window.document_list.document_items()
        if item.isSelected()
    ]


def test_files_remove_requested_signal_invalidates_review_before_stale_state_survives(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 3)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    controller.enter_review()
    _click(qtbot, window.multi_compare_view.occupied_viewers[0].header.pick)

    assert controller.active
    assert controller.picked_ids == {documents[0].document_id}

    window.document_list.remove_requested.emit([documents[0].document_id])

    assert not controller.active
    assert controller.picked_count == 0
    assert documents[0].document_id not in window.documents
    assert all(viewer.header.pick.isHidden() for viewer in window.multi_compare_view.viewers)
    assert all(
        not bool(viewer.property("reviewPicked"))
        for viewer in window.multi_compare_view.viewers
    )
    window.close()


def test_picked_tile_border_is_independent_and_persists_across_pages(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 7)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    controller.enter_review()

    target = window.multi_compare_view.occupied_viewers[1]
    assert not bool(target.property("reviewPicked"))
    _click(qtbot, target.header.pick)

    assert bool(target.property("reviewPicked"))
    assert target.header.pick.isChecked()
    assert TOKENS.warning in target.styleSheet()
    assert 'ImageViewer[reviewPicked="true"]' in target.styleSheet()
    assert TOKENS.warning in tile_style(False)
    assert TOKENS.warning in tile_style(True)
    assert f"border-left: 5px solid {TOKENS.accent}" in tile_style(True)

    window.next_comparison_page()
    assert documents[1].document_id in controller.picked_ids
    window.previous_comparison_page()

    restored = window.multi_compare_view.occupied_viewers[1]
    assert restored.document is documents[1]
    assert bool(restored.property("reviewPicked"))
    assert restored.header.pick.isChecked()
    window.close()


@pytest.mark.parametrize(
    "modifier",
    [
        Qt.KeyboardModifier.NoModifier,
        Qt.KeyboardModifier.ControlModifier,
        Qt.KeyboardModifier.ShiftModifier,
    ],
)
def test_viewer_drag_gestures_do_not_toggle_review_pick(
    qtbot: object,
    tmp_path: Path,
    modifier: Qt.KeyboardModifier,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 2)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    window.show()
    controller.enter_review()

    viewer = window.multi_compare_view.occupied_viewers[0]
    viewport = viewer._graphics.viewport()
    start = viewport.rect().center()
    end = start + QPoint(24, 18)
    picked_before = controller.picked_ids

    qtbot.mousePress(  # type: ignore[attr-defined]
        viewport,
        Qt.MouseButton.LeftButton,
        modifier=modifier,
        pos=start,
    )
    qtbot.mouseMove(viewport, end, delay=10)  # type: ignore[attr-defined]
    qtbot.mouseRelease(  # type: ignore[attr-defined]
        viewport,
        Qt.MouseButton.LeftButton,
        modifier=modifier,
        pos=end,
    )

    assert controller.picked_ids == picked_before
    assert not viewer.header.pick.isChecked()
    assert not bool(viewer.property("reviewPicked"))
    window.close()


def test_keep_picked_updates_files_selection_and_first_result_is_active(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 5)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    controller.enter_review()

    viewers = window.multi_compare_view.occupied_viewers
    _click(qtbot, viewers[1].header.pick)
    _click(qtbot, viewers[4].header.pick)

    assert controller.keep_picked()

    expected = [documents[1].document_id, documents[4].document_id]
    assert [document.document_id for document in window.selected_documents] == expected
    assert _selected_tree_ids(window) == expected
    assert window._active_document_id == expected[0]
    active_item = window.document_list.document_item(expected[0])
    assert active_item is not None
    assert bool(active_item.data(0, window.document_list.ACTIVE_ROLE))
    assert not controller.active
    assert controller.picked_count == 0
    window.close()
