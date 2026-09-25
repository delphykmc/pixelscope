from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QMessageBox, QWidget

from pixelscope.app import main_window as main_window_module
from pixelscope.app import raw_input_compatibility as raw_compatibility_module
from pixelscope.app import yuv_input_semantics as yuv_semantics_module
from pixelscope.app.main_window import MainWindow
from pixelscope.app.raw_input_compatibility import RawInputCompatibilityController
from pixelscope.app.yuv_input_semantics import NativeYuvSemanticsController
from pixelscope.io.path_discovery import ImageInput
from pixelscope.ui import user_guide_help
from pixelscope.ui.raw_open_dialog import RawOpenDialog
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
from pixelscope.ui.yuv_open_dialog import YuvOpenDialog


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
    for dock in (window.bottom_dock, window.iqa_dock):
        assert len(dock.findChildren(QShortcut, "floatingContextHelpShortcut")) == 1
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
        (
            "User Guide unavailable",
            "This build does not include the local PixelScope User Guide bundle.",
        )
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
        (
            "Unable to open User Guide",
            "PixelScope could not open the local User Guide in the system browser.",
        )
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
    assert context_help_page(window, focus=window.difference_panel) == ("features/difference.html")
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
        window,
        index_path=index,
        page="features/histogram.html",
        opener=lambda url: opened.append(url) or True,
    )
    assert Path(opened[-1].toLocalFile()) == topic.resolve()

    assert open_local_user_guide(
        window,
        index_path=index,
        page="features/not-yet-built.html",
        opener=lambda url: opened.append(url) or True,
    )
    assert Path(opened[-1].toLocalFile()) == index.resolve()
    assert open_local_user_guide(
        window,
        index_path=index,
        page="../outside.html",
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


def test_floating_docks_own_separate_f1_routes(qtbot: Any, monkeypatch: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    install_user_guide_help(window)
    seen: list[str | None] = []

    def fake_open(_parent: object, *, page: str | None = None) -> bool:
        seen.append(page)
        return True

    monkeypatch.setattr(user_guide_help, "open_local_user_guide", fake_open)
    plots = window.bottom_dock.findChild(QShortcut, "floatingContextHelpShortcut")
    iqa = window.iqa_dock.findChild(QShortcut, "floatingContextHelpShortcut")
    assert plots is not None and iqa is not None
    window.bottom_tabs.setCurrentIndex(1)
    plots.activated.emit()
    iqa.activated.emit()
    assert seen == ["features/line-profile.html", "features/iqa-workspace.html"]
    window.close()


def _key_f1_on_actual_focus(
    qtbot: Any,
    widget: QWidget,
    seen: list[tuple[object, str | None]],
    parent: object,
    topic: str | None,
) -> None:
    """Exercise Qt's shortcut map, rather than invoking QAction/Signal callbacks."""
    assert widget.isVisible(), "F1 target must be a visible production widget"
    top_level = widget.window()
    top_level.activateWindow()
    QApplication.setActiveWindow(top_level)
    qtbot.waitUntil(lambda: QApplication.activeWindow() is top_level, timeout=3000)
    widget.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is widget, timeout=3000)
    before = len(seen)
    qtbot.keyClick(widget, Qt.Key.Key_F1)
    qtbot.waitUntil(lambda: len(seen) != before, timeout=3000)
    assert seen[before:] == [(parent, topic)], "ignored or ambiguous F1 shortcut"


def test_f1_real_key_dispatch_main_workspaces_and_presentation_controls(
    qtbot: Any, monkeypatch: Any
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    install_user_guide_help(window)
    seen: list[tuple[object, str | None]] = []

    def fake_open(parent: object, *, page: str | None = None) -> bool:
        seen.append((parent, page))
        return True

    monkeypatch.setattr(user_guide_help, "open_local_user_guide", fake_open)
    window.central_stack.setCurrentWidget(window.viewer)
    window.show()
    window.activateWindow()

    for widget, topic in (
        (window.document_list, "features/files-workspace.html"),
        (window.viewer._graphics, "features/image-view.html"),
        (window.layout_selector, "features/image-view.html"),
    ):
        _key_f1_on_actual_focus(qtbot, widget, seen, window, topic)

    for index, topic in (
        (0, "features/statistics.html"),
        (1, "features/difference.html"),
    ):
        window.analysis_tabs.setCurrentIndex(index)
        _key_f1_on_actual_focus(qtbot, window.analysis_tabs.tabBar(), seen, window, topic)
    window.close()


def test_f1_real_key_dispatch_docked_and_floating_analyses(qtbot: Any, monkeypatch: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    install_user_guide_help(window)
    seen: list[tuple[object, str | None]] = []

    def fake_open(parent: object, *, page: str | None = None) -> bool:
        seen.append((parent, page))
        return True

    monkeypatch.setattr(user_guide_help, "open_local_user_guide", fake_open)
    window.show()
    window.activateWindow()
    window.bottom_dock.show()
    for index, topic in (
        (0, "features/histogram.html"),
        (1, "features/line-profile.html"),
    ):
        window.bottom_tabs.setCurrentIndex(index)
        _key_f1_on_actual_focus(qtbot, window.bottom_tabs.tabBar(), seen, window, topic)

    window.iqa_dock.show()
    window.iqa_workspace.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    _key_f1_on_actual_focus(
        qtbot, window.iqa_workspace, seen, window, "features/iqa-workspace.html"
    )

    window.bottom_dock.setFloating(True)
    window.bottom_dock.show()
    window.bottom_dock.activateWindow()
    for index, topic in (
        (0, "features/histogram.html"),
        (1, "features/line-profile.html"),
    ):
        window.bottom_tabs.setCurrentIndex(index)
        _key_f1_on_actual_focus(qtbot, window.bottom_tabs.tabBar(), seen, window, topic)

    window.iqa_dock.setFloating(True)
    window.iqa_dock.show()
    window.iqa_dock.activateWindow()
    _key_f1_on_actual_focus(
        qtbot, window.iqa_workspace, seen, window, "features/iqa-workspace.html"
    )
    window.close()


def test_f1_real_key_dispatch_settings_dialog_with_child_focus(
    qtbot: Any, monkeypatch: Any
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    install_user_guide_help(window)
    window.show()
    dialog = window.create_settings_dialog()
    qtbot.addWidget(dialog)
    dialog.setModal(True)
    dialog.show()
    dialog.activateWindow()
    dialog.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    seen: list[tuple[object, str | None]] = []

    def fake_open(parent: object, *, page: str | None = None) -> bool:
        seen.append((parent, page))
        return True

    monkeypatch.setattr(user_guide_help, "open_local_user_guide", fake_open)
    assert len(dialog.findChildren(QShortcut, "contextHelpShortcut")) == 1
    _key_f1_on_actual_focus(qtbot, dialog, seen, dialog, "features/settings.html")
    dialog.close()
    window.close()


def test_f1_real_key_dispatch_from_actual_raw_and_yuv_construction_paths(
    qtbot: Any, monkeypatch: Any, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    install_user_guide_help(window)
    window.show()
    seen: list[tuple[object, str | None]] = []
    routes: list[tuple[str, str]] = []

    def fake_open(parent: object, *, page: str | None = None) -> bool:
        seen.append((parent, page))
        return True

    monkeypatch.setattr(user_guide_help, "open_local_user_guide", fake_open)

    def make_checked_dialog(
        cls: type[RawOpenDialog] | type[YuvOpenDialog], route: str
    ) -> type[RawOpenDialog] | type[YuvOpenDialog]:
        class CheckedDialog(cls):  # type: ignore[misc, valid-type]
            def exec(self) -> QDialog.DialogCode:
                assert len(self.findChildren(QShortcut, "contextHelpShortcut")) == 1
                shortcut = self.findChild(QShortcut, "contextHelpShortcut")
                assert shortcut is not None and shortcut.parent() is self
                self.setModal(True)
                self.show()
                self.activateWindow()
                _key_f1_on_actual_focus(qtbot, self.width_box, seen, self, route)
                routes.append((type(self).__name__, route))
                self.close()
                return QDialog.DialogCode.Rejected

        return CheckedDialog

    raw = tmp_path / "source.raw"
    raw.write_bytes(bytes(32))
    monkeypatch.setattr(
        main_window_module,
        "RawOpenDialog",
        make_checked_dialog(RawOpenDialog, "formats/raw.html"),
    )
    assert window._confirm_raw_profile(ImageInput(raw, None), None) is None

    imgprops = tmp_path / "source.imgprops"
    imgprops.write_text(
        '{"width":4,"height":4,"imageType":"BAYER12",'
        '"pattern":"RGGB","sensorBitWidth":12,"pedestal":64}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        raw_compatibility_module,
        "RawOpenDialog",
        make_checked_dialog(RawOpenDialog, "formats/raw.html"),
    )
    controller = RawInputCompatibilityController(window)
    assert controller.confirm_raw_profile(ImageInput(raw, imgprops), None) is None

    yuv = tmp_path / "source.yuv"
    yuv.write_bytes(bytes(24))
    monkeypatch.setattr(
        yuv_semantics_module,
        "YuvOpenDialog",
        make_checked_dialog(YuvOpenDialog, "formats/yuv.html"),
    )
    yuv_controller = NativeYuvSemanticsController(window)
    assert yuv_controller._show_yuv_dialog(yuv, None, None) is None
    assert [route for _, route in routes] == [
        "formats/raw.html",
        "formats/raw.html",
        "formats/yuv.html",
    ]
    window.close()


@pytest.mark.parametrize(
    ("topic_exists", "page"),
    (
        (True, "features/histogram.html"),
        (False, "features/not-yet-built.html"),
    ),
)
def test_context_help_error_paths_never_open_online(
    qtbot: Any,
    monkeypatch: Any,
    tmp_path: Path,
    topic_exists: bool,
    page: str,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    index = tmp_path / "help" / "index.html"
    index.parent.mkdir()
    index.write_text("index", encoding="utf-8")
    topic = index.parent / "features" / "histogram.html"
    topic.parent.mkdir()
    if topic_exists:
        topic.write_text("topic", encoding="utf-8")

    opened: list[QUrl] = []
    warnings: list[tuple[str, str]] = []
    online: list[str] = []

    def failed_open(url: QUrl) -> bool:
        opened.append(url)
        return False

    def warning(_parent: object, title: str, message: str) -> None:
        warnings.append((title, message))

    monkeypatch.setattr(QMessageBox, "warning", warning)
    monkeypatch.setattr(
        user_guide_help,
        "open_online_documentation",
        lambda *_args, **_kwargs: online.append("unexpected") or False,
    )
    assert not open_local_user_guide(window, index_path=index, page=page, opener=failed_open)
    assert len(opened) == 1 and opened[0].isLocalFile()
    assert Path(opened[0].toLocalFile()) == (topic.resolve() if topic_exists else index.resolve())
    assert warnings == [
        (
            "Unable to open User Guide",
            "PixelScope could not open the local User Guide in the system browser.",
        )
    ]
    assert online == []

    missing_messages: list[tuple[str, str]] = []

    def information(_parent: object, title: str, message: str) -> None:
        missing_messages.append((title, message))

    monkeypatch.setattr(QMessageBox, "information", information)
    assert not open_local_user_guide(
        window,
        index_path=tmp_path / "missing" / "index.html",
        page="features/histogram.html",
        opener=failed_open,
    )
    assert missing_messages == [
        (
            "User Guide unavailable",
            "This build does not include the local PixelScope User Guide bundle.",
        )
    ]
    assert len(opened) == 1
    assert online == []
    window.close()
