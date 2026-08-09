from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QFileDialog

from pixelscope.app.main_window import COMPARISON_PAGE_SIZE, MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.residency import ResidencyManager
from pixelscope.core.roi import RoiBounds
from pixelscope.io.path_discovery import ImageInput
from pixelscope.ui.display_gain import install_display_gain_control


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    settings = QSettings()
    settings.clear()
    settings.sync()


def _ready_documents(tmp_path: Path, count: int) -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((4, 4), index, dtype=np.uint8),
            f"image{index + 1:02d}.png",
            source_path=tmp_path / f"folder-{index:02d}" / f"image{index + 1:02d}.png",
        )
        for index in range(count)
    ]


def _select_ready_documents(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])


def _visible_source_ids(window: MainWindow) -> list[str]:
    return [
        viewer.document.document_id
        for viewer in window.multi_compare_view.visible_viewers
        if viewer.document is not None
    ]


def test_selected_at_most_six_shows_stable_single_page_information(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 5)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    _select_ready_documents(window, documents)

    assert window.current_comparison_documents() == documents
    assert window._page_start == 0
    assert not window.comparison_page_group.isHidden()
    assert window.comparison_page_label.text() == "Page 01 / 01 · 1–5 of 5"
    assert window.previous_comparison_page_button.isHidden()
    assert window.next_comparison_page_button.isHidden()
    label_width = window.comparison_page_label.width()
    state_before = window._comparison_page_controls_state
    window._update_comparison_page_controls()
    assert window._comparison_page_controls_state == state_before
    assert window.comparison_page_label.width() == label_width
    assert window.multi_compare_view.capacity == 6
    assert window.multi_compare_view._arranged_count == 5
    window.close()


def test_fifteen_selected_documents_page_without_changing_selection(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 15)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_ready_documents(window, documents)
    selected_ids = tuple(document.document_id for document in window.selected_documents)

    assert window.current_comparison_documents() == documents[:6]
    assert window.comparison_page_label.text() == "Page 01 / 03 · 1–6 of 15"
    assert not window.previous_comparison_page_button.isEnabled()
    assert window.next_comparison_page_button.isEnabled()
    assert _visible_source_ids(window) == [document.document_id for document in documents[:6]]
    assert [viewer._slot for viewer in window.multi_compare_view.occupied_viewers] == list(
        range(1, COMPARISON_PAGE_SIZE + 1)
    )

    window.next_comparison_page()
    assert tuple(document.document_id for document in window.selected_documents) == selected_ids
    assert window.current_comparison_documents() == documents[6:12]
    assert window.comparison_page_label.text() == "Page 02 / 03 · 7–12 of 15"
    assert _visible_source_ids(window) == [document.document_id for document in documents[6:12]]
    assert [viewer._slot for viewer in window.multi_compare_view.occupied_viewers] == list(
        range(1, COMPARISON_PAGE_SIZE + 1)
    )

    window.next_comparison_page()
    assert tuple(document.document_id for document in window.selected_documents) == selected_ids
    assert window.current_comparison_documents() == documents[12:15]
    assert window.comparison_page_label.text() == "Page 03 / 03 · 13–15 of 15"
    assert window.multi_compare_view.capacity == COMPARISON_PAGE_SIZE
    assert window.multi_compare_view._arranged_count == COMPARISON_PAGE_SIZE
    assert _visible_source_ids(window) == [document.document_id for document in documents[12:15]]
    assert [viewer.document for viewer in window.multi_compare_view.visible_viewers[3:]] == [
        None,
        None,
        None,
    ]
    assert [viewer._slot for viewer in window.multi_compare_view.occupied_viewers] == [1, 2, 3]
    last_start = window._page_start
    window.next_comparison_page()
    assert window._page_start == last_start
    assert "last Comparison Page" in window.statusBar().currentMessage()

    window.previous_comparison_page()
    assert window.current_comparison_documents() == documents[6:12]
    window.previous_comparison_page()
    assert window.current_comparison_documents() == documents[:6]
    first_start = window._page_start
    window.previous_comparison_page()
    assert window._page_start == first_start
    assert "first Comparison Page" in window.statusBar().currentMessage()
    assert tuple(document.document_id for document in window.selected_documents) == selected_ids
    window.close()


def test_primary_promotion_is_bounded_to_current_comparison_page(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 15)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_ready_documents(window, documents)
    selected_ids = tuple(document.document_id for document in window.selected_documents)
    window.next_comparison_page()

    window._set_focus_document(documents[8])

    assert tuple(document.document_id for document in window.selected_documents) == selected_ids
    assert window.current_comparison_documents() == documents[6:12]
    visible_ids = set(_visible_source_ids(window))
    assert visible_ids == {document.document_id for document in documents[6:12]}
    focused_viewer = next(
        viewer
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is documents[8]
    )
    assert focused_viewer._slot == 3

    window.next_comparison_page()
    assert window.current_comparison_documents() == documents[12:15]
    assert set(_visible_source_ids(window)) == {
        document.document_id for document in documents[12:15]
    }
    window.close()


