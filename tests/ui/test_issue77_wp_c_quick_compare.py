from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.quick_compare import QuickCompareController

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> tuple[MainWindow, QuickCompareController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.quick_compare_controller
    assert isinstance(controller, QuickCompareController)
    return window, controller


def _document(name: str, value: int, tmp_path: Path) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((6, 8), value, dtype=np.uint8),
        name,
        source_path=tmp_path / name,
    )


def _add(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)


def _ids(window: MainWindow) -> list[str]:
    return [document.document_id for document in window.selected_documents]


def _wait_for_difference(
    qtbot: object,
    window: MainWindow,
    pair: tuple[str, str],
) -> None:
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_source_ids == pair and window.diff_action.isChecked(),
        timeout=5000,
    )


def test_sequential_quick_drop_is_additive_and_second_drop_calculates_difference(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 20, tmp_path)
    third = _document("c.png", 30, tmp_path)
    _add(window, [first, second, third])

    controller._apply_registered_drop([first.document_id])
    assert _ids(window) == [first.document_id]
    assert window._difference_source_ids is None

    controller._apply_registered_drop([second.document_id])
    _wait_for_difference(qtbot, window, (first.document_id, second.document_id))
    assert _ids(window) == [first.document_id, second.document_id]

    controller._apply_registered_drop([third.document_id])
    assert _ids(window) == [first.document_id, second.document_id, third.document_id]
    assert window._difference_source_ids == (first.document_id, second.document_id)
    window.close()


def test_two_file_batch_pairs_the_dropped_sources_without_retargeting_existing_difference(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [
        _document(f"{name}.png", value, tmp_path)
        for name, value in zip("abc", (1, 2, 3), strict=True)
    ]
    _add(window, documents)

    controller._apply_registered_drop([documents[0].document_id])
    controller._apply_registered_drop([documents[1].document_id, documents[2].document_id])
    _wait_for_difference(
        qtbot,
        window,
        (documents[1].document_id, documents[2].document_id),
    )
    assert _ids(window) == [document.document_id for document in documents]
    window.close()


def test_three_file_batch_is_additive_without_automatic_difference(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [_document(f"{index}.png", index, tmp_path) for index in range(3)]
    _add(window, documents)

    controller._apply_registered_drop([document.document_id for document in documents])

    assert _ids(window) == [document.document_id for document in documents]
    assert window._difference_source_ids is None
    assert not window.diff_action.isChecked()
    window.close()


def test_ordinary_two_source_selection_remains_passive(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, _controller = _window(qtbot)
    first = _document("a.png", 1, tmp_path)
    second = _document("b.png", 2, tmp_path)
    _add(window, [first, second])

    window._select_document_ids([first.document_id, second.document_id])

    assert window._difference_source_ids is None
    assert not window.diff_action.isChecked()
    window.close()


def test_quick_compare_drop_target_is_limited_to_image_presentation_surface(
    qtbot: object,
) -> None:
    window, controller = _window(qtbot)

    assert controller._is_image_surface(window.central_stack)
    assert controller._is_image_surface(window.viewer._graphics.viewport())
    assert not controller._is_image_surface(window.document_list)
    window.close()


def test_three_view_defaults_equal_and_user_can_switch_focus_without_state_change(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [_document(f"{index}.png", index, tmp_path) for index in range(3)]
    _add(window, documents)
    window._select_document_ids([document.document_id for document in documents])
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    roi = RoiBounds(1, 1, 4, 3)
    line = LineSelection(0, 0, 5, 4)
    assert window._shared_roi_changed(roi)
    window._shared_line_changed(line)

    authority = (
        tuple(_ids(window)),
        window._focus_document_id,
        window._active_document_id,
        window._shared_roi,
        window._shared_line,
    )
    equal_geometry = window.multi_compare_view._fixed_geometry(3)
    assert equal_geometry == (
        ((0, 0, 1, 1), (0, 1, 1, 1), (0, 2, 1, 1)),
        (1,),
        (1, 1, 1),
    )
    assert controller.three_view_group.isVisible() == (
        window.central_stack.currentWidget() is window.multi_compare_view
    )

    controller.set_three_view_variant("Focus")

    assert window.multi_compare_view._fixed_geometry(3) == controller._original_fixed_geometry(3)
    assert authority == (
        tuple(_ids(window)),
        window._focus_document_id,
        window._active_document_id,
        window._shared_roi,
        window._shared_line,
    )
    window.close()


def test_three_view_difference_defaults_focus_and_other_geometries_are_unchanged(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 1, tmp_path)
    second = _document("b.png", 9, tmp_path)
    _add(window, [first, second])

    controller._apply_registered_drop([first.document_id, second.document_id])
    _wait_for_difference(qtbot, window, (first.document_id, second.document_id))

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.multi_compare_view._document_count == 3,
        timeout=3000,
    )
    assert controller._effective_three_view_variant() == "Focus"
    assert window.multi_compare_view._fixed_geometry(3) == controller._original_fixed_geometry(3)
    for count in (4, 5, 6):
        assert window.multi_compare_view._fixed_geometry(
            count
        ) == controller._original_fixed_geometry(count)
    window.close()


def test_hold_b_blinks_presentation_only_and_restores_reference(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 200, tmp_path)
    _add(window, [first, second])
    window._select_document_ids([first.document_id, second.document_id])
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    reference_viewer = controller._viewer_for_document(first.document_id)
    alternate_viewer = controller._viewer_for_document(second.document_id)
    assert reference_viewer is not None
    assert alternate_viewer is not None
    before_image = np.array(reference_viewer.image_item.image, copy=True)
    alternate_image = np.array(alternate_viewer.image_item.image, copy=True)
    before_range = reference_viewer.view_box.viewRange()
    authority = (
        tuple(_ids(window)),
        window._focus_document_id,
        window._active_document_id,
        window._difference_source_ids,
        window._shared_roi,
        window._shared_line,
    )

    assert controller._begin_blink()
    assert np.array_equal(reference_viewer.image_item.image, alternate_image)
    assert reference_viewer.document is first
    controller._end_blink()

    assert np.array_equal(reference_viewer.image_item.image, before_image)
    assert reference_viewer.view_box.viewRange() == before_range
    assert authority == (
        tuple(_ids(window)),
        window._focus_document_id,
        window._active_document_id,
        window._difference_source_ids,
        window._shared_roi,
        window._shared_line,
    )
    window.close()


def test_blink_is_safe_noop_for_three_sources_and_while_numeric_input_has_focus(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [_document(f"{index}.png", index, tmp_path) for index in range(3)]
    _add(window, documents)
    window._select_document_ids([documents[0].document_id, documents[1].document_id])
    window.show()
    window.activateWindow()
    QApplication.setActiveWindow(window)
    window.comparison_analysis_panel.roi_x_input.setFocus()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: QApplication.activeWindow() is window
        and window.comparison_analysis_panel.roi_x_input.hasFocus(),
        timeout=3000,
    )
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_B,
        Qt.KeyboardModifier.NoModifier,
        "b",
    )
    assert not controller.eventFilter(window.comparison_analysis_panel.roi_x_input, event)
    assert controller._blink_snapshot is None

    window._select_document_ids([document.document_id for document in documents])
    assert not controller._begin_blink()
    assert controller._blink_snapshot is None
    window.close()
