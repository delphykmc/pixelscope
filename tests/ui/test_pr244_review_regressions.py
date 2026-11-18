"""PR #244 independent review regressions: close veto and exclusive Session commit."""
from __future__ import annotations

from pathlib import Path
from threading import Event

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QTimer

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.app.path_preparation import path_preparation
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.recent_entries import RecentEntryKind
from pixelscope.io.path_discovery import RegistrationDiscovery
from pixelscope.io.session_preparation import prepare_recent_session

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    compose_main_window_presentation(window)
    return window


def _document(tmp_path: Path, name: str, value: int) -> ImageDocument:
    path = tmp_path / name
    pixels = np.full((6, 6), value, dtype=np.uint8)
    assert cv2.imwrite(str(path), pixels)
    return ImageDocument.from_array(pixels, name, source_path=path)


def test_idle_close_veto_keeps_both_worker_controllers_usable(qtbot, monkeypatch, tmp_path):
    window = _window(qtbot)
    window.show()
    preparation = path_preparation(window)
    registration = window.large_folder_registration_controller
    review = window.named_review_coordinator
    monkeypatch.setattr(review, "confirm_close", lambda: False)
    try:
        assert not window.close()
        assert window.isVisible()
        assert not preparation._closing
        assert not registration._closing
        values = []
        preparation.submit(str, ("ok",), values.append, lambda error: pytest.fail(str(error)))
        qtbot.waitUntil(lambda: preparation.is_idle and values == ["ok"], timeout=5000)
        empty = tmp_path / "empty"
        empty.mkdir()
        registration.enqueue((empty,))
        qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)
        assert not registration._closing
    finally:
        monkeypatch.setattr(review, "confirm_close", lambda: True)
        window.close()


def test_inflight_close_veto_does_not_cancel_preparation(qtbot, monkeypatch):
    window = _window(qtbot)
    window.show()
    preparation = path_preparation(window)
    review = window.named_review_coordinator
    monkeypatch.setattr(review, "confirm_close", lambda: False)
    entered, release = Event(), Event()
    values = []

    def held():
        entered.set()
        assert release.wait(5)
        return "ready"

    try:
        preparation.submit(held, (), values.append, lambda error: pytest.fail(str(error)))
        qtbot.waitUntil(entered.is_set)
        assert not window.close()
        assert not preparation._closing
        assert preparation.pool.activeThreadCount() == 1
        release.set()
        qtbot.waitUntil(lambda: preparation.is_idle and values == ["ready"], timeout=5000)
        monkeypatch.setattr(review, "confirm_close", lambda: True)
        window.close()
        assert window._closing
    finally:
        release.set()
        monkeypatch.setattr(review, "confirm_close", lambda: True)
        window.close()


def test_session_commit_waits_for_revoked_discovery_and_discards_queue(qtbot, tmp_path):
    window = _window(qtbot)
    seed = _document(tmp_path, "session.png", 13)
    window.add_document(seed)
    saved = tmp_path / "exclusive.pixelscope"
    window.session_controller.save_to_path(saved)
    extra = _document(tmp_path, "extra.png", 31)
    window.add_document(extra)

    registration = window.large_folder_registration_controller
    entered, release = Event(), Event()

    def held_discovery(_paths, *, checkpoint):
        del checkpoint
        entered.set()
        assert release.wait(5)
        return RegistrationDiscovery((), 0, 0, ())

    registration._discovery_function = held_discovery
    try:
        registration.enqueue((tmp_path / "blocked",))
        qtbot.waitUntil(entered.is_set)
        registration.enqueue((tmp_path / "queued",))
        window.recent_entries_controller.open_recent(RecentEntryKind.SESSION, saved)
        qtbot.waitUntil(
            lambda: window.recent_entries_controller._pending_session_restore is not None,
            timeout=5000,
        )
        assert not registration._queue
        assert extra.document_id in window.documents
        release.set()
        qtbot.waitUntil(
            lambda: (
                window.recent_entries_controller._pending_session_restore is None
                and registration.pool.activeThreadCount() == 0
                and set(window.documents) == {seed.document_id}
            ),
            timeout=6000,
        )
        assert [doc.document_id for doc in window.selected_documents] == [seed.document_id]
    finally:
        release.set()
        window.close()


