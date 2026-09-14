from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QMenu

from pixelscope.app.main_window import MainWindow
from pixelscope.ui import user_guide_help
from pixelscope.ui.user_guide_help import (
    install_user_guide_help,
    open_local_user_guide,
    resolve_local_user_guide_index,
    user_guide_candidates,
)


def _help_menu(window: MainWindow) -> QMenu:
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        if menu is not None and menu.title().replace("&", "") == "Help":
            return menu
    raise AssertionError("Help menu not found")


def test_frozen_user_guide_candidate_is_relative_to_executable(tmp_path: Path) -> None:
    executable = tmp_path / "PixelScope.exe"

    assert user_guide_candidates(frozen=True, executable_path=executable) == (
        tmp_path / "help" / "index.html",
    )


def test_source_user_guide_prefers_built_site_then_help_bundle(tmp_path: Path) -> None:
    site_index = tmp_path / "site" / "index.html"
    site_index.parent.mkdir()
    site_index.write_text("site", encoding="utf-8")
    help_index = tmp_path / "help" / "index.html"
    help_index.parent.mkdir()
    help_index.write_text("help", encoding="utf-8")

    assert resolve_local_user_guide_index(frozen=False, source_root=tmp_path) == site_index

    site_index.unlink()
    assert resolve_local_user_guide_index(frozen=False, source_root=tmp_path) == help_index


def test_install_user_guide_help_places_action_before_diagnostics(qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    action = install_user_guide_help(window)
    install_user_guide_help(window)

    assert action.objectName() == "userGuideAction"
    assert [item.text() for item in _help_menu(window).actions()] == [
        "User Guide",
        "",
        "Copy Diagnostics",
    ]
    window.close()


def test_user_guide_action_delegates_to_local_open(qtbot: Any, monkeypatch: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    calls: list[MainWindow] = []

    def fake_open(parent: MainWindow) -> bool:
        calls.append(parent)
        return True

    monkeypatch.setattr(user_guide_help, "open_local_user_guide", fake_open)
    action = install_user_guide_help(window)
    action.trigger()

    assert calls == [window]
    window.close()


def test_open_local_user_guide_uses_local_file_url(tmp_path: Path, qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    index_path = tmp_path / "help" / "index.html"
    index_path.parent.mkdir()
    index_path.write_text("guide", encoding="utf-8")
    opened: list[QUrl] = []

    def opener(url: QUrl) -> bool:
        opened.append(url)
        return True

    assert open_local_user_guide(window, index_path=index_path, opener=opener)
    assert len(opened) == 1
    assert opened[0].isLocalFile()
    assert Path(opened[0].toLocalFile()) == index_path.resolve()
    window.close()
