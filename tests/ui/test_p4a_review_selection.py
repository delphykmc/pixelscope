from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QItemSelectionModel, QSettings, Qt

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import COMPARISON_PAGE_SIZE, MainWindow
from pixelscope.core.channel_views import split_document_channels
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.review_selection import ReviewSelectionController


def _ready_documents(tmp_path: Path, count: int) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((4, 4), index, dtype=np.uint8),
            f"image{index + 1:02d}.png",
            source_path=tmp_path / f"image{index + 1:02d}.png",
        )
        for index in range(count)
    ]


def _pending_documents(tmp_path: Path, count: int) -> list[ImageDocument]:
    return [
        ImageDocument.pending_document(tmp_path / f"image{index + 1:02d}.png")
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


def _wait_until(qtbot: object, callback: object) -> None:
    qtbot.waitUntil(callback)  # type: ignore[attr-defined]


def test_review_inactive_preserves_tile_activation_and_hides_pick_affordance(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 2)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    window.show()

    first, second = window.multi_compare_view.occupied_viewers
    assert not controller.active
    assert first.header.pick.isHidden()
    assert second.header.pick.isHidden()

    first_active = window._active_document_id
    _click(qtbot, second._graphics.viewport())
    _wait_until(qtbot, lambda: window._active_document_id == documents[1].document_id)
    assert window._active_document_id != first_active
    assert controller.picked_count == 0
    window.close()


def test_review_pick_is_explicit_and_independent_from_active_and_primary(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 3)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    window.show()

    assert controller.mode_button.isEnabled()
    _click(qtbot, controller.mode_button)
    assert controller.active
    assert controller.count_label.text() == "Picked 0"
    assert not controller.keep_button.isEnabled()

    viewers = window.multi_compare_view.occupied_viewers
    primary_id = window._focus_document_id
    active_id = window._active_document_id
    target = viewers[1]
    assert target.document is documents[1]
    assert not target.header.pick.isChecked()

    _click(qtbot, target.header.pick)

    assert controller.picked_ids == {documents[1].document_id}
    assert target.header.pick.isChecked()
    assert target.header.pick.text() == "Picked"
    assert controller.count_label.text() == "Picked 1"
    assert controller.keep_button.isEnabled()
    assert window._focus_document_id == primary_id
    assert window._active_document_id == active_id
    window.close()


def test_clear_and_cancel_leave_selected_page_active_and_primary_unchanged(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 15)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    window.next_comparison_page()
    window._set_focus_document(documents[7])
    window._set_active_document(documents[8])
    selected_before = tuple(document.document_id for document in window.selected_documents)
    page_before = window._page_start
    active_before = window._active_document_id
    primary_before = window._focus_document_id

    controller.enter_review()
    _click(qtbot, window.multi_compare_view.occupied_viewers[0].header.pick)
    controller.clear_picks()
    assert controller.picked_count == 0
    assert not controller.keep_button.isEnabled()

    controller.cancel_review()

    assert not controller.active
    assert tuple(document.document_id for document in window.selected_documents) == selected_before
    assert window._page_start == page_before
    assert window._active_document_id == active_before
    assert window._focus_document_id == primary_before
    window.close()


@pytest.mark.parametrize("count", [1, 2, 6, 7, 15, 50])
def test_review_entry_does_not_change_selected_or_current_page(
    qtbot: object,
    tmp_path: Path,
    count: int,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, count)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    selected_before = tuple(document.document_id for document in window.selected_documents)
    page_before = tuple(
        document.document_id for document in window.current_comparison_documents()
    )

    assert controller.enter_review()

    assert tuple(document.document_id for document in window.selected_documents) == selected_before
    assert (
        tuple(document.document_id for document in window.current_comparison_documents())
        == page_before
    )
    assert controller.state.baseline_selected_ids == selected_before
    window.close()


def test_seven_images_preserve_picks_across_pages(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 7)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    controller.enter_review()

    _click(qtbot, window.multi_compare_view.occupied_viewers[1].header.pick)
    window.next_comparison_page()
    assert window._page_start == COMPARISON_PAGE_SIZE
    _click(qtbot, window.multi_compare_view.occupied_viewers[0].header.pick)

    assert controller.picked_ids == {documents[1].document_id, documents[6].document_id}
    window.previous_comparison_page()
    assert window.multi_compare_view.occupied_viewers[1].header.pick.isChecked()
    assert tuple(document.document_id for document in window.selected_documents) == tuple(
        document.document_id for document in documents
    )
    window.close()


def test_fifteen_images_keep_first_middle_and_final_page_picks(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 15)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    controller.enter_review()

    _click(qtbot, window.multi_compare_view.occupied_viewers[1].header.pick)
    window.next_comparison_page()
    _click(qtbot, window.multi_compare_view.occupied_viewers[2].header.pick)
    window.next_comparison_page()
    _click(qtbot, window.multi_compare_view.occupied_viewers[2].header.pick)

    assert controller.picked_ids == {
        documents[1].document_id,
        documents[8].document_id,
        documents[14].document_id,
    }
    assert controller.count_label.text() == "Picked 3"
    window.close()


def test_keep_picked_filters_baseline_order_and_keeps_nonpicked_registered(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 8)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    controller.enter_review()

    # Pick out of order: H -> B -> E. Apply must preserve baseline order B, E, H.
    window.next_comparison_page()
    _click(qtbot, window.multi_compare_view.occupied_viewers[1].header.pick)
    window.previous_comparison_page()
    _click(qtbot, window.multi_compare_view.occupied_viewers[1].header.pick)
    _click(qtbot, window.multi_compare_view.occupied_viewers[4].header.pick)

    assert controller.keep_picked()

    expected = [
        documents[1].document_id,
        documents[4].document_id,
        documents[7].document_id,
    ]
    assert [document.document_id for document in window.selected_documents] == expected
    assert [
        document.document_id for document in window.current_comparison_documents()
    ] == expected
    assert set(window.documents) == {document.document_id for document in documents}
    assert not controller.active
    assert controller.picked_count == 0
    assert [
        viewer.document.document_id
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    ] == expected
    window.close()


def test_zero_pick_keep_is_disabled_and_cannot_clear_selected(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 4)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    selected_before = tuple(document.document_id for document in window.selected_documents)
    controller.enter_review()

    assert controller.picked_count == 0
    assert not controller.keep_button.isEnabled()
    assert not controller.keep_picked()
    assert tuple(document.document_id for document in window.selected_documents) == selected_before
    assert controller.active
    window.close()


def test_pick_unpick_does_not_load_render_analyze_or_mutate_source_generation(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 4)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents)
    generations = tuple(document.generation for document in documents)
    residency_before = window.residency_manager.used_bytes
    cache_before = (
        window.difference_panel._map_cache.used_bytes,
        len(window.difference_panel._metric_cache),
    )
    calls: list[str] = []
    monkeypatch.setattr(window, "_ensure_loaded", lambda _document: calls.append("load"))
    monkeypatch.setattr(
        window,
        "_render_selection",
        lambda *args, **kwargs: calls.append("render"),
    )
    monkeypatch.setattr(
        window.comparison_analysis_panel,
        "set_documents",
        lambda *args, **kwargs: calls.append("statistics"),
    )
    monkeypatch.setattr(
        window.difference_panel,
        "set_documents",
        lambda *args, **kwargs: calls.append("difference"),
    )
    monkeypatch.setattr(
        window.line_profile_panel,
        "set_documents",
        lambda *args, **kwargs: calls.append("line"),
    )

    controller.enter_review()
    button = window.multi_compare_view.occupied_viewers[2].header.pick
    _click(qtbot, button)
    _click(qtbot, button)
    controller.clear_picks()

    assert calls == []
    assert tuple(document.generation for document in documents) == generations
    assert window.residency_manager.used_bytes == residency_before
    assert (
        window.difference_panel._map_cache.used_bytes,
        len(window.difference_panel._metric_cache),
    ) == cache_before
    window.close()