def test_session_supersedes_scheduled_registration_chunk(qtbot, tmp_path):
    window = _window(qtbot)
    seed = _document(tmp_path, "saved.png", 18)
    window.add_document(seed)
    saved = tmp_path / "chunk.pixelscope"
    window.session_controller.save_to_path(saved)
    prepared = prepare_recent_session(saved, window.session_controller.repository)
    folder = tmp_path / "many"
    folder.mkdir()
    for index in range(8):
        _document(folder, f"frame{index}.png", index + 1)

    registration = window.large_folder_registration_controller
    registration.chunk_size = 1
    registration.slice_budget_ms = 10000
    invoked = []

    def after_chunk(phase, completed, total):
        if phase == "registering" and completed == 1 and total == 8 and not invoked:
            invoked.append(True)
            QTimer.singleShot(
                0, lambda: window.recent_entries_controller._session_prepared(prepared)
            )

    registration.progress_changed.connect(after_chunk)
    try:
        registration.enqueue((folder,))
        qtbot.waitUntil(
            lambda: (
                invoked
                and registration.is_idle
                and set(window.documents) == {seed.document_id}
            ),
            timeout=6000,
        )
        assert registration.progress.phase == "idle"
        assert len(window.documents) == 1
    finally:
        window.close()


def test_recent_folder_does_not_store_missing_or_cancelled_directory(qtbot, monkeypatch, tmp_path):
    window = _window(qtbot)
    registration = window.large_folder_registration_controller
    recent = window.recent_entries_controller
    previous = tmp_path / "valid"
    previous.mkdir()
    window._remember_directory(previous)
    monkeypatch.setattr(recent, "_confirm_remove_missing", lambda *_args: False)
    try:
        recent.open_recent(RecentEntryKind.FOLDER, tmp_path / "missing")
        qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)
        assert window._last_directory == str(previous)
        assert window.settings.value("paths/last_directory") == str(previous)
        valid = tmp_path / "present"
        valid.mkdir()
        recent.open_recent(RecentEntryKind.FOLDER, valid)
        qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)
        assert window._last_directory == str(valid)
    finally:
        window.close()


def test_blocked_session_a_is_fenced_when_session_b_opens(qtbot, monkeypatch, tmp_path):
    import pixelscope.ui.recent_entries as recent_module

    window = _window(qtbot)
    a = _document(tmp_path, "a.png", 15)
    window.add_document(a)
    path_a = tmp_path / "a.pixelscope"
    window.session_controller.save_to_path(path_a)
    window._remove_document_ids([a.document_id])
    b = _document(tmp_path, "b.png", 25)
    window.add_document(b)
    path_b = tmp_path / "b.pixelscope"
    window.session_controller.save_to_path(path_b)
    window._remove_document_ids([b.document_id])
    original = recent_module.prepare_recent_session
    entered, release = Event(), Event()

    def blocked_prepare(path, repository):
        if path == path_a:
            entered.set()
            assert release.wait(5)
        return original(path, repository)

    monkeypatch.setattr(recent_module, "prepare_recent_session", blocked_prepare)
    try:
        recent = window.recent_entries_controller
        recent.open_recent(RecentEntryKind.SESSION, path_a)
        qtbot.waitUntil(entered.is_set)
        recent.open_recent(RecentEntryKind.SESSION, path_b)
        release.set()
        qtbot.waitUntil(
            lambda: (
                window.path_preparation_controller.is_idle
                and [doc.document_id for doc in window.selected_documents] == [b.document_id]
            ),
            timeout=6000,
        )
        assert a.document_id not in window.documents
    finally:
        release.set()
        window.close()
