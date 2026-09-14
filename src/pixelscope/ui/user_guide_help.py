from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QMainWindow, QMenu, QMessageBox

_USER_GUIDE_ACTION_OBJECT_NAME = "userGuideAction"


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
    parent: QMainWindow,
    *,
    index_path: Path | None = None,
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

    open_url = opener or QDesktopServices.openUrl
    if open_url(QUrl.fromLocalFile(str(resolved.resolve()))):
        return True

    QMessageBox.warning(
        parent,
        "Unable to open User Guide",
        "PixelScope could not open the local User Guide in the system browser.",
    )
    return False


def _find_help_menu(window: QMainWindow) -> QMenu:
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        if menu is not None and menu.title().replace("&", "") == "Help":
            return menu
    raise RuntimeError("PixelScope Help menu is unavailable")


def install_user_guide_help(window: QMainWindow) -> QAction:
    """Install Help > User Guide ahead of diagnostic/support actions."""

    existing = window.findChild(QAction, _USER_GUIDE_ACTION_OBJECT_NAME)
    if existing is not None:
        return existing

    help_menu = _find_help_menu(window)
    action = QAction("User Guide", window)
    action.setObjectName(_USER_GUIDE_ACTION_OBJECT_NAME)
    action.setStatusTip("Open the local PixelScope User Guide")
    action.triggered.connect(lambda _checked=False: open_local_user_guide(window))  # type: ignore[attr-defined]

    first_action = help_menu.actions()[0] if help_menu.actions() else None
    if first_action is None:
        help_menu.addAction(action)
    else:
        help_menu.insertAction(first_action, action)
        help_menu.insertSeparator(first_action)
    return action
