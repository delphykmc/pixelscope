from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTabWidget,
    QWidget,
)

_USER_GUIDE_ACTION_OBJECT_NAME = "userGuideAction"
_ONLINE_GUIDE_ACTION_OBJECT_NAME = "onlineDocumentationAction"
_CONTEXT_HELP_ACTION_OBJECT_NAME = "contextHelpAction"
_DIALOG_CONTEXT_HELP_OBJECT_NAME = "contextHelpShortcut"

# Only set after the owner confirms a published, approved, authoritative URL.
# The installed app does not infer a GitHub Pages URL or probe the network.
ONLINE_DOCUMENTATION_URL: str | None = None


def user_guide_candidates(
    *,
    frozen: bool | None = None,
    executable_path: Path | None = None,
    source_root: Path | None = None,
) -> tuple[Path, ...]:
    """Return local User Guide entry-point candidates in authoritative order."""

    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if is_frozen:
        executable = executable_path or Path(sys.executable)
        return (executable.resolve().parent / "help" / "index.html",)

    root = source_root or Path(__file__).resolve().parents[3]
    return (
        root / "site" / "index.html",
        root / "help" / "index.html",
    )


def resolve_local_user_guide_index(
    *,
    frozen: bool | None = None,
    executable_path: Path | None = None,
    source_root: Path | None = None,
) -> Path | None:
    """Resolve an existing local User Guide index without depending on CWD."""

    for candidate in user_guide_candidates(
        frozen=frozen,
        executable_path=executable_path,
        source_root=source_root,
    ):
        if candidate.is_file():
            return candidate
    return None


def open_local_user_guide(
    parent: QWidget,
    *,
    index_path: Path | None = None,
    page: str | None = None,
    opener: Callable[[QUrl], bool] | None = None,
) -> bool:
    """Open the local User Guide in the platform browser, with explicit failure UX."""

    resolved = index_path or resolve_local_user_guide_index()
    if resolved is None or not resolved.is_file():
        QMessageBox.information(
            parent,
            "User Guide unavailable",
            "This build does not include the local PixelScope User Guide bundle.",
        )
        return False

    target = resolved.resolve()
    if page is not None:
        candidate = (target.parent / page).resolve()
        # A missing page falls back to the local index; never navigate outside
        # the installed bundle, guess an online URL, or show a broken file URL.
        if candidate.is_relative_to(target.parent) and candidate.is_file():
            target = candidate

    open_url = opener or QDesktopServices.openUrl
    if open_url(QUrl.fromLocalFile(str(target))):
        return True

    QMessageBox.warning(
        parent,
        "Unable to open User Guide",
        "PixelScope could not open the local User Guide in the system browser.",
    )
    return False


def context_help_page(window: QMainWindow, *, focus: QWidget | None = None) -> str | None:
    """Map the focused production workspace to an existing local MkDocs HTML route.

    Focus takes precedence over whichever other dock happens to be visible.
    Unrecognized focus (including an empty window/menu) uses the guide home.
    """
    widget = QApplication.focusWidget() if focus is None else focus
    if widget is None or not (widget is window or window.isAncestorOf(widget)):
        return None

    def within(parent: QWidget) -> bool:
        return widget is parent or parent.isAncestorOf(widget)

    iqa_dock = getattr(window, "iqa_dock", None)
    if isinstance(iqa_dock, QWidget) and iqa_dock.isVisible() and within(iqa_dock):
        return "features/iqa-workspace.html"

    plots_dock = getattr(window, "bottom_dock", None)
    plots = getattr(window, "bottom_tabs", None)
    if isinstance(plots_dock, QWidget) and plots_dock.isVisible() and within(plots_dock):
        if isinstance(plots, QTabWidget) and plots.currentIndex() == 1:
            return "features/line-profile.html"
        return "features/histogram.html"

    files = getattr(window, "document_list", None)
    if isinstance(files, QWidget) and within(files):
        return "features/files-workspace.html"

    analysis = getattr(window, "analysis_tabs", None)
    if isinstance(analysis, QWidget) and within(analysis):
        return (
            "features/difference.html"
            if analysis.currentIndex() == 1
            else "features/statistics.html"
        )

    presentation = getattr(window, "central_stack", None)
    controls = getattr(window, "presentation_controls", None)
    if (
        isinstance(presentation, QWidget)
        and within(presentation)
        or isinstance(controls, QWidget)
        and within(controls)
    ):
        return "features/image-view.html"
    return None


def _install_floating_dock_context_help(window: QMainWindow) -> None:
    """F1 also works when Plots/IQA becomes a separate top-level dock window."""
    for dock_name in ("bottom_dock", "iqa_dock"):
        dock = getattr(window, dock_name, None)
        if not isinstance(dock, QDockWidget):
            continue
        if dock.findChild(QShortcut, "floatingContextHelpShortcut") is not None:
            continue
        shortcut = QShortcut(QKeySequence(Qt.Key.Key_F1), dock)
        shortcut.setObjectName("floatingContextHelpShortcut")
        shortcut.setEnabled(dock.isFloating())
        dock.topLevelChanged.connect(shortcut.setEnabled)  # type: ignore[attr-defined]
        if dock_name == "bottom_dock":
            tabs = dock.widget()
            shortcut.activated.connect(  # type: ignore[attr-defined]
                lambda tabs=tabs: open_local_user_guide(
                    window,
                    page=(
                        "features/line-profile.html"
                        if isinstance(tabs, QTabWidget) and tabs.currentIndex() == 1
                        else "features/histogram.html"
                    ),
                )
            )
        else:
            shortcut.activated.connect(  # type: ignore[attr-defined]
                lambda: open_local_user_guide(window, page="features/iqa-workspace.html")
            )


