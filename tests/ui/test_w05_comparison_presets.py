"""W05 composed command-bar and Difference safety regression tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_presets import ComparisonPair, ComparisonPreset
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.quick_compare import ComparisonPresetController

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> tuple[MainWindow, ComparisonPresetController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    controller = window.quick_compare_controller.comparison_presets
    assert isinstance(controller, ComparisonPresetController)
    return window, controller


def _sources(window: MainWindow, root: Path, count: int) -> list[ImageDocument]:
    documents = [
        ImageDocument.from_array(
            np.full((48, 64), 20 + index, dtype=np.uint8),
            "same.png",
            source_path=root / str(index) / "same.png",
        )
        for index in range(count)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    return documents


@pytest.mark.parametrize("count", [2, 4, 6])
def test_original_presets_leave_files_selected_and_current_page_untouched(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, count)
    original_page = tuple(doc.document_id for doc in window.current_comparison_documents())
    selected = tuple(doc.document_id for doc in window.selected_documents)
    assert controller.pair == ComparisonPair(docs[0].document_id, docs[1].document_id)

    def no_calculate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("W05 preset must never calculate Difference")

    monkeypatch.setattr(window.difference_panel, "calculate_difference", no_calculate)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    assert controller.preset is ComparisonPreset.ORIGINAL_2
    assert [
        v.document.document_id
        for v in window.multi_compare_view.occupied_viewers
        if v.document is not None
    ] == [doc.document_id for doc in docs[:2]]
    if count >= 4:
        controller.set_preset(ComparisonPreset.ORIGINAL_4)
        assert [
            v.document.document_id
            for v in window.multi_compare_view.occupied_viewers
            if v.document is not None
        ] == [doc.document_id for doc in docs[:4]]
    else:
        controller.set_preset(ComparisonPreset.ORIGINAL_4)
        assert controller.preset is ComparisonPreset.ORIGINAL_2
    assert tuple(doc.document_id for doc in window.selected_documents) == selected
    assert tuple(doc.document_id for doc in window.current_comparison_documents()) == original_page
    controller.set_preset(ComparisonPreset.WORKSPACE)
    assert controller.preset is ComparisonPreset.WORKSPACE
    window.close()


def test_reference_remains_fixed_as_target_changes_in_original_four(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 4)
    controller.set_preset(ComparisonPreset.ORIGINAL_4)
    ref_id = docs[0].document_id

    def no_calculate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Target changes must not calculate Difference")

    monkeypatch.setattr(window.difference_panel, "calculate_difference", no_calculate)
    for target in docs[1:]:
        controller._change_pair(target_id=target.document_id)
        assert controller.pair == ComparisonPair(ref_id, target.document_id)
        pair = window.difference_panel.selected_documents()
        assert pair is not None
        assert (pair[0].document_id, pair[1].document_id) == (
            ref_id,
            target.document_id,
        )
        badges = {
            viewer.document.document_id: viewer.header.badge.text()
            for viewer in window.multi_compare_view.occupied_viewers
            if viewer.document is not None
        }
        assert badges[ref_id] == "A1"
        assert badges[target.document_id] == f"B{docs.index(target) + 1}"
    assert len(window.selected_documents) == 4
    window.close()


def test_diff_preset_does_not_display_missing_or_unrelated_map(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 2)

    def no_calculate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Switching presets cannot invoke Difference Calculate")

    monkeypatch.setattr(window.difference_panel, "calculate_difference", no_calculate)
    controller.set_preset(ComparisonPreset.AB_DIFF)
    assert controller.status_label.text() == "Not Calculated".title()
    assert all(
        viewer.document is not window._difference_document
        for viewer in window.multi_compare_view.occupied_viewers
    )
    controller.set_preset(ComparisonPreset.DIFF_FOCUS)
    assert window._difference_document is None
    assert controller.pair == ComparisonPair(docs[0].document_id, docs[1].document_id)
    window.close()


def test_cached_pair_can_be_displayed_only_after_identity_match(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 4)
    panel = window.difference_panel
    numerical = np.full((48, 64), 25, dtype=np.uint8)
    preview = numerical.copy()
    correct_key = panel._cache_key()
    assert correct_key is not None

    monkeypatch.setattr(panel, "has_cached_map", lambda: panel._cache_key() == correct_key)
    monkeypatch.setattr(
        panel,
        "cached_display_for_current",
        lambda: ("Cached Difference", numerical, preview)
        if panel._cache_key() == correct_key
        else None,
    )
    monkeypatch.setattr(
        panel,
        "calculate_difference",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("preset calculated Difference")
        ),
    )
    controller.set_preset(ComparisonPreset.AB_DIFF)
    assert controller.status_label.text() == "Cached"
    assert any(
        viewer.document is window._difference_document
        for viewer in window.multi_compare_view.occupied_viewers
    )
    # Different target: the previous cached map is never shown for C.
    controller._change_pair(target_id=docs[2].document_id)
    assert controller.status_label.text() == "Not Calculated".title()
    assert all(
        viewer.document is not window._difference_document
        for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_changed_page_generation_revokes_temporary_preset(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 6)
    controller.set_preset(ComparisonPreset.ORIGINAL_4)
    docs[0].generation += 1
    window._render_selection(preserve_view=True)
    assert controller.preset is ComparisonPreset.WORKSPACE
    window.close()


def test_closing_preset_controller_rejects_late_callbacks(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    _sources(window, tmp_path, 2)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    window.close()
    assert controller._closed
    controller.on_workspace_rendered()


def test_sync_off_blocks_preset_without_mutating_selection(
    qtbot: object, tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 4)
    page = tuple(doc.document_id for doc in window.current_comparison_documents())
    window.multi_compare_view.set_sync_enabled(False)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    assert controller.preset is ComparisonPreset.WORKSPACE
    assert tuple(doc.document_id for doc in window.selected_documents) == page
    assert window._difference_document is None
    window.multi_compare_view.set_sync_enabled(True)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    assert controller.preset is ComparisonPreset.ORIGINAL_2
    window.multi_compare_view.set_sync_enabled(False)
    controller.set_preset(ComparisonPreset.WORKSPACE)
    assert controller.preset is ComparisonPreset.ORIGINAL_2
    window.close()


def test_page_two_presets_bind_exact_runtime_documents(
    qtbot: object, tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 8)
    window.next_comparison_page()
    current = window.current_comparison_documents()
    assert tuple(doc.document_id for doc in current) == (
        docs[6].document_id, docs[7].document_id,
    )
    assert controller.pair == ComparisonPair(docs[6].document_id, docs[7].document_id)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    presented = [
        v.document for v in window.multi_compare_view.occupied_viewers
        if v.document is not None
    ]
    assert presented == current
    assert len(window.selected_documents) == 8
    window.close()
