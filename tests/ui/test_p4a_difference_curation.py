from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QAbstractButton

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.difference_cache import CachedDifferenceMap
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.review_selection import ReviewSelectionController


def _ready_documents(tmp_path: Path, count: int) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((4, 4), index * 10, dtype=np.uint8),
            f"image{index + 1:02d}.png",
            source_path=tmp_path / f"image{index + 1:02d}.png",
        )
        for index in range(count)
    ]


def _production_window(qtbot: object) -> tuple[MainWindow, ReviewSelectionController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window, window.review_selection_controller


def _register_and_select(
    window: MainWindow,
    documents: list[ImageDocument],
    *,
    selected_count: int | None = None,
) -> None:
    for document in documents:
        window.add_document(document, select=False)
    selected = documents if selected_count is None else documents[:selected_count]
    window._select_document_ids([document.document_id for document in selected])


def _pick_document(qtbot: object, window: MainWindow, document: ImageDocument) -> None:
    viewer = next(
        viewer
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.presented_document is document
    )
    assert not viewer.header.pick.isHidden()
    qtbot.mouseClick(viewer.header.pick, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]


def _activate_difference(
    window: MainWindow,
    pair: tuple[ImageDocument, ImageDocument],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ImageDocument, list[str]]:
    numerical = np.abs(
        pair[0].source.astype(np.int16) - pair[1].source.astype(np.int16)  # type: ignore[union-attr]
    )
    preview = np.clip(numerical, 0, 255).astype(np.uint8)
    title = f"Difference: {pair[0].display_name} vs {pair[1].display_name}"
    cached = (title, numerical, preview)
    calculate_calls: list[str] = []
    monkeypatch.setattr(window.difference_panel, "selected_documents", lambda: pair)
    monkeypatch.setattr(window.difference_panel, "cached_display_for_current", lambda: cached)
    monkeypatch.setattr(
        window.difference_panel,
        "calculate_difference",
        lambda: calculate_calls.append("calculate"),
    )

    window._difference_panel_ready(*cached)

    difference = window._difference_document
    assert difference is not None
    assert window._difference_source_ids == (pair[0].document_id, pair[1].document_id)
    assert window.diff_action.isChecked()
    return difference, calculate_calls


def _selected_ids(window: MainWindow) -> list[str]:
    return [document.document_id for document in window.selected_documents]


def test_difference_tile_is_derived_while_source_tiles_remain_pickable(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 3)
    window, _controller = _production_window(qtbot)
    _register_and_select(window, documents)

    difference, _calls = _activate_difference(window, (documents[0], documents[1]), monkeypatch)
    difference_viewer = next(
        viewer
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.presented_document is difference
    )
    source_viewers = [
        viewer
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.presented_document in documents
    ]

    assert difference_viewer.header.pick.isHidden()
    assert not difference_viewer.header.derived.isHidden()
    assert difference_viewer.header.derived.text() == "Derived"
    assert not isinstance(difference_viewer.header.derived, QAbstractButton)
    assert difference_viewer.header.derived.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert (
        difference_viewer.header.derived.textInteractionFlags()
        == Qt.TextInteractionFlag.NoTextInteraction
    )
    assert documents[0].display_name in difference_viewer.header.derived.toolTip()
    assert documents[1].display_name in difference_viewer.header.derived.toolTip()
    assert difference_viewer.header.pick.width() == difference_viewer.header.derived.width()
    assert source_viewers
    assert all(not viewer.header.pick.isHidden() for viewer in source_viewers)
    assert all(viewer.header.derived.isHidden() for viewer in source_viewers)
    window.close()


@pytest.mark.parametrize(
    ("kept_indices", "difference_survives"),
    [
        ((0, 1), True),
        ((0, 2), False),
        ((1, 2), False),
        ((2, 3, 4), False),
    ],
)
def test_keep_selection_reconciles_difference_by_provenance_not_selected_count(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kept_indices: tuple[int, ...],
    difference_survives: bool,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 5)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    for index in kept_indices:
        _pick_document(qtbot, window, documents[index])

    difference, calculate_calls = _activate_difference(
        window,
        (documents[0], documents[1]),
        monkeypatch,
    )
    expected = [documents[index].document_id for index in kept_indices]

    assert controller.keep_picked()

    assert _selected_ids(window) == expected
    assert [
        document.document_id for document in window.current_comparison_documents()
    ] == expected
    assert window.diff_action.isChecked() is difference_survives
    if difference_survives:
        assert window._difference_document is difference
        assert window._difference_source_ids == (
            documents[0].document_id,
            documents[1].document_id,
        )
        assert calculate_calls == []
    else:
        assert window._difference_document is None
        assert window._difference_source_ids is None
    window.close()


def test_pick_unpick_and_clear_do_not_reconcile_active_difference(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 4)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    difference, calculate_calls = _activate_difference(
        window,
        (documents[0], documents[1]),
        monkeypatch,
    )
    provenance = window._difference_source_ids

    _pick_document(qtbot, window, documents[0])
    _pick_document(qtbot, window, documents[0])
    _pick_document(qtbot, window, documents[2])
    controller.clear_picks()

    assert window.diff_action.isChecked()
    assert window._difference_document is difference
    assert window._difference_source_ids == provenance
    assert calculate_calls == []
    assert _selected_ids(window) == [document.document_id for document in documents]
    window.close()


def test_invalid_keep_does_not_own_or_purge_difference_cache(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 7)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents, selected_count=5)
    generations = tuple(document.generation for document in documents)

    unrelated_key = (
        (documents[5].document_id, documents[5].generation),
        (documents[6].document_id, documents[6].generation),
    )
    unrelated_value = CachedDifferenceMap(
        absolute=np.ones((4, 4), dtype=np.uint8),
        domain="native",
        data_range=255.0,
        channel_layout="GRAY",
        bayer_pattern=None,
    )
    put_result = window.difference_panel.difference_cache.put(unrelated_key, unrelated_value)
    assert put_result.stored
    keys_before = window.difference_panel.difference_cache.keys()

    for index in (2, 3, 4):
        _pick_document(qtbot, window, documents[index])
    _difference, _calls = _activate_difference(
        window,
        (documents[0], documents[1]),
        monkeypatch,
    )

    assert controller.keep_picked()

    assert not window.diff_action.isChecked()
    assert window.difference_panel.difference_cache.keys() == keys_before
    assert window.difference_panel.difference_cache.peek(unrelated_key) is unrelated_value
    assert tuple(document.generation for document in documents) == generations
    window.close()