def install_dialog_context_help(dialog: object, page: str) -> QShortcut | None:
    """Give real modal dialogs F1; preserve non-QWidget profile test doubles."""
    if not isinstance(dialog, QWidget):
        return None
    existing = dialog.findChild(QShortcut, _DIALOG_CONTEXT_HELP_OBJECT_NAME)
    if isinstance(existing, QShortcut):
        return existing
    shortcut = QShortcut(QKeySequence(Qt.Key.Key_F1), dialog)
    shortcut.setObjectName(_DIALOG_CONTEXT_HELP_OBJECT_NAME)
    shortcut.activated.connect(  # type: ignore[attr-defined]
        lambda: open_local_user_guide(dialog, page=page)
    )
    return shortcut


def validate_online_documentation_url(value: str) -> str:
    """Require an explicitly approved HTTPS documentation origin."""
    parts = urlsplit(value)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Online Documentation requires an approved HTTPS URL")
    return value


def open_online_documentation(
    parent: QMainWindow,
    url: str,
    *,
    opener: Callable[[QUrl], bool] | None = None,
) -> bool:
    """Open only the configured online documentation, never as a local fallback."""
    approved = validate_online_documentation_url(url)
    open_url = opener or QDesktopServices.openUrl
    if open_url(QUrl(approved)):
        return True
    QMessageBox.warning(
        parent,
        "Unable to open Online Documentation",
        "PixelScope could not open the online documentation in the system browser.",
    )
    return False


def _find_help_menu(window: QMainWindow) -> QMenu:
    menu_map = getattr(window, "_menu_map", None)
    if isinstance(menu_map, dict):
        help_menu = menu_map.get("Help")
        if isinstance(help_menu, QMenu):
            return help_menu
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        if isinstance(menu, QMenu) and menu.title().replace("&", "") == "Help":
            return menu
    raise RuntimeError("PixelScope Help menu is unavailable")


def install_user_guide_help(window: QMainWindow, *, online_url: str | None = None) -> QAction:
    """Install local Help and optionally add a separately approved online action."""

    help_menu = _find_help_menu(window)
    local = next(
        (
            action
            for action in help_menu.actions()
            if action.objectName() == _USER_GUIDE_ACTION_OBJECT_NAME
        ),
        None,
    )
    if local is None:
        local = QAction("User Guide", window)
        local.setObjectName(_USER_GUIDE_ACTION_OBJECT_NAME)
        local.setStatusTip("Open the local PixelScope User Guide")
        local.triggered.connect(  # type: ignore[attr-defined]
            lambda _checked=False: open_local_user_guide(window)
        )

        first_action = help_menu.actions()[0] if help_menu.actions() else None
        if first_action is None:
            help_menu.addAction(local)
        else:
            help_menu.insertAction(first_action, local)
            help_menu.insertSeparator(first_action)

    context = next(
        (
            action
            for action in help_menu.actions()
            if action.objectName() == _CONTEXT_HELP_ACTION_OBJECT_NAME
        ),
        None,
    )
    if context is None:
        context = QAction("Context Help", window)
        context.setObjectName(_CONTEXT_HELP_ACTION_OBJECT_NAME)
        context.setShortcut(QKeySequence(Qt.Key.Key_F1))
        context.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        context.setStatusTip("Open help for the focused PixelScope workspace")
        context.triggered.connect(  # type: ignore[attr-defined]
            lambda _checked=False: open_local_user_guide(window, page=context_help_page(window))
        )
        separator = next(
            (action for action in help_menu.actions() if action.isSeparator()),
            None,
        )
        if separator is None:
            help_menu.addAction(context)
        else:
            help_menu.insertAction(separator, context)

    _install_floating_dock_context_help(window)

    approved = ONLINE_DOCUMENTATION_URL if online_url is None else online_url
    if approved is not None:
        approved = validate_online_documentation_url(approved)
        already_installed = any(
            action.objectName() == _ONLINE_GUIDE_ACTION_OBJECT_NAME
            for action in help_menu.actions()
        )
        if not already_installed:
            online = QAction("Online Documentation", window)
            online.setObjectName(_ONLINE_GUIDE_ACTION_OBJECT_NAME)
            online.setStatusTip("Open the approved PixelScope documentation website")
            online.triggered.connect(  # type: ignore[attr-defined]
                lambda _checked=False: open_online_documentation(window, approved)
            )
            separator = next(
                (action for action in help_menu.actions() if action.isSeparator()),
                None,
            )
            if separator is None:
                help_menu.addAction(online)
            else:
                help_menu.insertAction(separator, online)
    return local
