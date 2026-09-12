from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QMimeData, QPoint, Qt, QUrl
from PySide6.QtGui import QDragLeaveEvent, QDragMoveEvent

import pixelscope.ui.difference_panel as difference_panel_module
from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.quick_compare import QuickCompareController

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


class _InlinePool:
    """Run submitted workers immediately to exercise pre-return terminal races."""

    def start(self, worker: Any) -> None:
        worker.run()


def _window(qtbot: object) -> tuple[MainWindow, QuickCompareController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    controller = window.quick_compare_controller
    assert isinstance(controller, QuickCompareController)
    return window, controller


def _document(
    name: str,
    value: int,
    tmp_path: Path,
    *,
    shape: tuple[int, int] = (6, 8),
) -> ImageDocument:
    return ImageDocument.from_array(
        np.full(shape, value, dtype=np.uint8),
        name,
        source_path=tmp_path / name,
    )


def _add(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)


def _ids(window: MainWindow) -> list[str]:
    return [document.document_id for document in window.selected_documents]


def test_image_view_drag_move_keeps_proposed_action_accepted(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(tmp_path / "a.png"))])
    event = QDragMoveEvent(
        QPoint(8, 8),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    assert controller.eventFilter(window.viewer._graphics.viewport(), event)
    assert event.isAccepted()
    window.close()


def test_image_view_drag_leave_is_consumed_by_quick_compare_filter(
    qtbot: object,
) -> None:
    window, controller = _window(qtbot)
    event = QDragLeaveEvent()

    assert controller.eventFilter(window.viewer._graphics.viewport(), event)
    assert event.isAccepted()
    window.close()


def test_explicit_pair_freezes_repaint_but_keeps_two_source_state_updates(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 20, tmp_path)
    _add(window, [first, second])

    controller._apply_registered_drop([first.document_id])
    assert window.viewer.document is first

    monkeypatch.setattr(window.difference_panel, "calculate_difference", lambda: None)
    controller._apply_registered_drop([second.document_id])

    pair = (first.document_id, second.document_id)
    assert _ids(window) == [first.document_id, second.document_id]
    assert controller._deferred_difference_pair == pair
    assert not window.central_stack.updatesEnabled()
    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert window.multi_compare_view._document_count == 2

    controller._release_deferred_difference(pair)
    assert window.central_stack.updatesEnabled()
    assert window.multi_compare_view._document_count == 2
    window.close()


def test_successful_difference_releases_repaint_hold_with_three_tile_result(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 20, tmp_path)
    _add(window, [first, second])

    controller._apply_registered_drop([first.document_id])
    controller._apply_registered_drop([second.document_id])
    pair = (first.document_id, second.document_id)

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_source_ids == pair
        and window.central_stack.updatesEnabled()
        and window.multi_compare_view._document_count == 3,
        timeout=5000,
    )

    assert window.diff_action.isChecked()
    assert controller._deferred_difference_pair is None
    window.close()


def test_immediate_difference_map_failure_releases_deferred_repaint(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 20, tmp_path)
    _add(window, [first, second])

    def fail_map(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("injected map failure")

    monkeypatch.setattr(window.difference_panel, "_pool", _InlinePool())
    monkeypatch.setattr(difference_panel_module, "compact_absolute_difference", fail_map)
    controller._apply_registered_drop([first.document_id])
    controller._apply_registered_drop([second.document_id])

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.central_stack.updatesEnabled()
        and controller._deferred_difference_pair is None
        and window.difference_panel._worker is None,
        timeout=5000,
    )

    assert _ids(window) == [first.document_id, second.document_id]
    assert window._difference_source_ids is None
    assert window.multi_compare_view._document_count == 2
    window.close()


def test_immediate_difference_preview_failure_releases_deferred_repaint(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path)
    second = _document("b.png", 20, tmp_path)
    _add(window, [first, second])

    def fail_preview(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("injected preview failure")

    monkeypatch.setattr(window.difference_panel, "_pool", _InlinePool())
    monkeypatch.setattr(window.difference_panel, "_render_preview", fail_preview)
    controller._apply_registered_drop([first.document_id])
    controller._apply_registered_drop([second.document_id])

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.central_stack.updatesEnabled()
        and controller._deferred_difference_pair is None
        and window.difference_panel._preview_worker is None,
        timeout=5000,
    )

    assert _ids(window) == [first.document_id, second.document_id]
    assert window._difference_source_ids is None
    assert window.multi_compare_view._document_count == 2
    window.close()


