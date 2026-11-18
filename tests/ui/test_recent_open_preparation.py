from __future__ import annotations

from pathlib import Path
from threading import Event, get_ident

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.app.path_preparation import path_preparation
from pixelscope.app.settings import ApplicationSettings
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.recent_entries import RecentEntryKind

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


@pytest.mark.parametrize("kind", [RecentEntryKind.FOLDER, RecentEntryKind.SESSION])
def test_recent_network_probe_yields_and_cancellation_rejects_late_result(qtbot, monkeypatch, kind):
    window = MainWindow()
    qtbot.addWidget(window)
    compose_main_window_presentation(window)
    path = Path("//pixelscope-offline.invalid/share/item")
    entered, release = Event(), Event()
    gui = get_ident()
    original = Path.stat

    def stat(candidate, *args, **kwargs):
        if "pixelscope-offline.invalid" in str(candidate):
            assert get_ident() != gui, "Recent network stat ran on the GUI thread"
            entered.set()
            assert release.wait(5), "test did not release held network call"
            raise FileNotFoundError(str(candidate))
        return original(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    feedback = []
    recent = window.recent_entries_controller
    monkeypatch.setattr(recent, "_confirm_remove_missing", lambda *args: feedback.append(args))
    turns = []
    QTimer.singleShot(0, lambda: turns.append(True))
    try:
        recent.open_recent(kind, path)
        qtbot.waitUntil(lambda: entered.is_set() and bool(turns))
        if kind is RecentEntryKind.FOLDER:
            window.large_folder_registration_controller.cancel_active()
        else:
            window.path_preparation_controller.cancel()
        release.set()
        if kind is RecentEntryKind.FOLDER:
            qtbot.waitUntil(
                lambda: window.large_folder_registration_controller.pool.activeThreadCount() == 0
            )
        else:
            qtbot.waitUntil(lambda: window.path_preparation_controller.is_idle)
        assert feedback == []
        assert not window.documents and not window.selected_documents
    finally:
        release.set()
        window.close()


def test_close_during_session_preflight_defers_and_fences_feedback(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    compose_main_window_presentation(window)
    window.show()
    entered, release = Event(), Event()
    original = Path.stat

    def stat(path, *args, **kwargs):
        if "pixelscope-offline.invalid" in str(path):
            entered.set()
            assert release.wait(5)
            raise FileNotFoundError(str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    recent = window.recent_entries_controller
    feedback = []
    monkeypatch.setattr(recent, "_confirm_remove_missing", lambda *args: feedback.append(args))
    try:
        recent.open_recent(
            RecentEntryKind.SESSION, Path("//pixelscope-offline.invalid/share/a.pixelscope")
        )
        qtbot.waitUntil(entered.is_set)
        window.close()
        assert window.isVisible()
        turns = []
        QTimer.singleShot(0, lambda: turns.append(True))
        qtbot.waitUntil(lambda: bool(turns))
        release.set()
        qtbot.waitUntil(lambda: not window.isVisible())
        assert feedback == []
        assert not window.documents
    finally:
        release.set()
        window.close()


@pytest.mark.parametrize("cancel", [False, True])
def test_dialog_directory_validation_yields_then_falls_back_or_cancels(
    qtbot,
    monkeypatch,
    tmp_path,
    cancel,
):
    offline = "//pixelscope-offline.invalid/share/directory"
    settings = ApplicationSettings(default_open_directory=offline)
    window = MainWindow(settings, settings.performance_settings())
    qtbot.addWidget(window)
    window._last_directory = str(tmp_path)
    entered, release = Event(), Event()
    gui = get_ident()
    original = Path.is_dir

    def is_dir(path):
        if "pixelscope-offline.invalid" in str(path):
            assert get_ident() != gui, "Dialog directory checked on GUI thread"
            entered.set()
            assert release.wait(5)
            return False
        return original(path)

    monkeypatch.setattr(Path, "is_dir", is_dir)
    dialogs = []
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        lambda _parent, _title, directory, _filter: (dialogs.append(directory) or ([], "")),
    )
    try:
        window.open_images()
        turns = []
        QTimer.singleShot(0, lambda: turns.append(True))
        qtbot.waitUntil(lambda: entered.is_set() and bool(turns))
        assert dialogs == []
        if cancel:
            window.path_preparation_controller.cancel_button.click()
        release.set()
        qtbot.waitUntil(lambda: window.path_preparation_controller.is_idle)
        assert dialogs == ([] if cancel else [str(tmp_path)])
        assert not window.documents
    finally:
        release.set()
        window.close()


def test_superseding_preparation_is_bounded_and_only_latest_result_can_commit(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    controller = path_preparation(window)
    entered, release = Event(), Event()
    results, errors = [], []

    def held():
        entered.set()
        assert release.wait(5)
        return "old"

    try:
        controller.submit(held, (), results.append, errors.append)
        qtbot.waitUntil(entered.is_set)
        for number in range(10):
            controller.submit(str, (number,), results.append, errors.append)
        assert controller.pool.maxThreadCount() == 1
        assert controller.pool.activeThreadCount() == 1
        assert controller._worker._function is held
        release.set()
        qtbot.waitUntil(lambda: controller.is_idle)
        assert results == ["9"]
        assert errors == []
    finally:
        release.set()
        window.close()


def test_prepared_session_commit_does_not_resolve_source_paths_again(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    compose_main_window_presentation(window)
    source = tmp_path / "frame.png"
    pixels = np.zeros((4, 4), dtype=np.uint8)
    assert cv2.imwrite(str(source), pixels)
    document = ImageDocument.from_array(pixels, "frame.png", source_path=source)
    window.add_document(document)
    target = tmp_path / "workspace.pixelscope"
    window.session_controller.save_to_path(target)
    gui = get_ident()
    original = Path.resolve
    calls = []

    def resolve(path, *args, **kwargs):
        if path == source:
            calls.append(get_ident())
            assert get_ident() != gui, "Session commit repeated filesystem canonicalization"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    try:
        window.recent_entries_controller.open_recent(RecentEntryKind.SESSION, target)
        qtbot.waitUntil(lambda: window.path_preparation_controller.is_idle)
        assert calls and all(thread != gui for thread in calls)
        assert [item.document_id for item in window.selected_documents] == [document.document_id]
    finally:
        window.close()
