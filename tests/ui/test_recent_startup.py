"""Cold Recent-menu composition never probes stored network paths."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QTimer

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.recent_entries import RecentEntryKind

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _guard_offline_paths(monkeypatch):
    calls = []
    for method in ("resolve", "stat", "exists", "is_file", "is_dir"):
        original = getattr(Path, method)

        def guarded(path, *args, _original=original, _method=method, **kwargs):
            if "pixelscope-offline.invalid" in str(path):
                calls.append(_method)
                pytest.fail(f"Startup/Recent bookkeeping called Path.{_method} on offline history")
            return _original(path, *args, **kwargs)

        monkeypatch.setattr(Path, method, guarded)
    return calls


def test_production_startup_with_stale_unc_history_yields_without_probes(qtbot, monkeypatch):
    settings = QSettings()
    root = Path("//pixelscope-offline.invalid/share")
    image, folder, session = root / "frame.png", root / "dataset", root / "review.pixelscope"
    values = {
        "recent/images": json.dumps([str(image), str(root / "unused" / ".." / "frame.png")]),
        "recent/folders": json.dumps([str(folder)]),
        "recent/comparison_sets": json.dumps([str(session)]),
    }
    for key, value in values.items():
        settings.setValue(key, value)
    window = MainWindow()
    qtbot.addWidget(window)
    with monkeypatch.context() as patch:
        calls = _guard_offline_paths(patch)
        compose_main_window_presentation(window)
        window.show()
        turns = []
        QTimer.singleShot(0, lambda: turns.append(True))
        qtbot.waitUntil(lambda: window.isVisible() and bool(turns))
        recent = window.recent_entries_controller
        assert recent.repository.load(RecentEntryKind.IMAGE) == (image,)
        assert recent.repository.load(RecentEntryKind.FOLDER) == (folder,)
        assert recent.repository.load(RecentEntryKind.SESSION) == (session,)
        assert "frame.png" in recent.images_menu.actions()[0].text()
        assert "dataset" in recent.folders_menu.actions()[0].text()
        assert "review.pixelscope" in recent.sessions_menu.actions()[0].text()
        recent.refresh_menu()
        assert calls == []
        assert all(settings.value(key) == value for key, value in values.items())
        assert not window.documents and not window.selected_documents
    window.close()


def test_successful_session_history_notification_does_not_resolve_target(qtbot, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    compose_main_window_presentation(window)
    path = Path("//pixelscope-offline.invalid/share/saved.pixelscope")
    with monkeypatch.context() as patch:
        calls = _guard_offline_paths(patch)
        window.session_controller._notify_recent_entry(path)
        assert window.recent_entries_controller.repository.load(RecentEntryKind.SESSION) == (path,)
        assert calls == []
    window.close()
