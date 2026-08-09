from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog

from pixelscope.app.main_window import COMPARISON_PAGE_SIZE, MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds


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


def _ready_documents(window: MainWindow, tmp_path: Path, count: int) -> list[ImageDocument]:
    documents: list[ImageDocument] = []
    for index in range(count):
        document = ImageDocument.from_array(
            np.full((8, 8), index, dtype=np.uint8),
            f"image-{index + 1:02d}.png",
            source_path=tmp_path / f"folder-{index + 1:02d}" / f"image-{index + 1:02d}.png",
        )
        window.add_document(document, select=False)
        documents.append(document)
    return documents


def _silence_analysis_runtime(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(window, "_refresh_preload_plan", lambda: None)
    monkeypatch.setattr(
        window.comparison_analysis_panel,
        "set_documents",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        window.line_profile_panel,
        "set_documents",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        window.difference_panel,
        "set_documents",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        window.difference_panel,
        "cached_display_for_current",
        lambda: None,
    )


@pytest.mark.parametrize("image_count", [6, 8])
def test_open_images_keeps_all_selected_files_and_uses_comparison_page_navigation(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    image_count: int,
) -> None:
    paths = [tmp_path / f"direct-{index:02d}.png" for index in range(image_count)]
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

    assert len(window.documents) == image_count
    assert [document.source_path for document in window.selected_documents] == [
        path.resolve() for path in paths
    ]
    assert [document.source_path for document in window.current_comparison_documents()] == [
        path.resolve() for path in paths[:COMPARISON_PAGE_SIZE]
    ]

    if image_count <= COMPARISON_PAGE_SIZE:
        assert not window.comparison_page_group.isVisible()
    else:
        selected_before = tuple(document.document_id for document in window.selected_documents)
        window.next_image()
        assert window._page_start == 0
        window.next_comparison_page()
        assert window._page_start == COMPARISON_PAGE_SIZE
        assert tuple(document.document_id for document in window.selected_documents) == selected_before
        assert [document.source_path for document in window.current_comparison_documents()] == [
            path.resolve() for path in paths[COMPARISON_PAGE_SIZE:]
        ]

    window.close()


def test_fifteen_image_comparison_pages_are_derived_and_keep_local_slots(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _silence_analysis_runtime(window, monkeypatch)
    documents = _ready_documents(window, tmp_path, 15)
    selected_ids = [document.document_id for document in documents]

    window._select_document_ids(selected_ids)

    assert [document.document_id for document in window.current_comparison_documents()] == selected_ids[:6]
    assert window.comparison_page_label.text() == "1–6 of 15"
    assert [viewer._slot for viewer in window.multi_compare_view.occupied_viewers] == [1, 2, 3, 4, 5, 6]

    window.next_comparison_page()
    assert [document.document_id for document in window.current_comparison_documents()] == selected_ids[6:12]
    assert window.comparison_page_label.text() == "7–12 of 15"
    assert [viewer._slot for viewer in window.multi_compare_view.occupied_viewers] == [1, 2, 3, 4, 5, 6]
    assert [
        viewer.document.document_id
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    ] == selected_ids[6:12]

    window.next_comparison_page()
    assert [document.document_id for document in window.current_comparison_documents()] == selected_ids[12:15]
    assert window.comparison_page_label.text() == "13–15 of 15"
    assert window.multi_compare_view.capacity == 6
    assert [viewer.document is not None for viewer in window.multi_compare_view.visible_viewers] == [
        True,
        True,
        True,
        False,
        False,
        False,
    ]

    window.next_comparison_page()
    assert window._page_start == 12
    window.previous_comparison_page()
    assert window._page_start == 6
    assert tuple(document.document_id for document in window.selected_documents) == tuple(selected_ids)
    window.close()


def test_single_view_number_keys_and_fine_navigation_are_page_local(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _silence_analysis_runtime(window, monkeypatch)
    documents = _ready_documents(window, tmp_path, 15)
    selected_ids = [document.document_id for document in documents]
    window._select_document_ids(selected_ids)
    window.next_comparison_page()
    window.set_layout_mode("Single View")

    window.show_selected_image(3)
    assert window.current_document is documents[9]
    assert window.viewer.document is documents[9]
    assert window.viewer._slot == 4
    assert window._page_start == 6

    window.show_selected_image(5)
    assert window.current_document is documents[11]
    assert window.viewer._slot == 6
    window.next_image()
    assert window.current_document is documents[12]
    assert window._page_start == 12
    assert window.viewer._slot == 1

    window.previous_image()
    assert window.current_document is documents[11]
    assert window._page_start == 6
    assert window.viewer._slot == 6
    window.close()


def test_comparison_page_navigation_preserves_active_local_slot_and_clamps_final_page(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _silence_analysis_runtime(window, monkeypatch)
    documents = _ready_documents(window, tmp_path, 15)
    window._select_document_ids([document.document_id for document in documents])
    window._current_index = 4
    window._set_active_document(documents[4])

    window.next_comparison_page()
    assert window.current_document is documents[10]
    assert window._current_page_local_index() == 4

    window.next_comparison_page()
    assert window.current_document is documents[14]
    assert window._current_page_local_index() == 2
    window.close()


def test_analysis_and_difference_inputs_follow_current_comparison_page(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = _ready_documents(window, tmp_path, 12)
    selected_ids = [document.document_id for document in documents]
    statistics_calls: list[tuple[str, ...]] = []
    difference_calls: list[tuple[str, ...]] = []
    line_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(window, "_refresh_preload_plan", lambda: None)
    monkeypatch.setattr(
        window.comparison_analysis_panel,
        "set_documents",
        lambda docs, *_args, **_kwargs: statistics_calls.append(
            tuple(document.document_id for document in docs)
        ),
    )
    monkeypatch.setattr(
        window.difference_panel,
        "set_documents",
        lambda docs, *_args, **_kwargs: difference_calls.append(
            tuple(document.document_id for document in docs)
        ),
    )
    monkeypatch.setattr(window.difference_panel, "cached_display_for_current", lambda: None)
    monkeypatch.setattr(
        window.line_profile_panel,
        "set_documents",
        lambda docs, *_args, **_kwargs: line_calls.append(
            tuple(document.document_id for document in docs)
        ),
    )

    window._select_document_ids(selected_ids)
    assert statistics_calls[-1] == tuple(selected_ids[:6])
    assert difference_calls[-1] == tuple(selected_ids[:6])
    assert line_calls[-1] == tuple(selected_ids[:6])

    window.next_comparison_page()
    assert statistics_calls[-1] == tuple(selected_ids[6:12])
    assert difference_calls[-1] == tuple(selected_ids[6:12])
    assert line_calls[-1] == tuple(selected_ids[6:12])
    window.close()


def test_residency_protection_is_current_page_not_entire_large_selection(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _silence_analysis_runtime(window, monkeypatch)
    documents = _ready_documents(window, tmp_path, 12)
    selected_ids = [document.document_id for document in documents]
    window._select_document_ids(selected_ids)

    protected_page_1 = window._residency_protected_document_ids()
    assert set(selected_ids[:6]).issubset(protected_page_1)
    assert set(selected_ids[6:12]).isdisjoint(protected_page_1)

    window.next_comparison_page()
    protected_page_2 = window._residency_protected_document_ids()
    assert set(selected_ids[6:12]).issubset(protected_page_2)
    assert set(selected_ids[:6]).isdisjoint(protected_page_2)
    assert tuple(document.document_id for document in window.selected_documents) == tuple(selected_ids)
    window.close()


def test_selected_over_six_disables_folder_position_without_changing_selection(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _silence_analysis_runtime(window, monkeypatch)
    documents = _ready_documents(window, tmp_path, 7)
    selected_ids = [document.document_id for document in documents]
    window._select_document_ids(selected_ids)

    window.next_folder_position()

    assert tuple(document.document_id for document in window.selected_documents) == tuple(selected_ids)
    assert "requires 1–6 selected images" in window.statusBar().currentMessage()
    window.close()


def test_lazy_raw_cancel_prompts_once_per_foreground_attempt(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "raw"
    folder.mkdir()
    raw_path = folder / "frame.raw"
    raw_path.write_bytes(bytes(32))
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    monkeypatch.setattr(window, "_refresh_preload_plan", lambda: None)
    window.register_folders([folder])
    document = next(iter(window.documents.values()))
    prompts: list[str] = []
    monkeypatch.setattr(
        window,
        "_confirm_raw_profile",
        lambda _image_input, document_id: prompts.append(document_id or "") or None,
    )
    monkeypatch.setattr(
        window,
        "_start_load",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("cancelled RAW must not start a worker")
        ),
    )

    window._select_document_ids([document.document_id])
    assert prompts == [document.document_id]
    assert document.loading_state == "pending"
    window._render_selection(preserve_view=True)
    assert prompts == [document.document_id]

    window.show_selected_image(0)
    assert prompts == [document.document_id, document.document_id]
    assert document.loading_state == "pending"
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
        "pixelscope.app.main_window.choose_directories",
        lambda *_args, **_kwargs: (),
    )

    window.open_folders()

    assert len(window.documents) == 1
    assert tuple(document.document_id for document in window.selected_documents) == selected_before
    assert window.central_stack.currentWidget() is central_before
    assert window._layout_mode == layout_before
    assert window._active_document_id == active_before
    assert window._shared_roi == roi_before
    assert window._shared_line == line_before
    window.close()