def test_incompatible_difference_releases_deferred_source_presentation(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    first = _document("a.png", 10, tmp_path, shape=(6, 8))
    second = _document("b.png", 20, tmp_path, shape=(6, 9))
    _add(window, [first, second])

    controller._apply_registered_drop([first.document_id])
    controller._apply_registered_drop([second.document_id])

    assert _ids(window) == [first.document_id, second.document_id]
    assert window._difference_source_ids is None
    assert window.multi_compare_view._document_count == 2
    assert controller._deferred_difference_pair is None
    assert window.central_stack.updatesEnabled()
    window.close()


def test_registered_selected_sources_still_form_sequential_quick_compare_pair(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [
        _document(f"{name}.png", value, tmp_path)
        for name, value in zip("abc", (10, 20, 30), strict=True)
    ]
    _add(window, documents)
    window._select_document_ids([document.document_id for document in documents])

    controller._apply_registered_drop([documents[0].document_id])
    assert window._difference_source_ids is None

    controller._apply_registered_drop([documents[1].document_id])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_source_ids
        == (documents[0].document_id, documents[1].document_id),
        timeout=5000,
    )

    assert _ids(window) == [document.document_id for document in documents]
    window.close()


def test_files_single_add_reveals_new_comparison_page(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, _controller = _window(qtbot)
    documents = [_document(f"image-{index}.png", index, tmp_path) for index in range(7)]
    _add(window, documents)
    window._select_document_ids([document.document_id for document in documents[:6]])

    added = documents[6]
    item = window.document_list.document_item(added.document_id)
    assert item is not None
    item.setSelected(True)

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._page_start == 6
        and [document.document_id for document in window.current_comparison_documents()]
        == [added.document_id],
        timeout=3000,
    )
    assert _ids(window) == [document.document_id for document in documents]
    window.close()


def test_quick_compare_add_reveals_new_comparison_page(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [_document(f"image-{index}.png", index, tmp_path) for index in range(7)]
    _add(window, documents)
    window._select_document_ids([document.document_id for document in documents[:6]])

    controller._apply_registered_drop([documents[6].document_id])

    assert window._page_start == 6
    assert [document.document_id for document in window.current_comparison_documents()] == [
        documents[6].document_id
    ]
    assert window._difference_source_ids is None
    assert _ids(window) == [document.document_id for document in documents]
    window.close()


def test_bulk_selection_reconstruction_keeps_first_comparison_page(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, _controller = _window(qtbot)
    documents = [_document(f"image-{index}.png", index, tmp_path) for index in range(7)]
    _add(window, documents)

    window._select_document_ids([document.document_id for document in documents])

    assert window._page_start == 0
    assert [document.document_id for document in window.current_comparison_documents()] == [
        document.document_id for document in documents[:6]
    ]
    window.close()


def test_multi_item_files_add_does_not_turn_bulk_selection_into_page_follow(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, _controller = _window(qtbot)
    documents = [_document(f"image-{index}.png", index, tmp_path) for index in range(7)]
    _add(window, documents)
    window._select_document_ids([documents[0].document_id])

    window.document_list.selectAll()

    assert window._page_start == 0
    assert [document.document_id for document in window.current_comparison_documents()] == [
        document.document_id for document in documents[:6]
    ]
    window.close()


def test_initial_quick_compare_batch_starts_on_first_page(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    documents = [_document(f"image-{index}.png", index, tmp_path) for index in range(10)]
    _add(window, documents)
    window._current_index = 9
    window._page_start = 6

    controller._apply_registered_drop([document.document_id for document in documents])

    assert window._current_index == 0
    assert window._page_start == 0
    assert [document.document_id for document in window.current_comparison_documents()] == [
        document.document_id for document in documents[:6]
    ]
    assert _ids(window) == [document.document_id for document in documents]
    window.close()


def test_initial_files_drop_starts_on_first_page(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, _controller = _window(qtbot)
    registration = window.large_folder_registration_controller
    paths = [tmp_path / f"image-{index}.png" for index in range(10)]
    for index, path in enumerate(paths):
        assert cv2.imwrite(str(path), np.full((6, 8), index, dtype=np.uint8))
    window._current_index = 9
    window._page_start = 6

    window._handle_dropped_paths(paths)
    qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)  # type: ignore[attr-defined]

    selected = window.selected_documents
    assert window._current_index == 0
    assert window._page_start == 0
    assert [document.source_path for document in selected] == [
        path.resolve() for path in paths
    ]
    assert window.current_comparison_documents() == selected[:6]
    window.close()


def test_files_drop_extends_existing_selection_and_reveals_last_addition(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, _controller = _window(qtbot)
    registration = window.large_folder_registration_controller
    paths = [tmp_path / f"image-{index}.png" for index in range(10)]
    for index, path in enumerate(paths):
        assert cv2.imwrite(str(path), np.full((6, 8), index, dtype=np.uint8))

    window._handle_dropped_paths(paths[:3])
    qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)  # type: ignore[attr-defined]
    assert [document.source_path for document in window.selected_documents] == [
        path.resolve() for path in paths[:3]
    ]

    window._handle_dropped_paths(paths[3:])
    qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)  # type: ignore[attr-defined]

    selected = window.selected_documents
    assert [document.source_path for document in selected] == [
        path.resolve() for path in paths
    ]
    assert window._page_start == 6
    assert window.current_comparison_documents() == selected[6:]
    window.close()
