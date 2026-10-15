from __future__ import annotations

from pathlib import Path
from threading import Event

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.recent_entries import RecentEntryKind
from pixelscope.io.path_discovery import RegistrationDiscovery

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _image(path: Path, value: int) -> Path:
    assert cv2.imwrite(str(path), np.full((8, 12, 3), value, dtype=np.uint8))
    return path


def _window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    return window


@pytest.mark.parametrize("command", ["dialog", "recent"])
def test_open_command_yields_to_qt_and_defers_recent_until_paint(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, command: str
) -> None:
    path = _image(tmp_path / "opened.png", 31)
    window = _window(qtbot)
    seed = ImageDocument.from_array(np.zeros((8, 12), dtype=np.uint8), "seed")
    window.add_document(seed)
    registration = window.large_folder_registration_controller
    recent = window.recent_entries_controller
    started, release = Event(), Event()
    original = registration._discovery_function

    def blocked_discovery(paths: object, *, checkpoint: object) -> RegistrationDiscovery:
        started.set()
        assert release.wait(timeout=3.0)
        return original(paths, checkpoint=checkpoint)

    monkeypatch.setattr(registration, "_discovery_function", blocked_discovery)
    written: list[str] = []
    original_write = recent.repository._storage.set_value

    def record_write(key: str, value: object) -> None:
        written.append(key)
        original_write(key, value)

    monkeypatch.setattr(recent.repository._storage, "set_value", record_write)
    try:
        if command == "dialog":
            monkeypatch.setattr(
                QFileDialog, "getOpenFileNames", lambda *_a, **_k: ([str(path)], "")
            )
            window.action_map["Open Images..."].trigger()
        else:
            recent.open_recent(RecentEntryKind.IMAGE, path)
        qtbot.waitUntil(started.is_set)  # type: ignore[attr-defined]
        turns: list[bool] = []
        QTimer.singleShot(0, lambda: turns.append(True))
        qtbot.waitUntil(lambda: bool(turns))  # type: ignore[attr-defined]
        assert window.selected_documents == [seed]
        assert list(window.documents) == [seed.document_id]
        assert not registration.is_idle
        assert written == []
    finally:
        release.set()
    qtbot.waitUntil(lambda: registration.is_idle)  # type: ignore[attr-defined]
    selected = window.selected_documents
    assert len(selected) == 1 and selected[0].source_path == path.resolve()
    assert seed.document_id in window.documents
    assert recent.repository.load(RecentEntryKind.IMAGE) == (path.resolve(),)
    assert written == []
    assert registration._deferred_recent
    window.viewer.first_frame_painted.emit(selected[0].document_id)
    qtbot.waitUntil(lambda: "recent/images" in written)  # type: ignore[attr-defined]
    assert not registration._deferred_recent
    window.close()


def test_open_preserves_natural_order_without_drop_difference_and_reloads_same_path(
    qtbot: object, tmp_path: Path
) -> None:
    a, b = _image(tmp_path / "a.png", 11), _image(tmp_path / "b.png", 22)
    window = _window(qtbot)
    seed = ImageDocument.from_array(np.zeros((8, 12), dtype=np.uint8), "seed")
    window.add_document(seed)
    registration = window.large_folder_registration_controller
    window.open_image_paths([b, a, b])
    qtbot.waitUntil(lambda: registration.is_idle)  # type: ignore[attr-defined]
    assert [item.source_path for item in window.selected_documents] == [a.resolve(), b.resolve()]
    qtbot.waitUntil(lambda: not window._workers)  # type: ignore[attr-defined]
    assert window.quick_compare_controller._pending_difference_pair is None
    assert window.difference_panel._worker is None
    assert not window.diff_action.isChecked()
    assert len(window.documents) == 3
    document = window.selected_documents[0]
    generation = document.generation
    _image(a, 93)
    window.recent_entries_controller.open_recent(RecentEntryKind.IMAGE, a)
    qtbot.waitUntil(lambda: registration.is_idle and not window._workers)  # type: ignore[attr-defined]
    reloaded = window.selected_documents[0]
    assert [item.document_id for item in window.selected_documents] == [document.document_id]
    assert window.documents[document.document_id] is reloaded
    assert len(window.documents) == 3
    assert reloaded.generation == generation + 1
    assert reloaded.source is not None and int(reloaded.source[0, 0, 0]) == 93
    window.close()


def test_queued_open_replacements_and_following_drop_keep_distinct_selection_intents(
    qtbot: object, tmp_path: Path
) -> None:
    a, b, c = (
        _image(tmp_path / f"{name}.png", value)
        for name, value in zip("abc", (1, 2, 3), strict=True)
    )
    window = _window(qtbot)
    registration = window.large_folder_registration_controller
    window.open_image_paths([a])
    window.open_image_paths([b])
    registration.enqueue([c])
    qtbot.waitUntil(lambda: registration.is_idle)  # type: ignore[attr-defined]
    assert [item.source_path for item in window.selected_documents] == [b.resolve(), c.resolve()]
    assert len(window.documents) == 3
    window.close()


def test_open_batch_keeps_all_selected_but_loads_only_first_page(
    qtbot: object, tmp_path: Path
) -> None:
    paths = [_image(tmp_path / f"{index}.png", index) for index in range(8)]
    window = _window(qtbot)
    registration = window.large_folder_registration_controller
    window.open_image_paths(paths)
    qtbot.waitUntil(lambda: registration.is_idle and not window._workers)  # type: ignore[attr-defined]
    assert [item.source_path for item in window.selected_documents] == paths
    assert len(window.current_comparison_documents()) == 6
    assert all(item.source is not None for item in window.selected_documents[:6])
    assert all(item.source is None for item in window.selected_documents[6:])
    window.close()


def test_cancelled_open_and_skipped_raw_do_not_replace_existing_selection(
    qtbot: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = _image(tmp_path / "cancel.png", 7)
    window = _window(qtbot)
    seed = ImageDocument.from_array(np.zeros((8, 12), dtype=np.uint8), "seed")
    window.add_document(seed)
    registration = window.large_folder_registration_controller
    started, release = Event(), Event()
    original = registration._discovery_function

    def blocked_discovery(paths: object, *, checkpoint: object) -> RegistrationDiscovery:
        started.set()
        assert release.wait(timeout=3.0)
        return original(paths, checkpoint=checkpoint)

    monkeypatch.setattr(registration, "_discovery_function", blocked_discovery)
    try:
        window.open_image_paths([path])
        qtbot.waitUntil(started.is_set)  # type: ignore[attr-defined]
        registration.cancel_active()
    finally:
        release.set()
    qtbot.waitUntil(lambda: registration.pool.activeThreadCount() == 0)  # type: ignore[attr-defined]
    assert window.selected_documents == [seed]
    assert len(window.documents) == 1
    assert not registration._active_replace_selection
    monkeypatch.setattr(registration, "_discovery_function", original)
    raw = tmp_path / "skipped.raw"
    raw.write_bytes(bytes(64))
    monkeypatch.setattr(window, "_confirm_raw_profile", lambda *_a, **_k: None)
    window.open_image_paths([raw, tmp_path])
    qtbot.waitUntil(lambda: registration.is_idle)  # type: ignore[attr-defined]
    assert window.selected_documents == [seed]
    assert len(window.documents) == 1
    assert window.statusBar().currentMessage() == "No supported images opened"
    window.close()
