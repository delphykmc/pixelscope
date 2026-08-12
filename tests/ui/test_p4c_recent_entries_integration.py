from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMessageBox

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.recent_entries import RecentEntryKind


def _production_window(qtbot: object) -> MainWindow:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _ready_document(path: Path, value: int) -> ImageDocument:
    path.write_bytes(b"p4c-integration-source")
    return ImageDocument.from_array(
        np.full((4, 4), value, dtype=np.uint8),
        path.name,
        source_path=path,
    )


def _register(window: MainWindow, documents: list[ImageDocument]) -> None:
    for document in documents:
        window.add_document(document, select=False)


def test_recent_image_wrong_kind_is_not_reinterpreted_as_folder_input(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    selected = _ready_document(tmp_path / "selected.png", 1)
    _register(window, [selected])
    window._select_document_ids([selected.document_id])

    recent_path = tmp_path / "frame.png"
    recent_path.mkdir()
    (recent_path / "nested.png").write_bytes(b"nested")
    controller.repository.record(RecentEntryKind.IMAGE, [recent_path])
    before_documents = tuple(window.documents)
    before_selected = tuple(item.document_id for item in window.selected_documents)
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(str(args[2])))

    controller.open_recent(RecentEntryKind.IMAGE, recent_path)

    assert tuple(window.documents) == before_documents
    assert tuple(item.document_id for item in window.selected_documents) == before_selected
    assert controller.repository.load(RecentEntryKind.IMAGE) == (recent_path.resolve(),)
    assert warnings and "no longer a file" in warnings[0]
    window.close()


def test_recent_folder_wrong_kind_stays_history_only(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    selected = _ready_document(tmp_path / "selected.png", 1)
    _register(window, [selected])
    window._select_document_ids([selected.document_id])

    recent_path = tmp_path / "dataset"
    recent_path.write_bytes(b"not-a-folder")
    controller.repository.record(RecentEntryKind.FOLDER, [recent_path])
    before_documents = tuple(window.documents)
    before_selected = tuple(item.document_id for item in window.selected_documents)
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(str(args[2])))

    controller.open_recent(RecentEntryKind.FOLDER, recent_path)

    assert tuple(window.documents) == before_documents
    assert tuple(item.document_id for item in window.selected_documents) == before_selected
    assert controller.repository.load(RecentEntryKind.FOLDER) == (recent_path.resolve(),)
    assert warnings and "no longer a folder" in warnings[0]
    window.close()


def test_recent_session_partial_open_restores_saved_workspace_and_promotes_mru(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    a = _ready_document(tmp_path / "a.png", 1)
    b = _ready_document(tmp_path / "b.png", 2)
    c = _ready_document(tmp_path / "c.png", 3)
    registered_only = _ready_document(tmp_path / "registered-only.png", 4)
    _register(window, [a, b, c, registered_only])

    window._select_document_ids([a.document_id, b.document_id, c.document_id])
    window.set_layout_mode("Multi View")
    window._set_focus_document(a.document_id)
    window._set_active_document(c)
    target = tmp_path / "partial.pixelscope"
    window.session_controller.save_to_path(target)

    extra = _ready_document(tmp_path / "extra.png", 9)
    _register(window, [extra])
    b.source_path.unlink()
    window._select_document_ids([extra.document_id])
    review = window.review_selection_controller
    review.state.enter([extra.document_id])
    review.state.set_picked(extra.document_id, True)

    other = tmp_path / "other.pixelscope"
    other.write_text("{}", encoding="utf-8")
    controller.repository.record(RecentEntryKind.SESSION, [target])
    controller.repository.record(RecentEntryKind.SESSION, [other])
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((str(title), str(message))),
    )

    controller.open_recent(RecentEntryKind.SESSION, target)

    assert [item.source_path for item in window.selected_documents] == [a.source_path, c.source_path]
    assert registered_only.document_id in window.documents
    assert extra.document_id not in window.documents
    assert window._active_document_id == c.document_id
    assert window._focus_document_id == a.document_id
    assert window._layout_mode == "Multi View"
    assert not review.active
    assert controller.repository.load(RecentEntryKind.SESSION)[0] == target.resolve()
    assert any("missing sources" in title.lower() for title, _message in warnings)
    window.close()


def test_recent_session_zero_loadable_keeps_workspace_and_mru_position(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    a = _ready_document(tmp_path / "a.png", 1)
    b = _ready_document(tmp_path / "b.png", 2)
    _register(window, [a, b])

    window._select_document_ids([a.document_id, b.document_id])
    target = tmp_path / "zero.pixelscope"
    window.session_controller.save_to_path(target)
    a.source_path.unlink()
    b.source_path.unlink()

    surviving = _ready_document(tmp_path / "surviving.png", 7)
    _register(window, [surviving])
    window._select_document_ids([surviving.document_id])
    review = window.review_selection_controller
    review.state.enter([surviving.document_id])
    review.state.set_picked(surviving.document_id, True)
    before_documents = tuple(window.documents)
    before_selected = tuple(item.document_id for item in window.selected_documents)

    other = tmp_path / "other.pixelscope"
    other.write_text("{}", encoding="utf-8")
    controller.repository.record(RecentEntryKind.SESSION, [target])
    controller.repository.record(RecentEntryKind.SESSION, [other])
    before_history = controller.repository.load(RecentEntryKind.SESSION)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((str(title), str(message))),
    )

    controller.open_recent(RecentEntryKind.SESSION, target)

    assert tuple(window.documents) == before_documents
    assert tuple(item.document_id for item in window.selected_documents) == before_selected
    assert review.active
    assert review.picked_ids == {surviving.document_id}
    assert controller.repository.load(RecentEntryKind.SESSION) == before_history
    assert any("sources unavailable" in title.lower() for title, _message in warnings)
    window.close()