def test_invalid_keep_synchronizes_files_active_current_index_and_page(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 5)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    for index in (2, 3, 4):
        _pick_document(qtbot, window, documents[index])
    difference, _calls = _activate_difference(
        window,
        (documents[0], documents[1]),
        monkeypatch,
    )

    assert controller.keep_picked()

    expected = [documents[index].document_id for index in (2, 3, 4)]
    assert _selected_ids(window) == expected
    assert [
        document.document_id for document in window.current_comparison_documents()
    ] == expected
    files_selected = {
        str(item.data(0, Qt.ItemDataRole.UserRole))
        for item in window.document_list.selected_document_items()
    }
    assert files_selected == set(expected)
    active_items = [
        item
        for item in window.document_list.document_items()
        if bool(item.data(0, window.document_list.ACTIVE_ROLE))
    ]
    assert len(active_items) == 1
    active_id = str(active_items[0].data(0, Qt.ItemDataRole.UserRole))
    assert active_id == window._active_document_id
    assert active_id in expected
    assert 0 <= window._current_index < len(window.selected_documents)
    assert window.selected_documents[window._current_index].document_id == active_id
    assert all(
        viewer.presented_document is not difference
        for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_six_source_difference_keep_uses_pr32_teardown_and_leaves_no_stale_derived_view(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 6)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    for index in (2, 3, 4):
        _pick_document(qtbot, window, documents[index])

    difference, _calls = _activate_difference(
        window,
        (documents[0], documents[1]),
        monkeypatch,
    )
    assert window.central_stack.currentWidget() is window.viewer
    assert window.viewer.presented_document is difference
    assert not window.viewer.header.derived.isHidden()
    assert window._six_image_diff_restore_state is not None

    assert controller.keep_picked()

    expected = [documents[index].document_id for index in (2, 3, 4)]
    assert _selected_ids(window) == expected
    assert not window.diff_action.isChecked()
    assert window._difference_document is None
    assert window._difference_source_ids is None
    assert window._six_image_diff_restore_state is None
    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert window.viewer.presented_document is not difference
    assert all(
        viewer.presented_document is not difference
        for viewer in window.multi_compare_view.occupied_viewers
    )
    assert window._active_document_id in expected
    assert [
        document.document_id for document in window.current_comparison_documents()
    ] == expected
    window.close()
