from __future__ import annotations

import logging
import stat
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox

from pixelscope.app.recent_entries import RecentEntriesRepository
from pixelscope.app.settings import QSettingsAdapter
from pixelscope.core.comparison_set import ComparisonSetError
from pixelscope.core.recent_entries import RecentEntryKind
from pixelscope.io.path_discovery import ImageInput, discover_image_inputs
from pixelscope.ui.comparison_set import ComparisonSetController
from pixelscope.ui.design_tokens import menu_style

LOGGER = logging.getLogger(__name__)


class RecentEntriesController:
    """Typed Recent UI that observes and reuses canonical entry workflows."""

    def __init__(
        self,
        window: Any,
        repository: RecentEntriesRepository | None = None,
    ) -> None:
        self.window = window
        self.repository = repository or RecentEntriesRepository(QSettingsAdapter(self._settings()))
        comparison_set = getattr(window, "comparison_set_controller", None)
        if not isinstance(comparison_set, ComparisonSetController):
            raise RuntimeError("Recent Entries requires the Comparison Set controller")
        self.comparison_set_controller = comparison_set

        file_menu = getattr(comparison_set, "_file_menu_ref", None)
        if not isinstance(file_menu, QMenu):
            raise RuntimeError("Recent Entries requires the retained File menu")
        self.file_menu = file_menu

        self.images_menu = QMenu("Open Recent Images", self.file_menu)
        self.folders_menu = QMenu("Open Recent Folders", self.file_menu)
        self.comparison_sets_menu = QMenu("Open Recent Comparison Sets", self.file_menu)
        for menu in (self.images_menu, self.folders_menu, self.comparison_sets_menu):
            menu.setStyleSheet(menu_style())

        self._install_runtime_observers()
        self._install_comparison_set_observers()
        self._install_recent_menus()
        self.refresh_menu()

    def _settings(self) -> QSettings:
        settings = getattr(self.window, "settings", None)
        return settings if isinstance(settings, QSettings) else QSettings()

    def _install_runtime_observers(self) -> None:
        register_inputs = getattr(self.window, "_register_inputs", None)
        register_folders = getattr(self.window, "register_folders", None)
        if not callable(register_inputs) or not callable(register_folders):
            raise RuntimeError("Recent Entries requires the P3 registration APIs")

        self._register_inputs_original: Callable[..., list[str]] = register_inputs
        self._register_folders_original: Callable[..., Any] = register_folders

        def observed_register_inputs(
            inputs: tuple[ImageInput, ...],
            *,
            resolve_raw_profiles: bool,
        ) -> list[str]:
            document_ids = self._register_inputs_original(
                inputs,
                resolve_raw_profiles=resolve_raw_profiles,
            )
            if resolve_raw_profiles and document_ids:
                paths = [
                    document.source_path
                    for document_id in document_ids
                    if (document := self.window.documents.get(document_id)) is not None
                    and document.source_path is not None
                ]
                if paths:
                    self._observe_history(RecentEntryKind.IMAGE, paths)
            return document_ids

        def observed_register_folders(folders: Sequence[Path]) -> Any:
            supplied = tuple(Path(folder).resolve(strict=False) for folder in folders)
            result = self._register_folders_original(folders)
            existing = tuple(folder for folder in supplied if folder.is_dir())
            if existing:
                self._observe_history(RecentEntryKind.FOLDER, existing)
            return result

        self.window._register_inputs = observed_register_inputs
        self.window.register_folders = observed_register_folders

    def _install_comparison_set_observers(self) -> None:
        open_from_path = self.comparison_set_controller.open_from_path
        save_to_path = self.comparison_set_controller.save_to_path
        self._comparison_set_open_original = open_from_path
        self._comparison_set_save_original = save_to_path

        def observed_open_from_path(path: str | Path) -> tuple[int, tuple[Path, ...]]:
            loaded, missing = self._comparison_set_open_original(path)
            if loaded > 0:
                self._observe_history(RecentEntryKind.COMPARISON_SET, [path])
            return loaded, missing

        def observed_save_to_path(path: str | Path) -> object:
            result = self._comparison_set_save_original(path)
            self._observe_history(RecentEntryKind.COMPARISON_SET, [path])
            return result

        setattr(self.comparison_set_controller, "open_from_path", observed_open_from_path)
        setattr(self.comparison_set_controller, "save_to_path", observed_save_to_path)

    def _observe_history(
        self,
        kind: RecentEntryKind,
        paths: Sequence[str | Path],
    ) -> None:
        try:
            self.repository.record(kind, paths)
            self.refresh_menu()
        except Exception:  # noqa: BLE001 - history must not affect canonical workflows
            LOGGER.warning("Unable to update Recent %s history", kind.value, exc_info=True)

    def _install_recent_menus(self) -> None:
        actions = self.file_menu.actions()
        open_folder_action = self.window.action_map.get("Open Folder...")
        open_action = self.comparison_set_controller.open_action
        save_action = self.comparison_set_controller.save_action

        if isinstance(open_folder_action, QAction):
            folder_index = actions.index(open_folder_action)
            open_index = actions.index(open_action)
            for action in actions[folder_index + 1 : open_index]:
                if action.isSeparator():
                    self.file_menu.removeAction(action)

        for menu in (self.images_menu, self.folders_menu, self.comparison_sets_menu):
            self.file_menu.insertMenu(save_action, menu)
        separator = QAction(self.window)
        separator.setSeparator(True)
        self.file_menu.insertAction(save_action, separator)
        self.recent_group_separator = separator

    def refresh_menu(self) -> None:
        self._populate_menu(RecentEntryKind.IMAGE, self.images_menu, "Images")
        self._populate_menu(RecentEntryKind.FOLDER, self.folders_menu, "Folders")
        self._populate_menu(
            RecentEntryKind.COMPARISON_SET,
            self.comparison_sets_menu,
            "Comparison Sets",
        )

    def _populate_menu(
        self,
        kind: RecentEntryKind,
        menu: QMenu,
        clear_label: str,
    ) -> None:
        menu.clear()
        entries = self.repository.load(kind)
        if not entries:
            placeholder = menu.addAction("(None)")
            placeholder.setEnabled(False)
        else:
            for path in entries:
                action = menu.addAction(self._display_label(path))
                action.setToolTip(str(path))
                action.setStatusTip(str(path))
                action.triggered.connect(  # type: ignore[attr-defined]
                    lambda _checked=False, entry_kind=kind, entry_path=path: self.open_recent(
                        entry_kind,
                        entry_path,
                    )
                )
        menu.addSeparator()
        clear_action = menu.addAction(f"Clear Recent {clear_label}")
        clear_action.setEnabled(bool(entries))
        clear_action.triggered.connect(  # type: ignore[attr-defined]
            lambda _checked=False, entry_kind=kind: self.clear_kind(entry_kind)
        )

    @staticmethod
    def _display_label(path: Path) -> str:
        leaf = path.name or str(path)
        parent = path.parent.name
        return f"{leaf} — {parent}" if parent and parent != leaf else leaf

    def open_recent(self, kind: RecentEntryKind, path: Path) -> None:
        path_state = self._recent_path_state(kind, path)
        if path_state == "missing":
            self._handle_missing_entry(kind, path)
            return
        if path_state == "wrong_type":
            self._show_wrong_type(kind, path)
            return
        if kind is RecentEntryKind.IMAGE:
            self._open_image_paths([path])
            return
        if kind is RecentEntryKind.FOLDER:
            result = self.window.register_folders([path])
            self._remember_directory(path)
            if result.image_count > 0:
                self.window.statusBar().showMessage(
                    f"Registered {result.image_count} image(s) from recent folder",
                    4000,
                )
            else:
                self.window.statusBar().showMessage(
                    "Recent folder contains no supported images",
                    4000,
                )
            return
        self._open_recent_comparison_set(path)

    def _open_image_paths(self, paths: list[Path]) -> list[str]:
        if not paths:
            return []
        self._remember_directory(paths[0].parent)
        document_ids = list(
            self.window._register_inputs(
                discover_image_inputs(paths),
                resolve_raw_profiles=True,
            )
        )
        if document_ids:
            self.window._select_document_ids(document_ids)
            self.window.statusBar().showMessage(
                f"Opened {len(document_ids)} image(s)",
                4000,
            )
        else:
            self.window.statusBar().showMessage("No supported images opened", 4000)
        return document_ids

    def _open_recent_comparison_set(self, path: Path) -> None:
        try:
            loaded, missing = self.comparison_set_controller.open_from_path(path)
        except (OSError, ComparisonSetError) as exc:
            QMessageBox.warning(self.window, "Cannot open Comparison Set", str(exc))
            return
        if loaded == 0:
            return
        self._remember_directory(path.parent)
        if missing:
            preview = "\n".join(str(item) for item in missing[:5])
            suffix = f"\n… and {len(missing) - 5} more" if len(missing) > 5 else ""
            QMessageBox.warning(
                self.window,
                "Comparison Set opened with missing sources",
                f"Loaded {loaded} source(s); {len(missing)} source(s) were unavailable.\n\n"
                f"{preview}{suffix}",
            )
        self.window.statusBar().showMessage(
            f"Opened Comparison Set · {loaded} source(s)",
            4000,
        )

    @staticmethod
    def _recent_path_state(kind: RecentEntryKind, path: Path) -> str:
        try:
            path_stat = path.stat()
        except FileNotFoundError:
            return "missing"
        except OSError:
            return "unknown"
        if kind is RecentEntryKind.FOLDER:
            return "usable" if stat.S_ISDIR(path_stat.st_mode) else "wrong_type"
        return "usable" if stat.S_ISREG(path_stat.st_mode) else "wrong_type"

    def _show_wrong_type(self, kind: RecentEntryKind, path: Path) -> None:
        expected = "folder" if kind is RecentEntryKind.FOLDER else "file"
        QMessageBox.warning(
            self.window,
            "Recent entry unavailable",
            f"This Recent entry is no longer a {expected}. The history entry was kept.\n\n{path}",
        )

    def _handle_missing_entry(self, kind: RecentEntryKind, path: Path) -> None:
        if not self._confirm_remove_missing(kind, path):
            return
        try:
            self.repository.remove(kind, path)
            self.refresh_menu()
        except Exception:  # noqa: BLE001 - cleanup remains non-authoritative
            LOGGER.warning(
                "Unable to remove unavailable Recent %s entry",
                kind.value,
                exc_info=True,
            )

    def _confirm_remove_missing(self, kind: RecentEntryKind, path: Path) -> bool:
        item_type = "folder" if kind is RecentEntryKind.FOLDER else "file"
        dialog = QMessageBox(self.window)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle("Recent entry unavailable")
        dialog.setText(f"The {item_type} cannot be found. Remove it from Recent Entries?")
        dialog.setInformativeText(str(path))
        remove_button = dialog.addButton("Remove", QMessageBox.ButtonRole.DestructiveRole)
        keep_button = dialog.addButton("Keep", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(keep_button)
        dialog.exec()
        return dialog.clickedButton() is remove_button

    def clear_kind(self, kind: RecentEntryKind) -> None:
        try:
            self.repository.clear(kind)
            self.refresh_menu()
        except Exception as exc:  # noqa: BLE001 - report history-storage failure to user
            QMessageBox.warning(self.window, "Cannot clear Recent Entries", str(exc))
            return
        self.window.statusBar().showMessage(
            f"Recent {self._kind_label(kind)} cleared",
            3000,
        )

    def clear_all(self) -> None:
        try:
            self.repository.clear()
            self.refresh_menu()
        except Exception as exc:  # noqa: BLE001 - report history-storage failure to user
            QMessageBox.warning(self.window, "Cannot clear Recent Entries", str(exc))
            return
        self.window.statusBar().showMessage("Recent Entries cleared", 3000)

    @staticmethod
    def _kind_label(kind: RecentEntryKind) -> str:
        if kind is RecentEntryKind.IMAGE:
            return "Images"
        if kind is RecentEntryKind.FOLDER:
            return "Folders"
        return "Comparison Sets"

    def _remember_directory(self, path: Path) -> None:
        remember = getattr(self.window, "_remember_directory", None)
        if callable(remember):
            remember(path)


def install_recent_entries(
    window: Any,
    repository: RecentEntriesRepository | None = None,
) -> RecentEntriesController:
    existing = getattr(window, "recent_entries_controller", None)
    if isinstance(existing, RecentEntriesController):
        return existing
    controller = RecentEntriesController(window, repository)
    window.recent_entries_controller = controller
    return controller
