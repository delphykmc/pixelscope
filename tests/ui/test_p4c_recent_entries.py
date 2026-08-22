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


def _register(window: MainWindow, *documents: ImageDocument) -> None:
    for document in documents:
        window.add_document(document, select=False)


def _raise_recent_failure(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("injected Recent storage failure")


def test_file_menu_groups_open_recent_then_save_session(qtbot: object) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    file_menu = window.session_controller._file_menu_ref

    assert isinstance(file_menu, QMenu)
    texts = [action.text().replace("&", "") for action in file_menu.actions()]
    expected = [
        "Open Images...",
        "Open Folder...",
        "Open Session...",
        "Open Recent Images",
        "Open Recent Folders",
        "Open Recent Sessions",
    ]
    indices = [texts.index(text) for text in expected]
    assert indices == sorted(indices)
    save_index = texts.index("Save Session...")
    assert indices[-1] < save_index
    assert any(action.isSeparator() for action in file_menu.actions()[indices[-1] + 1 : save_index])
    assert controller.images_menu.title() == "Open Recent Images"
    assert controller.folders_menu.title() == "Open Recent Folders"
    assert controller.sessions_menu.title() == "Open Recent Sessions"
    window.close()


def test_direct_image_registration_is_observed_without_selection_authority(
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
    assert controller.repository.load(RecentEntryKind.IMAGE) == (document.source_path.resolve(),)
    assert window.selected_documents == []
    window.close()


def test_file_open_images_succeeds_when_recent_observer_fails(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    document = _ready_document(tmp_path / "action.png")
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

    assert [item.document_id for item in window.selected_documents] == [document.document_id]
    assert window._active_document_id == document.document_id
    assert window.statusBar().currentMessage() == "Opened 1 image(s)"
    window.close()


def test_folder_history_is_registration_only_and_history_failure_is_non_authoritative(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    selected = _ready_document(tmp_path / "selected.png")
    _register(window, selected)
    window._select_document_ids([selected.document_id])
    folder = tmp_path / "dataset"
    folder.mkdir()
    (folder / "frame.png").write_bytes(b"pending-image")

    result = window.register_folders([folder])
    assert result.folder_count == 1
    assert controller.repository.load(RecentEntryKind.FOLDER) == (folder.resolve(),)
    assert [item.document_id for item in window.selected_documents] == [selected.document_id]

    second = tmp_path / "dataset2"
    second.mkdir()
    monkeypatch.setattr(controller.repository, "record", _raise_recent_failure)
    window.register_folders([second])
    assert [item.document_id for item in window.selected_documents] == [selected.document_id]
    window.close()


def test_recent_image_reuses_direct_open_selection_path(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    existing = _ready_document(tmp_path / "existing.png", 1)
    recent = _ready_document(tmp_path / "recent.png", 2)
    _register(window, existing, recent)
    window._select_document_ids([existing.document_id])
    controller._register_inputs_original = lambda inputs, resolve_raw_profiles: [recent.document_id]

    controller.open_recent(RecentEntryKind.IMAGE, recent.source_path)

    assert [item.document_id for item in window.selected_documents] == [recent.document_id]
    assert controller.repository.load(RecentEntryKind.IMAGE)[0] == recent.source_path.resolve()
    window.close()


def test_recent_session_delegates_to_session_loader_and_promotes_mru(
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
        window.session_controller,
        "open_from_path",
        lambda path: (calls.append(Path(path)) or (3, ())),
    )
    monkeypatch.setattr(
        window.session_controller,
        "show_open_feedback",
        lambda path, loaded, missing: feedback.append((Path(path), loaded, missing)),
    )

    controller.open_recent(RecentEntryKind.SESSION, target)

    assert calls == [target]
    assert feedback == [(target, 3, ())]
    assert controller.repository.load(RecentEntryKind.SESSION) == (target.resolve(),)
    window.close()


def test_session_save_dialog_records_recent_only_after_success(
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

    window.session_controller.save_dialog()

    assert target.is_file()
    assert controller.repository.load(RecentEntryKind.SESSION) == (target.resolve(),)
    assert window.statusBar().currentMessage() == "Saved Session · saved.pixelscope"
    window.close()


def test_failed_session_save_does_not_create_recent_entry(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    document = _ready_document(tmp_path / "source.png")
    _register(window, document)
    window._select_document_ids([document.document_id])
    target = tmp_path / "failed.pixelscope"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), ""),
    )
    monkeypatch.setattr(
        window.session_controller.repository,
        "save",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)

    window.session_controller.save_dialog()

    assert not target.exists()
    assert controller.repository.load(RecentEntryKind.SESSION) == ()
    window.close()


@pytest.mark.parametrize(
    "kind,suffix",
    [
        (RecentEntryKind.IMAGE, ".png"),
        (RecentEntryKind.FOLDER, ""),
        (RecentEntryKind.SESSION, ".pixelscope"),
    ],
)
def test_missing_recent_entry_remove_and_keep_preserve_workspace(
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
    other = tmp_path / ("other-folder" if kind is RecentEntryKind.FOLDER else f"other{suffix}")
    controller.repository.record(kind, [missing, other])
    before_selected = tuple(item.document_id for item in window.selected_documents)
    before_pick = set(review.state.picked_ids)

    monkeypatch.setattr(controller, "_confirm_remove_missing", lambda *args: False)
    controller.open_recent(kind, missing)
    assert controller.repository.load(kind)[0] == missing.resolve()
    assert tuple(item.document_id for item in window.selected_documents) == before_selected
    assert set(review.state.picked_ids) == before_pick

    monkeypatch.setattr(controller, "_confirm_remove_missing", lambda *args: True)
    controller.open_recent(kind, missing)
    assert controller.repository.load(kind) == (other.resolve(),)
    assert tuple(item.document_id for item in window.selected_documents) == before_selected
    assert set(review.state.picked_ids) == before_pick
    window.close()


def test_existing_invalid_session_stays_in_history_on_open_error(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    target = tmp_path / "broken.pixelscope"
    target.write_text("not json", encoding="utf-8")
    controller.repository.record(RecentEntryKind.SESSION, [target])
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warnings.append(str(args[2])),
    )

    controller.open_recent(RecentEntryKind.SESSION, target)

    assert controller.repository.load(RecentEntryKind.SESSION) == (target.resolve(),)
    assert warnings
    window.close()


def test_typed_clear_removes_only_the_selected_recent_history(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    image = (tmp_path / "private" / "frame.png").resolve()
    folder = (tmp_path / "dataset").resolve()
    session = (tmp_path / "workspace.pixelscope").resolve()
    controller.repository.record(RecentEntryKind.IMAGE, [image])
    controller.repository.record(RecentEntryKind.FOLDER, [folder])
    controller.repository.record(RecentEntryKind.SESSION, [session])
    controller.refresh_menu()

    action = controller.images_menu.actions()[0]
    assert action.text() == "frame.png — private"
    assert action.toolTip() == str(image)
    assert "Clear Recent Images" in [item.text() for item in controller.images_menu.actions()]

    controller.clear_kind(RecentEntryKind.IMAGE)
    assert controller.repository.load(RecentEntryKind.IMAGE) == ()
    assert controller.repository.load(RecentEntryKind.FOLDER) == (folder,)
    assert controller.repository.load(RecentEntryKind.SESSION) == (session,)
    window.close()
