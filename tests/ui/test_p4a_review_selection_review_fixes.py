from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QWidget

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


def test_production_composition_has_no_review_mode_and_unwraps_curation_controls(
    qtbot: object,
) -> None:
    QSettings().clear()
    window, controller = _production_window(qtbot)

    assert window.review_selection_controller is controller
    assert not controller.active
    assert not hasattr(controller, "mode_button")
    assert not hasattr(controller, "cancel_button")
    assert controller.count_label.text() == "Selected 0"
    assert controller.clear_button.text() == "Clear Selection"
    assert controller.keep_button.text() == "Keep Selection"

    layout = window.presentation_controls_layout
    assert isinstance(layout, QHBoxLayout)
    gain = window.findChild(QComboBox, "DisplayGainCombo")
    assert gain is not None
    gain_host = window.findChild(QWidget, "DisplayGainControl")
    assert gain_host is not None
    assert layout.indexOf(window.comparison_page_group) < layout.indexOf(gain_host)
    assert layout.indexOf(gain_host) < layout.indexOf(controller.count_label)
    assert layout.indexOf(controller.count_label) < layout.indexOf(controller.clear_button)
    assert layout.indexOf(controller.clear_button) < layout.indexOf(controller.keep_button)
    assert layout.spacing() >= TOKENS.spacing_md
    window.close()


def test_files_remove_request_clears_curation_before_stale_state_survives(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 3)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    _click(qtbot, window.multi_compare_view.occupied_viewers[0].header.pick)

    assert controller.active
    assert controller.picked_ids == {documents[0].document_id}

    window.document_list._emit_remove_request([documents[0].document_id])

    assert not controller.active
    assert controller.picked_count == 0
    assert documents[0].document_id not in window.documents
    assert all(
        not viewer.header.pick.isChecked() for viewer in window.multi_compare_view.occupied_viewers
    )
    assert all(
        not bool(viewer.property("reviewPicked")) for viewer in window.multi_compare_view.viewers
    )
    window.close()


def test_direct_remove_requested_fallback_clears_curation_after_external_emit(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 3)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    _click(qtbot, window.multi_compare_view.occupied_viewers[0].header.pick)

    window.document_list.remove_requested.emit([documents[0].document_id])

    assert documents[0].document_id not in window.documents
    assert not controller.active
    assert controller.picked_count == 0
    window.close()


def test_selected_tile_yellow_border_and_pressed_pick_persist_across_pages(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 7)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)

    target = window.multi_compare_view.occupied_viewers[1]
    assert not bool(target.property("reviewPicked"))
    _click(qtbot, target.header.pick)

    assert bool(target.property("reviewPicked"))
    assert target.header.pick.isChecked()
    assert target.header.pick.text() == "Pick"
    assert not target.header.pick.autoRaise()
    assert TOKENS.selection in target.styleSheet()
    assert 'ImageViewer[reviewPicked="true"]' in target.styleSheet()
    assert TOKENS.selection in tile_style(False)
    assert TOKENS.selection in tile_style(True)
    assert f"border-left: 5px solid {TOKENS.accent}" in tile_style(True)

    window.next_comparison_page()
    assert documents[1].document_id in controller.picked_ids
    window.previous_comparison_page()

    restored = window.multi_compare_view.occupied_viewers[1]
    assert restored.document is documents[1]
    assert bool(restored.property("reviewPicked"))
    assert restored.header.pick.isChecked()
    assert restored.header.pick.text() == "Pick"
    window.close()


@pytest.mark.parametrize(
    "modifier",
    [
        Qt.KeyboardModifier.NoModifier,
        Qt.KeyboardModifier.ControlModifier,
        Qt.KeyboardModifier.ShiftModifier,
    ],
)
def test_viewer_drag_gestures_do_not_toggle_direct_pick(
    qtbot: object,
    tmp_path: Path,
    modifier: Qt.KeyboardModifier,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 2)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    window.show()

    viewer = window.multi_compare_view.occupied_viewers[0]
    viewport = viewer._graphics.viewport()
    start = viewport.rect().center()
    end = start + QPoint(24, 18)
    picked_before = controller.picked_ids

    # PySide6 6.4 QTest uses the modifier/key-state as the third positional
    # argument; the newer `modifier=` keyword is not accepted on owner Windows.
    qtbot.mousePress(  # type: ignore[attr-defined]
        viewport,
        Qt.MouseButton.LeftButton,
        modifier,
        start,
    )
    qtbot.mouseMove(viewport, end, 10)  # type: ignore[attr-defined]
    qtbot.mouseRelease(  # type: ignore[attr-defined]
        viewport,
        Qt.MouseButton.LeftButton,
        modifier,
        end,
    )

    assert controller.picked_ids == picked_before
    assert not controller.active
    assert not viewer.header.pick.isChecked()
    assert not bool(viewer.property("reviewPicked"))
    window.close()


def test_keep_selection_updates_files_selection_and_first_result_is_active(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 5)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)

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
