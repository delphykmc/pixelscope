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


def _window(qtbot: object) -> MainWindow:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _document(path: Path, value: int = 1) -> ImageDocument:
    path.write_bytes(b"recent-source")
    return ImageDocument.from_array(
        np.full((4, 4), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def test_file_menu_keeps_p4b_names_and_adds_typed_recent(qtbot: object) -> None:
    window = _window(qtbot)
    controller = window.recent_entries_controller
    menu = window.comparison_set_controller._file_menu_ref
    assert isinstance(menu, QMenu)
    texts = [action.text().replace("&", "") for action in menu.actions()]
    expected = [
        "Open Images...",
        "Open Folder...",
        "Open Comparison Set...",
        "Open Recent Images",
        "Open Recent Folders",
        "Open Recent Comparison Sets",
    ]
    indices = [texts.index(text) for text in expected]
    assert indices == list(range(indices[0], indices[0] + len(expected)))
    assert indices[-1] < texts.index("Save Comparison Set...")
    assert controller.comparison_sets_menu.title() == "Open Recent Comparison Sets"
    window.close()


def test_image_observer_has_no_selection_authority(qtbot: object, tmp_path: Path) -> None:
    window = _window(qtbot)
    controller = window.recent_entries_controller
    document = _document(tmp_path / "image.png")
    window.add_document(document, select=False)
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


def test_recent_storage_failure_does_not_break_open_images(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _window(qtbot)
    controller = window.recent_entries_controller
    document = _document(tmp_path / "action.png")
    window.add_document(document, select=False)
    controller._register_inputs_original = lambda inputs, resolve_raw_profiles: [
        document.document_id
    ]
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        lambda *args, **kwargs: ([str(document.source_path)], ""),
    )
    monkeypatch.setattr(
        controller.repository,
        "record",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("history failure")),
    )
    window.action_map["Open Images..."].trigger()
    assert [item.document_id for item in window.selected_documents] == [document.document_id]
    window.close()


def test_recent_comparison_set_delegates_to_p4b_and_promotes_only_success(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    controller = window.recent_entries_controller
    target = tmp_path / "review.pixelscope"
    target.write_text("{}", encoding="utf-8")
    calls: list[Path] = []
    controller._comparison_set_open_original = lambda path: (
        calls.append(Path(path)) or (3, ())
    )
    controller.open_recent(RecentEntryKind.COMPARISON_SET, target)
    assert calls == [target]
    assert controller.repository.load(RecentEntryKind.COMPARISON_SET) == (target.resolve(),)

    failed = tmp_path / "failed.pixelscope"
    failed.write_text("{}", encoding="utf-8")
    controller._comparison_set_open_original = lambda path: (0, ())
    controller.open_recent(RecentEntryKind.COMPARISON_SET, failed)
    assert failed.resolve() not in controller.repository.load(RecentEntryKind.COMPARISON_SET)
    window.close()


def test_missing_recent_remove_or_keep_preserves_workspace(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _window(qtbot)
    controller = window.recent_entries_controller
    selected = _document(tmp_path / "selected.png")
    window.add_document(selected, select=False)
    window._select_document_ids([selected.document_id])
    missing = tmp_path / "missing.png"
    other = tmp_path / "other.png"
    controller.repository.record(RecentEntryKind.IMAGE, [missing, other])
    before = tuple(item.document_id for item in window.selected_documents)

    monkeypatch.setattr(controller, "_confirm_remove_missing", lambda *args: False)
    controller.open_recent(RecentEntryKind.IMAGE, missing)
    assert controller.repository.load(RecentEntryKind.IMAGE)[0] == missing.resolve()

    monkeypatch.setattr(controller, "_confirm_remove_missing", lambda *args: True)
    controller.open_recent(RecentEntryKind.IMAGE, missing)
    assert controller.repository.load(RecentEntryKind.IMAGE) == (other.resolve(),)
    assert tuple(item.document_id for item in window.selected_documents) == before
    window.close()


def test_wrong_kind_is_kept_and_not_reinterpreted(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _window(qtbot)
    controller = window.recent_entries_controller
    path = tmp_path / "image.png"
    path.mkdir()
    controller.repository.record(RecentEntryKind.IMAGE, [path])
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warnings.append(str(args[2])),
    )
    controller.open_recent(RecentEntryKind.IMAGE, path)
    assert controller.repository.load(RecentEntryKind.IMAGE) == (path.resolve(),)
    assert warnings and "no longer a file" in warnings[0]
    window.close()
