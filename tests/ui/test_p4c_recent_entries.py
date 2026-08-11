from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.recent_entries import RecentEntryKind
from pixelscope.io.path_discovery import discover_image_inputs


def _production_window(qtbot: object) -> MainWindow:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _ready_document(path: Path, value: int = 1) -> ImageDocument:
    path.write_bytes(b"recent-entry-source")
    return ImageDocument.from_array(
        np.full((4, 4), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def _register(window: MainWindow, document: ImageDocument) -> None:
    window.add_document(document, select=False)


def _raise_recent_failure(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("injected Recent storage failure")


def test_production_file_menu_exposes_typed_recent_entry_surface(qtbot: object) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    file_menu = window.comparison_set_controller._file_menu_ref

    assert isinstance(file_menu, QMenu)
    texts = [action.text().replace("&", "") for action in file_menu.actions()]
    assert texts.index("Open Images...") < texts.index("Open Comparison Set...")
    assert texts.index("Open Folder...") < texts.index("Open Comparison Set...")
    assert "Recent" in texts
    assert texts.index("Recent") < texts.index("Save Comparison Set...")
    assert [
        action.text()
        for action in controller.recent_menu.actions()
        if not action.isSeparator()
    ] == [
        "Images",
        "Folders",
        "Comparison Sets",
        "Clear Recent Entries",
    ]
    assert window.action_map["Open Images..."].shortcut().toString() == "Ctrl+O"
    assert window.action_map["Open Folder..."].shortcut().toString() == "Ctrl+Shift+O"
    window.close()


def test_direct_image_registration_is_observed_without_changing_selection_authority(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    document = _ready_document(tmp_path / "image.png")
    _register(window, document)

    controller._register_inputs_original = lambda inputs, resolve_raw_profiles: [
        document.document_id
    ]
    result = window._register_inputs(
        discover_image_inputs([document.source_path]),
        resolve_raw_profiles=True,
    )

    assert result == [document.document_id]
    assert controller.repository.load(RecentEntryKind.IMAGE) == (
        document.source_path.resolve(),
    )
    assert window.selected_documents == []
    window.close()


def test_file_open_images_routes_through_history_observer_and_survives_failure(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    document = _ready_document(tmp_path / "from-file-action.png")
    _register(window, document)
    controller._register_inputs_original = lambda inputs, resolve_raw_profiles: [
        document.document_id
    ]
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        lambda *args, **kwargs: ([str(document.source_path)], ""),
    )
    monkeypatch.setattr(controller.repository, "record", _raise_recent_failure)

    window.action_map["Open Images..."].trigger()

    assert [item.document_id for item in window.selected_documents] == [
        document.document_id
    ]
    assert window._active_document_id == document.document_id
    assert window.statusBar().currentMessage() == "Opened 1 image(s)"
    window.close()


def test_recent_observer_failure_does_not_acquire_selection_or_residency_authority(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    selected = _ready_document(tmp_path / "selected.png", 1)
    observed = _ready_document(tmp_path / "observed.png", 2)
    _register(window, selected)
    _register(window, observed)
    window._select_document_ids([selected.document_id])
    before_selected = tuple(item.document_id for item in window.selected_documents)
    before_protected = set(window._residency_protected_document_ids())
    controller._register_inputs_original = lambda inputs, resolve_raw_profiles: [
        observed.document_id
    ]
    monkeypatch.setattr(controller.repository, "record", _raise_recent_failure)

    result = window._register_inputs(
        discover_image_inputs([observed.source_path]),
        resolve_raw_profiles=True,
    )

    assert result == [observed.document_id]
    assert tuple(item.document_id for item in window.selected_documents) == before_selected
    assert set(window._residency_protected_document_ids()) == before_protected
    window.close()


def test_recent_image_open_reuses_direct_image_selection_path(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    existing = _ready_document(tmp_path / "existing.png", 1)
    recent = _ready_document(tmp_path / "recent.png", 2)
    _register(window, existing)
    _register(window, recent)
    window._select_document_ids([existing.document_id])
    controller._register_inputs_original = lambda inputs, resolve_raw_profiles: [
        recent.document_id
    ]

    controller.open_recent(RecentEntryKind.IMAGE, recent.source_path)

    assert [document.document_id for document in window.selected_documents] == [
        recent.document_id
    ]
    assert controller.repository.load(RecentEntryKind.IMAGE)[0] == recent.source_path.resolve()
    window.close()


def test_folder_registration_records_history_but_preserves_current_selection(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    selected = _ready_document(tmp_path / "selected.png")
    _register(window, selected)
    window._select_document_ids([selected.document_id])
    before_active = window._active_document_id
    before_layout = window._layout_mode
    folder = tmp_path / "dataset"
    folder.mkdir()
    (folder / "frame.png").write_bytes(b"pending-image")

    result = window.register_folders([folder])

    assert result.folder_count == 1
    assert controller.repository.load(RecentEntryKind.FOLDER) == (folder.resolve(),)
    assert [document.document_id for document in window.selected_documents] == [
        selected.document_id
    ]
    assert window._active_document_id == before_active
    assert window._layout_mode == before_layout
    window.close()


def test_folder_registration_survives_recent_storage_failure_and_stays_registration_only(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    selected = _ready_document(tmp_path / "selected.png")
    _register(window, selected)
    window._select_document_ids([selected.document_id])
    before_active = window._active_document_id
    folder = tmp_path / "dataset"
    folder.mkdir()
    (folder / "frame.png").write_bytes(b"pending-image")
    monkeypatch.setattr(controller.repository, "record", _raise_recent_failure)

    result = window.register_folders([folder])

    assert result.folder_count == 1
    assert result.image_count == 1
    assert [document.document_id for document in window.selected_documents] == [
        selected.document_id
    ]
    assert window._active_document_id == before_active
    window.close()


def test_recent_comparison_set_delegates_to_p4b_loader_and_moves_to_mru(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    target = tmp_path / "review.pixelscope"
    target.write_text("{}", encoding="utf-8")
    calls: list[Path] = []
    feedback: list[tuple[Path, int, tuple[Path, ...]]] = []
    monkeypatch.setattr(
        window.comparison_set_controller,
        "open_from_path",
        lambda path: (calls.append(Path(path)) or (3, ())),
    )
    monkeypatch.setattr(
        window.comparison_set_controller,
        "show_open_feedback",
        lambda path, loaded, missing: feedback.append((Path(path), loaded, missing)),
    )

    controller.open_recent(RecentEntryKind.COMPARISON_SET, target)

    assert calls == [target]
    assert feedback == [(target, 3, ())]
    assert controller.repository.load(RecentEntryKind.COMPARISON_SET) == (
        target.resolve(),
    )
    window.close()


def test_comparison_set_save_dialog_records_history_through_canonical_callback(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    document = _ready_document(tmp_path / "source.png")
    _register(window, document)
    window._select_document_ids([document.document_id])
    target = tmp_path / "saved.pixelscope"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), ""),
    )

    window.comparison_set_controller.save_dialog()

    assert target.is_file()
    assert controller.repository.load(RecentEntryKind.COMPARISON_SET) == (
        target.resolve(),
    )
    assert window.statusBar().currentMessage() == "Saved Comparison Set · saved.pixelscope"
    window.close()


def test_comparison_set_save_dialog_survives_recent_callback_failure(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    document = _ready_document(tmp_path / "source.png")
    _register(window, document)
    window._select_document_ids([document.document_id])
    target = tmp_path / "saved.pixelscope"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), ""),
    )
    window.comparison_set_controller.set_recent_entry_callback(_raise_recent_failure)

    window.comparison_set_controller.save_dialog()

    assert target.is_file()
    assert window.statusBar().currentMessage() == "Saved Comparison Set · saved.pixelscope"
    assert [item.document_id for item in window.selected_documents] == [
        document.document_id
    ]
    window.close()


def test_comparison_set_open_dialog_survives_recent_callback_failure(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    document = _ready_document(tmp_path / "source.png")
    _register(window, document)
    window._select_document_ids([document.document_id])
    target = tmp_path / "open.pixelscope"
    window.comparison_set_controller.save_to_path(target)
    window._select_document_ids([])
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(target), ""),
    )
    window.comparison_set_controller.set_recent_entry_callback(_raise_recent_failure)

    window.comparison_set_controller.open_dialog()

    assert [item.document_id for item in window.selected_documents] == [
        document.document_id
    ]
    assert window.statusBar().currentMessage() == (
        "Opened Comparison Set · open.pixelscope · 1 source(s)"
    )
    window.close()


@pytest.mark.parametrize(
    "kind,suffix",
    [
        (RecentEntryKind.IMAGE, ".png"),
        (RecentEntryKind.FOLDER, ""),
        (RecentEntryKind.COMPARISON_SET, ".pixelscope"),
    ],
)
def test_missing_recent_entry_removes_only_history_and_preserves_workspace(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: RecentEntryKind,
    suffix: str,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    selected = _ready_document(tmp_path / "selected.png")
    _register(window, selected)
    window._select_document_ids([selected.document_id])
    review = window.review_selection_controller
    review.state.enter([selected.document_id])
    review.state.set_picked(selected.document_id, True)
    missing = tmp_path / (
        "missing-folder" if kind is RecentEntryKind.FOLDER else f"missing{suffix}"
    )
    controller.repository.record(kind, [missing])
    controller.refresh_menu()
    before_registered = tuple(window.documents)
    before_selected = tuple(document.document_id for document in window.selected_documents)
    before_active = window._active_document_id
    before_primary = window._focus_document_id
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warnings.append(str(args[2])),
    )

    controller.open_recent(kind, missing)

    assert controller.repository.load(kind) == ()
    assert tuple(window.documents) == before_registered
    assert tuple(document.document_id for document in window.selected_documents) == before_selected
    assert window._active_document_id == before_active
    assert window._focus_document_id == before_primary
    assert review.active
    assert review.picked_ids == {selected.document_id}
    assert len(warnings) == 1
    window.close()


def test_existing_invalid_comparison_set_stays_in_history_on_open_error(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    target = tmp_path / "broken.pixelscope"
    target.write_text("not json", encoding="utf-8")
    controller.repository.record(RecentEntryKind.COMPARISON_SET, [target])
    controller.refresh_menu()
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warnings.append(str(args[2])),
    )

    controller.open_recent(RecentEntryKind.COMPARISON_SET, target)

    assert controller.repository.load(RecentEntryKind.COMPARISON_SET) == (
        target.resolve(),
    )
    assert len(warnings) == 1
    window.close()


def test_menu_labels_limit_path_exposure_and_clear_history(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    image = (tmp_path / "private" / "frame.png").resolve()
    controller.repository.record(RecentEntryKind.IMAGE, [image])
    controller.refresh_menu()

    action = controller.images_menu.actions()[0]
    assert action.text() == "frame.png — private"
    assert str(image) not in action.text()
    assert action.toolTip() == str(image)
    assert controller.clear_action.isEnabled()

    controller.clear_all()

    assert controller.repository.load(RecentEntryKind.IMAGE) == ()
    assert not controller.clear_action.isEnabled()
    window.close()
