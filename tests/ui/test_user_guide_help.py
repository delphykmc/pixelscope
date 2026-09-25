from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QMenu, QMessageBox, QShortcut

from pixelscope.app.main_window import MainWindow
from pixelscope.ui import user_guide_help
from pixelscope.ui.user_guide_help import (
    context_help_page,
    install_dialog_context_help,
    install_user_guide_help,
    open_local_user_guide,
    open_online_documentation,
    resolve_local_user_guide_index,
    user_guide_candidates,
    validate_online_documentation_url,
)


def _help_menu(window: MainWindow) -> QMenu:
    menu = window._menu_map["Help"]
    assert isinstance(menu, QMenu)
    return menu


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
    context = next(a for a in _help_menu(window).actions() if a.text() == "Context Help")
    assert context.shortcut().toString() == "F1"
    assert len([a for a in _help_menu(window).actions() if a.text() == "Context Help"]) == 1
    assert [item.text() for item in _help_menu(window).actions()] == [
        "User Guide",
        "Context Help",
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


def test_unconfigured_online_documentation_is_not_in_help_menu(qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    install_user_guide_help(window)

    assert "Online Documentation" not in [item.text() for item in _help_menu(window).actions()]
    window.close()


def test_opted_in_online_documentation_is_separate_and_idempotent(qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    url = "https://docs.example.org/pixelscope/"
    local = install_user_guide_help(window)
    install_user_guide_help(window, online_url=url)
    install_user_guide_help(window, online_url=url)

    assert local.objectName() == "userGuideAction"
    assert [item.text() for item in _help_menu(window).actions()] == [
        "User Guide",
        "Context Help",
        "Online Documentation",
        "",
        "Copy Diagnostics",
    ]
    window.close()


def test_online_documentation_opens_approved_https_only(
    qtbot: Any,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    opened: list[QUrl] = []

    def opener(url: QUrl) -> bool:
        opened.append(url)
        return True

    url = "https://docs.example.org/pixelscope/"
    assert open_online_documentation(window, url, opener=opener)
    assert len(opened) == 1
    assert opened[0].toString() == url
    assert not opened[0].isLocalFile()
    window.close()


def test_online_documentation_rejects_unapproved_protocols() -> None:
    for value in (
        "http://docs.example.org/",
        "file:///etc/index.html",
        "https://user:token@docs.example.org/",
        "https://docs.example.org/?access_token=secret",
    ):
        with pytest.raises(ValueError, match="approved HTTPS"):
            validate_online_documentation_url(value)


def test_missing_local_guide_shows_explicit_message(
    tmp_path: Path, qtbot: Any, monkeypatch: Any
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    shown: list[tuple[str, str]] = []

    def information(_parent: Any, title: str, message: str) -> None:
        shown.append((title, message))

    monkeypatch.setattr(QMessageBox, "information", information)
    assert not open_local_user_guide(window, index_path=tmp_path / "missing.html")
    assert shown == [
        ("User Guide unavailable", "This build does not include the local PixelScope User Guide bundle.")
    ]
    window.close()


def test_local_browser_failure_does_not_open_online(
    tmp_path: Path, qtbot: Any, monkeypatch: Any
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    index = tmp_path / "index.html"
    index.write_text("guide", encoding="utf-8")
    shown: list[tuple[str, str]] = []

    def warning(_parent: Any, title: str, message: str) -> None:
        shown.append((title, message))

    monkeypatch.setattr(QMessageBox, "warning", warning)
    assert not open_local_user_guide(window, index_path=index, opener=lambda _url: False)
    assert shown == [
        ("Unable to open User Guide", "PixelScope could not open the local User Guide in the system browser.")
    ]
    window.close()


def test_context_help_routes_from_focused_workspace(qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert context_help_page(window, focus=window.document_list) == "features/files-workspace.html"
    assert context_help_page(window, focus=window.viewer) == "features/image-view.html"
    assert context_help_page(window, focus=window.comparison_analysis_panel.table) == (
        "features/statistics.html"
    )
    window.analysis_tabs.setCurrentIndex(1)
    assert context_help_page(window, focus=window.difference_panel) == (
        "features/difference.html"
    )
    assert context_help_page(window, focus=window) is None
    window.close()


def test_f1_action_opens_focused_topic(qtbot: Any, monkeypatch: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    install_user_guide_help(window)
    seen: list[tuple[object, str | None]] = []

    def fake_open(parent: object, *, page: str | None = None) -> bool:
        seen.append((parent, page))
        return True

    monkeypatch.setattr(user_guide_help, "open_local_user_guide", fake_open)
    monkeypatch.setattr(
        user_guide_help, "context_help_page", lambda _window: "features/files-workspace.html"
    )
    action = next(a for a in _help_menu(window).actions() if a.text() == "Context Help")
    action.trigger()
    assert seen == [(window, "features/files-workspace.html")]
    window.close()


def test_local_context_help_uses_installed_topic_or_index_fallback(
    tmp_path: Path, qtbot: Any
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    index = tmp_path / "help" / "index.html"
    index.parent.mkdir()
    index.write_text("index", encoding="utf-8")
    topic = index.parent / "features" / "histogram.html"
    topic.parent.mkdir()
    topic.write_text("topic", encoding="utf-8")
    opened: list[QUrl] = []

    assert open_local_user_guide(
        window, index_path=index, page="features/histogram.html",
        opener=lambda url: opened.append(url) or True,
    )
    assert Path(opened[-1].toLocalFile()) == topic.resolve()

    assert open_local_user_guide(
        window, index_path=index, page="features/not-yet-built.html",
        opener=lambda url: opened.append(url) or True,
    )
    assert Path(opened[-1].toLocalFile()) == index.resolve()
    assert open_local_user_guide(
        window, index_path=index, page="../outside.html",
        opener=lambda url: opened.append(url) or True,
    )
    assert Path(opened[-1].toLocalFile()) == index.resolve()
    window.close()


def test_modal_dialog_f1_has_own_shortcut_and_opens_offline_topic(
    qtbot: Any, monkeypatch: Any
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    dialog = window.create_settings_dialog()
    qtbot.addWidget(dialog)
    shortcut = dialog.findChild(QShortcut, "contextHelpShortcut")
    assert shortcut is not None and shortcut.key().toString() == "F1"
    assert install_dialog_context_help(dialog, "features/settings.html") is shortcut
    seen: list[tuple[object, str | None]] = []

    def fake_open(parent: object, *, page: str | None = None) -> bool:
        seen.append((parent, page))
        return True

    monkeypatch.setattr(user_guide_help, "open_local_user_guide", fake_open)
    shortcut.activated.emit()
    assert seen == [(dialog, "features/settings.html")]
    dialog.close()
    window.close()


def test_dialog_f1_installer_preserves_non_qwidget_profile_test_doubles() -> None:
    assert install_dialog_context_help(object(), "formats/raw.html") is None
