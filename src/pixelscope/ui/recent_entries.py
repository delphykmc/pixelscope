from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable

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
    """Typed recent-entry UI that observes and delegates to existing runtime authorities."""

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
            raise RuntimeError(
                "Recent Entries requires the P4-B Comparison Set controller"
            )
        self.comparison_set_controller = comparison_set
        self.comparison_set_controller.set_recent_entry_callback(
            self._record_comparison_set
        )

        file_menu = getattr(comparison_set, "_file_menu_ref", None)
        if not isinstance(file_menu, QMenu):
            raise RuntimeError("Recent Entries requires the retained File menu")
        self.file_menu = file_menu

        self.recent_menu = QMenu("Recent", self.file_menu)
        self.recent_menu.setStyleSheet(menu_style())
        self.images_menu = QMenu("Images", self.recent_menu)
        self.folders_menu = QMenu("Folders", self.recent_menu)
        self.comparison_sets_menu = QMenu("Comparison Sets", self.recent_menu)
        for menu in (self.images_menu, self.folders_menu, self.comparison_sets_menu):
            menu.setStyleSheet(menu_style())
        self.clear_action = QAction("Clear Recent Entries", window)
        self.clear_action.triggered.connect(self.clear_all)  # type: ignore[attr-defined]

        self._install_runtime_observers()
        self._install_recent_menu()
        self.refresh_menu()

    def _settings(self) -> QSettings:
        settings = getattr(self.window, "settings", None)
        return settings if isinstance(settings, QSettings) else QSettings()

    def _install_runtime_observers(self) -> None:
        """Observe P3 entry APIs without rewiring constructor-time Qt signals."""

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

    def _observe_history(
        self,
        kind: RecentEntryKind,
        paths: Sequence[str | Path],
    ) -> None:
        """Best-effort observer boundary; Recent must never own workflow correctness."""

        try:
            self.repository.record(kind, paths)
            self.refresh_menu()
        except Exception:  # noqa: BLE001 - optional history must not break runtime work
            LOGGER.warning(
                "Unable to update Recent %s history",
                kind.value,
                exc_info=True,
            )

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
        leaf = path.name or str(path)
        parent = path.parent.name
        return f"{leaf} — {parent}" if parent and parent != leaf else leaf

    def open_recent(self, kind: RecentEntryKind, path: Path) -> None:
        if not self._entry_exists(kind, path):
            self._remove_missing(kind, path)
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
        self._observe_history(RecentEntryKind.COMPARISON_SET, [path])
        self.comparison_set_controller.show_open_feedback(path, loaded, missing)

    def _entry_exists(self, kind: RecentEntryKind, path: Path) -> bool:
        if kind is RecentEntryKind.FOLDER:
            return path.is_dir()
        return path.is_file()

    def _remove_missing(self, kind: RecentEntryKind, path: Path) -> None:
        try:
            self.repository.remove(kind, path)
            self.refresh_menu()
        except Exception:  # noqa: BLE001 - stale-entry cleanup is also non-authoritative
            LOGGER.warning(
                "Unable to remove unavailable Recent %s entry",
                kind.value,
                exc_info=True,
            )
        QMessageBox.warning(
            self.window,
            "Recent entry unavailable",
            f"The saved {kind.value.replace('_', ' ')} path is no longer available. "
            "It was removed from Recent Entries when possible.\n\n"
            f"{path}",
        )

    def _record_comparison_set(self, path: Path) -> None:
        self._observe_history(RecentEntryKind.COMPARISON_SET, [path])

    def clear_all(self) -> None:
        try:
            self.repository.clear()
            self.refresh_menu()
        except Exception as exc:  # noqa: BLE001 - report history-storage failure to user
            QMessageBox.warning(
                self.window,
                "Cannot clear Recent Entries",
                str(exc),
            )
            return
        self.window.statusBar().showMessage("Recent Entries cleared", 3000)

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
