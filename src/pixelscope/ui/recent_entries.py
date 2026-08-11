from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

from pixelscope.app.recent_entries import RecentEntriesRepository
from pixelscope.app.settings import QSettingsAdapter
from pixelscope.core.comparison_set import ComparisonSetError
from pixelscope.core.recent_entries import RecentEntryKind
from pixelscope.io.path_discovery import SUPPORTED_IMAGE_FILTER, discover_image_inputs
from pixelscope.ui.comparison_set import COMPARISON_SET_FILTER, ComparisonSetController
from pixelscope.ui.design_tokens import menu_style


class RecentEntriesController:
    """Typed recent-entry UI that delegates to existing P3/P4 runtime authorities."""

    def __init__(
        self,
        window: Any,
        repository: RecentEntriesRepository | None = None,
    ) -> None:
        self.window = window
        self.repository = repository or RecentEntriesRepository(
            QSettingsAdapter(self._settings())
        )
        comparison_set = getattr(window, "comparison_set_controller", None)
        if not isinstance(comparison_set, ComparisonSetController):
            raise RuntimeError("Recent Entries requires the P4-B Comparison Set controller")
        self.comparison_set_controller = comparison_set
        self.comparison_set_controller.set_recent_entry_callback(
            self._record_comparison_set
        )

        file_menu = getattr(comparison_set, "_file_menu_ref", None)
        if not isinstance(file_menu, QMenu):
            raise RuntimeError("Recent Entries requires the retained File menu")
        self.file_menu = file_menu

        self.open_images_action = QAction("Open Images...", window)
        self.open_images_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_images_action.triggered.connect(self.open_images_dialog)  # type: ignore[attr-defined]
        self.open_folder_action = QAction("Open Folder...", window)
        self.open_folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_folder_action.triggered.connect(self.open_folder_dialog)  # type: ignore[attr-defined]

        self.recent_menu = QMenu("Recent", self.file_menu)
        self.recent_menu.setStyleSheet(menu_style())
        self.images_menu = QMenu("Images", self.recent_menu)
        self.folders_menu = QMenu("Folders", self.recent_menu)
        self.comparison_sets_menu = QMenu("Comparison Sets", self.recent_menu)
        for menu in (self.images_menu, self.folders_menu, self.comparison_sets_menu):
            menu.setStyleSheet(menu_style())
        self.clear_action = QAction("Clear Recent Entries", window)
        self.clear_action.triggered.connect(self.clear_all)  # type: ignore[attr-defined]

        self._replace_primary_entry_actions()
        self._install_recent_menu()
        self.refresh_menu()

    def _settings(self) -> QSettings:
        settings = getattr(self.window, "settings", None)
        return settings if isinstance(settings, QSettings) else QSettings()

    def _replace_primary_entry_actions(self) -> None:
        """Replace only File-menu entry actions; keep MainWindow methods authoritative."""

        for name, replacement in (
            ("Open Images...", self.open_images_action),
            ("Open Folder...", self.open_folder_action),
        ):
            legacy = self.window.action_map.get(name)
            if isinstance(legacy, QAction):
                self.file_menu.removeAction(legacy)
                legacy.setShortcut(QKeySequence())
            self.window.action_map[name] = replacement

        actions = self.file_menu.actions()
        anchor = next(
            (action for action in actions if action.text().startswith("Open Comparison Set")),
            None,
        )
        if anchor is None:
            actions = self.file_menu.actions()
            anchor = actions[0] if actions else None
        if anchor is None:
            self.file_menu.addAction(self.open_images_action)
            self.file_menu.addAction(self.open_folder_action)
        else:
            self.file_menu.insertAction(anchor, self.open_images_action)
            self.file_menu.insertAction(anchor, self.open_folder_action)

    def _install_recent_menu(self) -> None:
        actions = self.file_menu.actions()
        save_action = self.comparison_set_controller.save_action
        if save_action in actions:
            self.file_menu.insertMenu(save_action, self.recent_menu)
        else:
            self.file_menu.addMenu(self.recent_menu)

    def refresh_menu(self) -> None:
        self._populate_menu(RecentEntryKind.IMAGE, self.images_menu)
        self._populate_menu(RecentEntryKind.FOLDER, self.folders_menu)
        self._populate_menu(RecentEntryKind.COMPARISON_SET, self.comparison_sets_menu)
        self.recent_menu.clear()
        self.recent_menu.addMenu(self.images_menu)
        self.recent_menu.addMenu(self.folders_menu)
        self.recent_menu.addMenu(self.comparison_sets_menu)
        self.recent_menu.addSeparator()
        self.recent_menu.addAction(self.clear_action)
        self.clear_action.setEnabled(
            any(self.repository.load(kind) for kind in RecentEntryKind)
        )

    def _populate_menu(self, kind: RecentEntryKind, menu: QMenu) -> None:
        menu.clear()
        entries = self.repository.load(kind)
        if not entries:
            placeholder = menu.addAction("(None)")
            placeholder.setEnabled(False)
            return
        for path in entries:
            action = menu.addAction(self._display_label(kind, path))
            action.setToolTip(str(path))
            action.setStatusTip(str(path))
            action.triggered.connect(  # type: ignore[attr-defined]
                lambda _checked=False, entry_kind=kind, entry_path=path: self.open_recent(
                    entry_kind,
                    entry_path,
                )
            )

    @staticmethod
    def _display_label(kind: RecentEntryKind, path: Path) -> str:
        if kind is RecentEntryKind.FOLDER:
            leaf = path.name or str(path)
        else:
            leaf = path.name
        parent = path.parent.name
        return f"{leaf} — {parent}" if parent and parent != leaf else leaf

    def open_images_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self.window,
            "Open images",
            self._dialog_directory(),
            SUPPORTED_IMAGE_FILTER,
        )
        if not paths:
            return
        supplied = [Path(path) for path in paths]
        document_ids = self._open_image_paths(supplied)
        if document_ids:
            opened_paths = [
                self.window.documents[document_id].source_path
                for document_id in document_ids
                if self.window.documents[document_id].source_path is not None
            ]
            self.repository.record(RecentEntryKind.IMAGE, opened_paths)
            self.refresh_menu()

    def open_folder_dialog(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self.window,
            "Open image folder",
            self._dialog_directory(),
        )
        if not path:
            return
        folder = Path(path)
        result = self.window.register_folders([folder])
        self._remember_directory(folder)
        if result.image_count > 0:
            self.repository.record(RecentEntryKind.FOLDER, [folder])
            self.refresh_menu()
            self.window.statusBar().showMessage(
                f"Registered {result.image_count} image(s) from 1 folder",
                4000,
            )
        else:
            self.window.statusBar().showMessage("No supported images found in folder", 4000)

    def open_recent(self, kind: RecentEntryKind, path: Path) -> None:
        if not self._entry_exists(kind, path):
            self._remove_missing(kind, path)
            return
        if kind is RecentEntryKind.IMAGE:
            document_ids = self._open_image_paths([path])
            if document_ids:
                self.repository.record(kind, [path])
                self.refresh_menu()
            return
        if kind is RecentEntryKind.FOLDER:
            result = self.window.register_folders([path])
            self._remember_directory(path)
            if result.image_count > 0:
                self.repository.record(kind, [path])
                self.refresh_menu()
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
        self.repository.record(RecentEntryKind.COMPARISON_SET, [path])
        self.refresh_menu()
        self.comparison_set_controller.show_open_feedback(path, loaded, missing)

    def _entry_exists(self, kind: RecentEntryKind, path: Path) -> bool:
        if kind is RecentEntryKind.FOLDER:
            return path.is_dir()
        return path.is_file()

    def _remove_missing(self, kind: RecentEntryKind, path: Path) -> None:
        self.repository.remove(kind, path)
        self.refresh_menu()
        QMessageBox.warning(
            self.window,
            "Recent entry unavailable",
            f"The saved {kind.value.replace('_', ' ')} path is no longer available. "
            "It was removed from Recent Entries.\n\n"
            f"{path}",
        )

    def _record_comparison_set(self, path: Path) -> None:
        self.repository.record(RecentEntryKind.COMPARISON_SET, [path])
        self.refresh_menu()

    def clear_all(self) -> None:
        self.repository.clear()
        self.refresh_menu()
        self.window.statusBar().showMessage("Recent Entries cleared", 3000)

    def _dialog_directory(self) -> str:
        getter = getattr(self.window, "_open_dialog_directory", None)
        return str(getter()) if callable(getter) else ""

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