def test_number_keys_are_current_page_local_slots_in_single_view(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 15)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_ready_documents(window, documents)
    window.set_layout_mode("Single View")
    window.next_comparison_page()

    window.show_selected_image(3)

    assert window._page_start == 6
    assert window._current_index == 9
    assert window.viewer.document is documents[9]
    assert window.viewer._slot == 4
    assert window.viewer.header.text().startswith("[4]")
    navigation_labels = [
        window.viewer.header.navigation_layout.itemAt(index).widget().text()
        for index in range(window.viewer.header.navigation_layout.count())
    ]
    assert navigation_labels == ["1", "2", "3", "4", "5", "6"]
    window.close()


def test_single_view_fine_navigation_crosses_page_boundary_with_local_slot_reset(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 15)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_ready_documents(window, documents)
    window.set_layout_mode("Single View")
    window.next_comparison_page()
    window.show_selected_image(5)
    assert window.viewer.document is documents[11]
    assert window.viewer._slot == 6

    window.next_image()

    assert window._current_index == 12
    assert window._page_start == 12
    assert window.current_comparison_documents() == documents[12:15]
    assert window.viewer.document is documents[12]
    assert window.viewer._slot == 1
    assert window.viewer.header.text().startswith("[1]")
    window.close()


def test_page_transition_updates_statistics_histogram_line_and_difference_working_set(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = _ready_documents(tmp_path, 15)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_ready_documents(window, documents)

    difference_calls: list[list[str]] = []
    line_calls: list[list[str]] = []
    monkeypatch.setattr(
        window.difference_panel,
        "set_documents",
        lambda current, *_args, **_kwargs: difference_calls.append(
            [document.document_id for document in current]
        ),
    )
    monkeypatch.setattr(window.difference_panel, "cached_display_for_current", lambda: None)
    monkeypatch.setattr(window.difference_panel, "selected_documents", lambda: None)
    monkeypatch.setattr(window.difference_panel, "has_cached_map", lambda: False)
    monkeypatch.setattr(
        window.line_profile_panel,
        "set_documents",
        lambda current, *_args, **_kwargs: line_calls.append(
            [document.document_id for document in current]
        ),
    )

    window.next_comparison_page()

    expected = [document.document_id for document in documents[6:12]]
    assert [
        document.document_id for document in window.comparison_analysis_panel._documents
    ] == expected
    assert difference_calls[-1] == expected
    assert line_calls[-1] == expected
    window.close()


def test_large_selection_residency_protects_current_page_not_all_selected(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    documents = _ready_documents(tmp_path, 15)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_ready_documents(window, documents)

    manager = ResidencyManager(COMPARISON_PAGE_SIZE * int(documents[0].source.nbytes))
    for document in documents:
        assert document.source is not None
        manager.record(document.document_id, int(document.source.nbytes))
    window.residency_manager = manager

    protected = window._residency_protected_document_ids()
    assert {document.document_id for document in documents[:6]}.issubset(protected)
    assert not {document.document_id for document in documents[6:]}.intersection(protected)

    window._evict_resident_documents()
    assert all(document.source is not None for document in documents[:6])
    assert all(document.source is None for document in documents[6:])

    requested: list[str] = []
    monkeypatch.setattr(
        window,
        "_ensure_loaded",
        lambda document: requested.append(document.document_id),
    )
    window.next_comparison_page()

    assert requested == [document.document_id for document in documents[6:12]]
    page_ids = {document.document_id for document in documents[6:12]}
    assert page_ids.issubset(window._residency_protected_document_ids())
    window.close()


def test_comparison_page_shortcuts_are_application_scoped_and_folder_position_stays_separate(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 15)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_ready_documents(window, documents)

    assert [shortcut.key().toString() for shortcut in window._comparison_page_shortcuts] == [
        "Ctrl+Left",
        "Ctrl+Right",
    ]
    assert all(
        shortcut.context() == Qt.ShortcutContext.ApplicationShortcut
        for shortcut in window._comparison_page_shortcuts
    )
    assert all(shortcut.parent() is window for shortcut in window._comparison_page_shortcuts)

    selected_before = tuple(document.document_id for document in window.selected_documents)
    window.next_folder_position()
    assert tuple(document.document_id for document in window.selected_documents) == selected_before
    assert window._page_start == 0
    assert "requires 1–6 selected images" in window.statusBar().currentMessage()
    window.close()


def test_presentation_controls_live_above_view_and_gain_combo_does_not_take_arrow_focus(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 2)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_ready_documents(window, documents)

    gain_control = install_display_gain_control(window)

    assert window.layout_selector.parentWidget() is window.presentation_controls
    assert window.comparison_page_group.parentWidget() is window.presentation_controls
    assert gain_control.parentWidget().parentWidget() is window.presentation_controls
    assert gain_control.focusPolicy() == Qt.FocusPolicy.NoFocus
    window.close()


def test_multi_view_fine_navigation_changes_active_without_changing_primary(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 5)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_ready_documents(window, documents)
    window._set_focus_document(documents[2])
    primary_id = window._focus_document_id

    window.next_image()
    window.next_image()

    assert window._focus_document_id == primary_id
    assert window._active_document_id != primary_id
    window.close()


def test_comparison_page_navigation_preserves_primary_local_slot(
    qtbot: object,
    tmp_path: Path,
) -> None:
    documents = _ready_documents(tmp_path, 15)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _select_ready_documents(window, documents)
    window._set_focus_document(documents[2])

    window.next_comparison_page()

    assert window._focus_document_id == documents[8].document_id
    focused = next(
        viewer
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
        and viewer.document.document_id == window._focus_document_id
    )
    assert focused._slot == 3
    window.close()


def test_split_channel_multi_view_exposes_explicit_primary_control(
    qtbot: object,
    tmp_path: Path,
) -> None:
    document = ImageDocument.from_array(
        np.arange(4 * 4 * 3, dtype=np.uint8).reshape(4, 4, 3),
        "rgb.png",
        source_path=tmp_path / "rgb.png",
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.add_document(document)

    window._set_split_channels(True)
    channels = [
        viewer.document
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    ]
    assert len(channels) == 3
    assert all(
        viewer.header.focus.isVisible()
        for viewer in window.multi_compare_view.occupied_viewers
    )

    window._set_focus_document(channels[1])

    assert window._split_focus_document_id == channels[1].document_id
    assert any(
        viewer.document is channels[1] and viewer.header.focus.isChecked()
        for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_off_page_raw_is_lazy_and_cancel_is_suppressed_until_new_foreground_intent(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ordinary = _ready_documents(tmp_path, 6)
    raw_path = tmp_path / "raw" / "frame.raw"
    raw_path.parent.mkdir(parents=True)
    raw_path.write_bytes(bytes(32))
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    for document in ordinary:
        window.add_document(document, select=False)
    raw_id = window._register_input(ImageInput(raw_path), resolve_raw_profile=False)
    assert raw_id is not None

    prompt_count = 0

    def cancel_profile(*_args: object, **_kwargs: object) -> None:
        nonlocal prompt_count
        prompt_count += 1
        return None

    started: list[str] = []
    monkeypatch.setattr(window, "_confirm_raw_profile", cancel_profile)
    monkeypatch.setattr(
        window,
        "_start_load",
        lambda target_id, *_args, **_kwargs: started.append(target_id),
    )
    selected_ids = [document.document_id for document in ordinary] + [raw_id]

    window._select_document_ids(selected_ids)
    assert prompt_count == 0
    assert window.documents[raw_id].source is None
    assert window.documents[raw_id].loading_state == "pending"

    window.next_comparison_page()
    assert prompt_count == 1
    assert started == []
    assert window.documents[raw_id].loading_state == "pending"
    assert raw_id in window._raw_profile_prompt_suppressed

    window._render_selection(preserve_view=True)
    assert prompt_count == 1
    assert started == []

    window.previous_comparison_page()
    window.next_comparison_page()
    assert prompt_count == 2
    assert started == []
    window.close()


def test_open_images_keeps_all_fifteen_files_selected_with_first_page_presented(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = [tmp_path / f"direct-{index:02d}.png" for index in range(15)]
    for path in paths:
        path.write_bytes(b"fixture")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        lambda *_args, **_kwargs: ([str(path) for path in paths], ""),
    )

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    monkeypatch.setattr(window, "_ensure_loaded", lambda _document: None)
    monkeypatch.setattr(window, "_refresh_preload_plan", lambda: None)

    window.open_images()

    assert len(window.documents) == 15
    assert [document.source_path for document in window.selected_documents] == [
        path.resolve() for path in paths
    ]
    assert [document.source_path for document in window.current_comparison_documents()] == [
        path.resolve() for path in paths[:6]
    ]
    assert window._view_capacity == COMPARISON_PAGE_SIZE
    window.close()


def test_open_folders_cancel_is_a_complete_noop(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = ImageDocument.from_array(
        np.arange(16, dtype=np.uint8).reshape(4, 4),
        "current.png",
        source_path=tmp_path / "current.png",
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.add_document(current)
    window._shared_roi = RoiBounds(0, 0, 2, 2)
    window._shared_line = LineSelection(0, 0, 3, 3)

    selected_before = tuple(document.document_id for document in window.selected_documents)
    central_before = window.central_stack.currentWidget()
    layout_before = window._layout_mode
    active_before = window._active_document_id
    roi_before = window._shared_roi
    line_before = window._shared_line
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: "",
    )

    window.open_folders()

    assert len(window.documents) == 1
    selected_after = tuple(document.document_id for document in window.selected_documents)
    assert selected_after == selected_before
    assert window.central_stack.currentWidget() is central_before
    assert window._layout_mode == layout_before
    assert window._active_document_id == active_before
    assert window._shared_roi == roi_before
    assert window._shared_line == line_before
    window.close()