def test_fifty_image_review_picks_do_not_expand_load_protection_or_preload(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    QSettings().clear()
    documents = _pending_documents(tmp_path, 50)
    window, controller = _production_window(qtbot)
    requested: list[str] = []
    monkeypatch.setattr(
        window,
        "_ensure_loaded",
        lambda document: requested.append(document.document_id),
    )
    _register_and_select(window, documents)
    selected_ids = [document.document_id for document in documents]
    assert requested == selected_ids[:6]
    requested.clear()

    controller.enter_review()
    _click(qtbot, window.multi_compare_view.visible_viewers[0].header.pick)
    assert requested == []

    window.next_comparison_page()
    assert requested == selected_ids[6:12]
    requested.clear()
    _click(qtbot, window.multi_compare_view.visible_viewers[4].header.pick)
    assert requested == []

    window.next_comparison_page()
    assert requested == selected_ids[12:18]
    requested.clear()
    _click(qtbot, window.multi_compare_view.visible_viewers[2].header.pick)
    assert requested == []

    assert controller.picked_ids == {
        selected_ids[0],
        selected_ids[10],
        selected_ids[14],
    }
    protected = window._residency_protected_document_ids()
    assert not {selected_ids[0], selected_ids[10]}.intersection(protected)
    assert set(selected_ids[12:18]).issubset(protected)
    assert window.preload_controller.current_plan is None
    window.close()


def test_split_and_difference_derived_documents_are_not_pick_identities(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    source = ImageDocument.from_array(
        np.zeros((4, 4, 3), dtype=np.uint8),
        "rgb.png",
        source_path=tmp_path / "rgb.png",
    )
    window, controller = _production_window(qtbot)
    _register_and_select(window, [source])
    controller.enter_review()

    assert controller._pickable_document_id(source) == source.document_id
    for derived in split_document_channels(source):
        assert derived.document_id != source.document_id
        assert controller._pickable_document_id(derived) is None

    difference = ImageDocument.from_array(
        np.zeros((4, 4), dtype=np.uint8),
        "difference",
        channel_layout="DIFFERENCE",
    )
    assert controller._pickable_document_id(difference) is None
    window.close()


def test_external_programmatic_selected_replacement_cancels_review_then_applies_normally(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 8)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents[:6])
    controller.enter_review()
    _click(qtbot, window.multi_compare_view.occupied_viewers[1].header.pick)

    replacement = [documents[6].document_id, documents[7].document_id]
    for document in documents[6:]:
        window.add_document(document, select=False)
    window._select_document_ids(replacement)

    assert not controller.active
    assert controller.picked_count == 0
    assert [document.document_id for document in window.selected_documents] == replacement
    assert all(viewer.header.pick.isHidden() for viewer in window.multi_compare_view.viewers)
    window.close()


def test_files_selection_change_cancels_review_without_stale_pick_state(
    qtbot: object,
    tmp_path: Path,
) -> None:
    QSettings().clear()
    documents = _ready_documents(tmp_path, 4)
    window, controller = _production_window(qtbot)
    _register_and_select(window, documents[:3])
    window.add_document(documents[3], select=False)
    controller.enter_review()
    _click(qtbot, window.multi_compare_view.occupied_viewers[0].header.pick)

    target_item = next(
        item
        for item in window.document_list.document_items()
        if str(item.data(0, Qt.ItemDataRole.UserRole)) == documents[3].document_id
    )
    window.document_list.setCurrentItem(
        target_item,
        0,
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )

    assert not controller.active
    assert controller.picked_count == 0
    assert [document.document_id for document in window.selected_documents] == [
        documents[3].document_id
    ]
    window.close()
