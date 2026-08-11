from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

from pixelscope.core.comparison_set import (
    ComparisonSet,
    ComparisonSetError,
    ComparisonSetSource,
)
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.io.path_discovery import ImageInput, image_input_for_path
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.design_tokens import menu_style

COMPARISON_SET_FILTER = "PixelScope Comparison Set (*.pixelscope)"


class ComparisonSetController:
    """Bridge Comparison Set artifacts to existing MainWindow runtime authorities."""

    def __init__(
        self,
        window: Any,
        repository: ComparisonSetRepository | None = None,
    ) -> None:
        self.window = window
        self.repository = repository or ComparisonSetRepository()
        self.open_action = QAction("Open Comparison Set...", window)
        self.save_action = QAction("Save Comparison Set...", window)
        self.open_action.setToolTip("Open a saved logical comparison set")
        self.save_action.setToolTip(
            "Save the current logical Selected set; temporary Picks are not saved. "
            "Use Keep Selection first to save a curated subset."
        )
        self.open_action.triggered.connect(self.open_dialog)  # type: ignore[attr-defined]
        self.save_action.triggered.connect(self.save_dialog)  # type: ignore[attr-defined]
        self._install_file_menu_actions()

    def _file_menu(self) -> QMenu:
        menu_bar = self.window.menuBar()
        for action in menu_bar.actions():
            if action.text().replace("&", "") != "File":
                continue
            try:
                menu = action.menu()
                if menu is not None:
                    menu.actions()
                    return menu
            except RuntimeError:
                return self._replace_deleted_file_menu(action)
        raise RuntimeError("Comparison Set commands require the File menu")

    def _replace_deleted_file_menu(self, stale_action: QAction) -> QMenu:
        """Recreate File menu when PySide released its temporary menu wrapper."""

        menu_bar = self.window.menuBar()
        top_level_actions = menu_bar.actions()
        stale_index = top_level_actions.index(stale_action)
        insert_before = (
            top_level_actions[stale_index + 1]
            if stale_index + 1 < len(top_level_actions)
            else None
        )

        replacement = QMenu("&File", self.window)
        replacement.setStyleSheet(menu_style())
        action_map = self.window.action_map
        for name in ("Open Images...", "Open Folder..."):
            action = action_map.get(name)
            if isinstance(action, QAction):
                replacement.addAction(action)
        replacement.addSeparator()
        export_action = action_map.get("Export Statistics CSV...")
        if isinstance(export_action, QAction):
            replacement.addAction(export_action)
        replacement.addSeparator()
        exit_action = action_map.get("Exit")
        if isinstance(exit_action, QAction):
            replacement.addAction(exit_action)

        menu_bar.removeAction(stale_action)
        if insert_before is None:
            menu_bar.addMenu(replacement)
        else:
            menu_bar.insertMenu(insert_before, replacement)
        self._replacement_file_menu = replacement
        return replacement

    def _install_file_menu_actions(self) -> None:
        menu = self._file_menu()
        actions = menu.actions()
        anchor = next(
            (action for action in actions if action.text().startswith("Export Statistics")),
            None,
        )
        if anchor is None:
            menu.addAction(self.open_action)
            menu.addAction(self.save_action)
            return
        menu.insertAction(anchor, self.open_action)
        menu.insertAction(anchor, self.save_action)
        separator = QAction(self.window)
        separator.setSeparator(True)
        menu.insertAction(anchor, separator)
        self.separator_action = separator

    def _dialog_directory(self) -> str:
        getter = getattr(self.window, "_open_dialog_directory", None)
        return str(getter()) if callable(getter) else ""

    def save_dialog(self) -> None:
        if not self.window.selected_documents:
            self.window.statusBar().showMessage("No Selected images to save", 3000)
            return
        initial = self._dialog_directory()
        path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Save Comparison Set",
            initial,
            COMPARISON_SET_FILTER,
        )
        if not path:
            return
        target = Path(path)
        if target.suffix.casefold() != ".pixelscope":
            target = target.with_suffix(".pixelscope")
        try:
            self.save_to_path(target)
        except (OSError, ComparisonSetError) as exc:
            QMessageBox.warning(self.window, "Cannot save Comparison Set", str(exc))
            return
        remember = getattr(self.window, "_remember_directory", None)
        if callable(remember):
            remember(target.parent)
        self.window.statusBar().showMessage(
            f"Saved Comparison Set · {target.name}",
            4000,
        )

    def save_to_path(self, path: str | Path) -> ComparisonSet:
        selected = list(self.window.selected_documents)
        if not selected:
            raise ComparisonSetError("no logical Selected images to save")
        sources: list[ComparisonSetSource] = []
        for document in selected:
            if document.source_path is None:
                raise ComparisonSetError(
                    "Selected item has no persistent native source path: "
                    f"{document.display_name}"
                )
            profile = self.window._raw_profiles.get(document.document_id)
            if profile is None and isinstance(document.raw_profile, RawProfile):
                profile = document.raw_profile
            raw_payload = profile.dict() if isinstance(profile, RawProfile) else None
            sources.append(ComparisonSetSource(str(document.source_path), raw_payload))

        selected_ids = {document.document_id for document in selected}
        active_path = self._path_for_runtime_id(
            self.window._active_document_id,
            selected_ids,
        )
        current_page_ids = {
            document.document_id for document in self.window.current_comparison_documents()
        }
        primary_path = (
            self._path_for_runtime_id(self.window._focus_document_id, current_page_ids)
            if self.window._layout_mode != "Single View"
            else None
        )
        comparison_set = ComparisonSet(
            sources=tuple(sources),
            active_path=active_path,
            primary_path=primary_path,
            layout_mode=self.window._layout_mode,
        )
        self.repository.save(path, comparison_set)
        return comparison_set

    def _path_for_runtime_id(
        self,
        document_id: str | None,
        allowed_ids: set[str],
    ) -> str | None:
        if document_id is None or document_id not in allowed_ids:
            return None
        document = self.window.documents.get(document_id)
        return (
            str(document.source_path)
            if document is not None and document.source_path is not None
            else None
        )

    def open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open Comparison Set",
            self._dialog_directory(),
            COMPARISON_SET_FILTER,
        )
        if not path:
            return
        try:
            loaded, missing = self.open_from_path(path)
        except (OSError, ComparisonSetError) as exc:
            QMessageBox.warning(self.window, "Cannot open Comparison Set", str(exc))
            return
        if loaded == 0:
            return
        target = Path(path)
        remember = getattr(self.window, "_remember_directory", None)
        if callable(remember):
            remember(target.parent)
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

    def open_from_path(self, path: str | Path) -> tuple[int, tuple[Path, ...]]:
        comparison_set = self.repository.load(path)

        loadable: list[tuple[ComparisonSetSource, ImageInput]] = []
        missing: list[Path] = []
        for source in comparison_set.sources:
            source_path = Path(source.path)
            image_input = image_input_for_path(source_path)
            if image_input is None:
                missing.append(source_path)
            else:
                loadable.append((source, image_input))
        if not loadable:
            QMessageBox.warning(
                self.window,
                "Comparison Set sources unavailable",
                "None of the saved source paths are currently loadable. "
                "The workspace was not changed.",
            )
            return 0, tuple(missing)

        document_ids: list[str] = []
        path_to_id: dict[str, str] = {}
        for source, image_input in loadable:
            document_id = self.window._register_input(
                image_input,
                resolve_raw_profile=False,
            )
            if document_id is None:
                continue
            document_ids.append(document_id)
            path_to_id[source.path.casefold()] = document_id
            if source.raw_profile is not None:
                profile = RawProfile.parse_obj(source.raw_profile)
                self._apply_saved_raw_profile(document_id, profile)
        self.window._update_empty_workspace_state()
        if not document_ids:
            QMessageBox.warning(
                self.window,
                "Comparison Set sources unavailable",
                "None of the saved source paths could be registered. "
                "The logical selection was not changed.",
            )
            return 0, tuple(missing)

        active_id = (
            self._saved_member_id(comparison_set.active_path, path_to_id)
            or document_ids[0]
        )
        active_index = document_ids.index(active_id)
        self.window._current_index = active_index
        self.window._page_start = 0
        self.window._focus_document_id = None
        self.window._primary_page_slot = 0
        self.window._select_document_ids(document_ids, preserve_view=True)

        if comparison_set.layout_mode != self.window._layout_mode:
            self.window.set_layout_mode(comparison_set.layout_mode)

        primary_id = self._saved_member_id(comparison_set.primary_path, path_to_id)
        current_page_ids = {
            document.document_id for document in self.window.current_comparison_documents()
        }
        if (
            primary_id is not None
            and primary_id in current_page_ids
            and self.window._layout_mode != "Single View"
        ):
            self.window._set_focus_document(primary_id)

        active_document = self.window.documents.get(active_id)
        if active_document is not None:
            self.window._set_active_document(active_document)
        return len(document_ids), tuple(missing)

    @staticmethod
    def _saved_member_id(
        path: str | None,
        path_to_id: dict[str, str],
    ) -> str | None:
        return None if path is None else path_to_id.get(path.casefold())

    def _apply_saved_raw_profile(self, document_id: str, profile: RawProfile) -> None:
        document = self.window.documents[document_id]
        previous = self.window._raw_profiles.get(document_id)
        if previous is not None and previous == profile:
            return
        if document.source is not None and previous != profile:
            self.window._raw_profiles[document_id] = profile
            self.window._mark_raw_for_reload(document_id, profile)
            return
        self.window._raw_profiles[document_id] = profile
        document.raw_profile = profile
        document.channel_layout = profile.channel_layout
        document.bit_depth = profile.bit_depth
        self.window._raw_profile_prompt_suppressed.discard(document_id)
        self.window._update_document_item(document)


def install_comparison_set(window: Any) -> ComparisonSetController:
    existing = getattr(window, "comparison_set_controller", None)
    if isinstance(existing, ComparisonSetController):
        return existing
    controller = ComparisonSetController(window)
    window.comparison_set_controller = controller
    return controller
