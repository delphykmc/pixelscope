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
    controller.refresh_menu()
    before_documents = tuple(window.documents)
    before_selected = tuple(item.document_id for item in window.selected_documents)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warnings.append(str(args[2])),
    )

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
    controller.refresh_menu()
    before_documents = tuple(window.documents)
    before_selected = tuple(item.document_id for item in window.selected_documents)
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warnings.append(str(args[2])),
    )

    controller.open_recent(RecentEntryKind.FOLDER, recent_path)

    assert tuple(window.documents) == before_documents
    assert tuple(item.document_id for item in window.selected_documents) == before_selected
    assert controller.repository.load(RecentEntryKind.FOLDER) == (recent_path.resolve(),)
    assert warnings and "no longer a folder" in warnings[0]
    window.close()


def test_recent_comparison_set_real_partial_open_uses_p4b_and_promotes_mru(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    a = _ready_document(tmp_path / "a.png", 1)
    b = _ready_document(tmp_path / "b.png", 2)
    c = _ready_document(tmp_path / "c.png", 3)
    extra = _ready_document(tmp_path / "extra.png", 9)
    _register(window, [a, b, c, extra])

    window._select_document_ids([a.document_id, b.document_id, c.document_id])
    window.set_layout_mode("Multi View")
    window._set_focus_document(a.document_id)
    window._set_active_document(c)
    target = tmp_path / "partial.pixelscope"
    window.comparison_set_controller.save_to_path(target)

    b.source_path.unlink()
    window._select_document_ids([extra.document_id])
    review = window.review_selection_controller
    review.state.enter([extra.document_id])
    review.state.set_picked(extra.document_id, True)

    other = tmp_path / "other.pixelscope"
    other.write_text("{}", encoding="utf-8")
    controller.repository.record(RecentEntryKind.COMPARISON_SET, [target])
    controller.repository.record(RecentEntryKind.COMPARISON_SET, [other])
    controller.refresh_menu()
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((str(title), str(message))),
    )

    controller.open_recent(RecentEntryKind.COMPARISON_SET, target)

    assert [item.document_id for item in window.selected_documents] == [
        a.document_id,
        c.document_id,
    ]
    assert window._active_document_id == c.document_id
    assert window._focus_document_id == a.document_id
    assert window._layout_mode == "Multi View"
    assert not review.active
    assert controller.repository.load(RecentEntryKind.COMPARISON_SET)[0] == target.resolve()
    assert any("missing sources" in title for title, _message in warnings)
    window.close()


def test_recent_comparison_set_real_zero_loadable_keeps_workspace_and_mru_position(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _production_window(qtbot)
    controller = window.recent_entries_controller
    a = _ready_document(tmp_path / "a.png", 1)
    b = _ready_document(tmp_path / "b.png", 2)
    current = _ready_document(tmp_path / "current.png", 9)
    _register(window, [a, b, current])

    window._select_document_ids([a.document_id, b.document_id])
    target = tmp_path / "zero.pixelscope"
    window.comparison_set_controller.save_to_path(target)
    a.source_path.unlink()
    b.source_path.unlink()

    window._select_document_ids([current.document_id])
    review = window.review_selection_controller
    review.state.enter([current.document_id])
    review.state.set_picked(current.document_id, True)
    before_selected = tuple(item.document_id for item in window.selected_documents)
    before_active = window._active_document_id
    before_primary = window._focus_document_id

    other = tmp_path / "other.pixelscope"
    other.write_text("{}", encoding="utf-8")
    controller.repository.record(RecentEntryKind.COMPARISON_SET, [target])
    controller.repository.record(RecentEntryKind.COMPARISON_SET, [other])
    controller.refresh_menu()
    before_history = controller.repository.load(RecentEntryKind.COMPARISON_SET)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((str(title), str(message))),
    )

    controller.open_recent(RecentEntryKind.COMPARISON_SET, target)

    assert tuple(item.document_id for item in window.selected_documents) == before_selected
    assert window._active_document_id == before_active
    assert window._focus_document_id == before_primary
    assert review.active
    assert review.picked_ids == {current.document_id}
    assert controller.repository.load(RecentEntryKind.COMPARISON_SET) == before_history
    assert any("sources unavailable" in title.lower() for title, _message in warnings)
    window.close()
