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


def _production_window(
    qtbot: object,
) -> tuple[MainWindow, ReviewSelectionController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window, window.review_selection_controller


def _register_and_select(
    window: MainWindow,
    documents: list[ImageDocument],
) -> None:
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])


def _pick_document(
    qtbot: object,
    window: MainWindow,
    document: ImageDocument,
) -> None:
    viewer = next(
        viewer
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.presented_document is document
    )
    qtbot.mouseClick(  # type: ignore[attr-defined]
        viewer.header.pick,
        Qt.MouseButton.LeftButton,
    )


def _activate_difference(
    window: MainWindow,
    pair: tuple[ImageDocument, ImageDocument],
    monkeypatch: pytest.MonkeyPatch,
) -> ImageDocument:
    for selector, document in (
        (window.difference_panel.a_selector, pair[0]),
        (window.difference_panel.b_selector, pair[1]),
    ):
        index = selector.findData(document.document_id)
        assert index >= 0
        selector.setCurrentIndex(index)

    source_a = pair[0].source
    source_b = pair[1].source
    assert source_a is not None and source_b is not None
    numerical = np.abs(source_a.astype(np.int16) - source_b.astype(np.int16))
    preview = np.clip(numerical, 0, 255).astype(np.uint8)
    title = f"Absolute [All]: {pair[0].display_name} vs {pair[1].display_name}"
    monkeypatch.setattr(
        window.difference_panel,
        "calculate_difference",
        lambda: None,
    )
    window._difference_panel_ready(title, numerical, preview)
    difference = window._difference_document
    assert difference is not None
    assert window._difference_source_ids == (
        pair[0].document_id,
        pair[1].document_id,
    )
    assert window.diff_action.isChecked()
    assert window.diff_action.isEnabled()
    return difference


def _selected_ids(window: MainWindow) -> list[str]:
    return [document.document_id for document in window.selected_documents]


def test_difference_is_derived_and_uses_local_slot_presentation(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 3)
    window, _controller = _production_window(qtbot)
    _register_and_select(window, documents)

    difference = _activate_difference(
        window,
        (documents[0], documents[1]),
        monkeypatch,
    )
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
    assert difference_viewer.header.difference_prefix.text() == "Absolute [All]:"
    assert difference_viewer.header.difference_a_badge.text() == "1"
    assert difference_viewer.header.difference_b_badge.text() == "2"
    assert difference_viewer.header.difference_a_name.isHidden()
    assert difference_viewer.header.difference_b_name.isHidden()

    assert source_viewers
    assert all(not viewer.header.pick.isHidden() for viewer in source_viewers)
    assert all(viewer.header.derived.isHidden() for viewer in source_viewers)
    assert all(
        viewer.header.difference_reference.isHidden() for viewer in source_viewers
    )
    assert "(P" not in window.difference_panel.a_selector.currentText()
    assert "(P" not in window.difference_panel.b_selector.currentText()
    window.close()


def test_pick_unpick_and_clear_leave_active_difference_unchanged(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 4)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    difference = _activate_difference(
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
    assert _selected_ids(window) == [document.document_id for document in documents]
    window.close()


@pytest.mark.parametrize("selected_count", [4, 8])
def test_keep_always_resets_active_difference_even_when_both_sources_are_kept(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selected_count: int,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, selected_count)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    _pick_document(qtbot, window, documents[0])
    _pick_document(qtbot, window, documents[1])
    generations = tuple(document.generation for document in documents)
    difference = _activate_difference(
        window,
        (documents[0], documents[1]),
        monkeypatch,
    )

    assert controller.keep_picked()

    assert _selected_ids(window) == [
        documents[0].document_id,
        documents[1].document_id,
    ]
    assert window._difference_document is None
    assert window._difference_source_ids is None
    assert not window.diff_action.isChecked()
    assert not window.diff_action.isEnabled()
    assert tuple(document.generation for document in documents) == generations
    assert all(
        viewer.presented_document is not difference
        for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_keep_preserves_generation_keyed_difference_cache(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 4)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    pair = (documents[0], documents[1])
    key = tuple(
        sorted(
            (
                (pair[0].document_id, pair[0].generation),
                (pair[1].document_id, pair[1].generation),
            )
        )
    )
    cached = CachedDifferenceMap(
        absolute=np.full((4, 4), 10, dtype=np.uint8),
        domain="native",
        data_range=255.0,
        channel_layout="GRAY",
        bayer_pattern=None,
    )
    assert window.difference_panel._map_cache.put(key, cached).stored
    generations = tuple(document.generation for document in documents)
    _pick_document(qtbot, window, pair[0])
    _pick_document(qtbot, window, pair[1])
    _activate_difference(window, pair, monkeypatch)

    assert controller.keep_picked()

    assert window.difference_panel._map_cache.peek(key) is cached
    assert tuple(document.generation for document in documents) == generations
    assert window._difference_document is None
    assert window._difference_source_ids is None
    assert not window.diff_action.isChecked()
    assert not window.diff_action.isEnabled()
    window.close()


def test_six_source_keep_restores_workspace_without_stale_derived_state(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 6)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    for document in documents[:3]:
        _pick_document(qtbot, window, document)

    difference = _activate_difference(
        window,
        (documents[0], documents[1]),
        monkeypatch,
    )
    assert window.central_stack.currentWidget() is window.viewer
    assert window.viewer.presented_document is difference
    assert window._six_image_diff_restore_state is not None
    assert not window.viewer.header.derived.isHidden()

    assert controller.keep_picked()

    expected = [document.document_id for document in documents[:3]]
    assert _selected_ids(window) == expected
    assert window._difference_document is None
    assert window._difference_source_ids is None
    assert window._six_image_diff_restore_state is None
    assert not window.diff_action.isChecked()
    assert not window.diff_action.isEnabled()
    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert window.viewer.presented_document is not difference
    assert window.viewer.header.derived.isHidden()
    assert window.viewer.header.difference_reference.isHidden()
    assert all(
        viewer.presented_document is not difference
        for viewer in window.multi_compare_view.occupied_viewers
    )
    assert all(
        viewer.header.derived.isHidden()
        for viewer in window.multi_compare_view.occupied_viewers
    )
    assert all(
        not viewer.header.pick.isHidden()
        for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()
