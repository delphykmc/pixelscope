from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog


class FolderDisplayTagController:
    """Attach persistent display-only labels to registered source folders."""

    SETTINGS_KEY = "ui/folderDisplayTags"
    MAX_TAG_LENGTH = 64

    def __init__(self, window: Any) -> None:
        self.window = window
        self.tree = window.document_list
        self._tags = self._load_tags()
        self._original_update_document_item = window._update_document_item
        self._original_register_input = window._register_input
        self._original_add_document = window.add_document
        self._bulk_registration_depth = 0
        self._pending_folder_rows: dict[str, Path] = {}
        self._install_document_hooks()
        self._install_context_menu_hook()
        self._refresh_existing_documents()

    @staticmethod
    def _folder_key(folder: Path) -> str:
        return str(folder.resolve()).casefold()

    def _load_tags(self) -> dict[str, str]:
        raw = self.window.settings.value(self.SETTINGS_KEY, "{}")
        try:
            parsed = json.loads(str(raw))
        except (TypeError, ValueError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in parsed.items()
            if isinstance(key, str) and isinstance(value, str) and value.strip()
        }

    def _save_tags(self) -> None:
        self.window.settings.setValue(
            self.SETTINGS_KEY,
            json.dumps(self._tags, ensure_ascii=False, sort_keys=True),
        )

    def tag_for_folder(self, folder: Path, *, folder_key: str | None = None) -> str:
        return self._tags.get(folder_key or self._folder_key(folder), "")

    def set_tag(self, folder: Path, tag: str) -> None:
        normalized = " ".join(str(tag).split())[: self.MAX_TAG_LENGTH]
        key = self._folder_key(folder)
        if normalized:
            self._tags[key] = normalized
        else:
            self._tags.pop(key, None)
        self._save_tags()
        self._refresh_folder(folder)
        self.window.statusBar().showMessage(
            f"Display tag {'set to ' + normalized if normalized else 'cleared'} · {folder.name}",
            3000,
        )

    def _registration_folder_key(self, source_path: Path) -> str | None:
        controller = getattr(self.window, "large_folder_registration_controller", None)
        record = getattr(controller, "current_record", None)
        if record is None or record.image_input.path != source_path:
            return None
        return cast(str | None, record.canonical_folder_key)

    def _apply_document_tag(self, document: Any, *, folder_key: str | None = None) -> None:
        source_path = getattr(document, "source_path", None)
        if not isinstance(source_path, Path):
            return
        key = folder_key or self._registration_folder_key(source_path)
        tag = self.tag_for_folder(source_path.parent, folder_key=key)
        document.display_name = f"[{tag}] {source_path.name}" if tag else source_path.name

    @contextmanager
    def bulk_registration(self) -> Iterator[None]:
        """Coalesce folder-row tag presentation across one GUI registration slice."""

        outermost = self._bulk_registration_depth == 0
        self._bulk_registration_depth += 1
        try:
            yield
        finally:
            self._bulk_registration_depth -= 1
            if outermost:
                pending = tuple(self._pending_folder_rows.items())
                self._pending_folder_rows.clear()
                for folder_key, folder in pending:
                    self._refresh_folder_row(folder, folder_key=folder_key)

    def _queue_folder_row_refresh(self, folder: Path, folder_key: str | None) -> None:
        key = folder_key or self._folder_key(folder)
        if self._bulk_registration_depth:
            self._pending_folder_rows[key] = folder
            return
        self._refresh_folder_row(folder, folder_key=key)

    def _install_document_hooks(self) -> None:
        def update_document_item(document: Any, *, folder_key: str | None = None) -> None:
            self._apply_document_tag(document, folder_key=folder_key)
            self._original_update_document_item(document)

        def register_input(*args: Any, **kwargs: Any) -> str | None:
            document_id = cast(str | None, self._original_register_input(*args, **kwargs))
            if document_id is not None:
                document = self.window.documents.get(document_id)
                if document is not None:
                    source_path = getattr(document, "source_path", None)
                    folder = source_path.parent if isinstance(source_path, Path) else None
                    folder_key = (
                        self._registration_folder_key(source_path)
                        if isinstance(source_path, Path)
                        else None
                    )
                    update_document_item(document, folder_key=folder_key)
                    if folder is not None:
                        self._queue_folder_row_refresh(folder, folder_key)
            return document_id

        def add_document(document: Any, *args: Any, **kwargs: Any) -> None:
            self._apply_document_tag(document)
            self._original_add_document(document, *args, **kwargs)
            source_path = getattr(document, "source_path", None)
            self._refresh_folder_row(source_path.parent if isinstance(source_path, Path) else None)

        self.window._update_document_item = update_document_item
        self.window._register_input = register_input
        self.window.add_document = add_document

    def _install_context_menu_hook(self) -> None:
        menu_controller = getattr(self.window, "workflow_files_context_menu", None)
        if menu_controller is None:
            return
        original_build_menu = menu_controller.build_menu_for_item

        def build_menu_for_item(item: Any | None) -> Any:
            menu = original_build_menu(item)
            if item is None or item.data(0, Qt.ItemDataRole.UserRole) is not None:
                return menu
            raw_path = str(item.data(0, self.tree.PATH_ROLE) or "")
            if not raw_path:
                return menu
            folder = Path(raw_path)
            menu.addSeparator()
            set_tag_action = menu.addAction("Set Display Tag...")
            set_tag_action.triggered.connect(
                lambda _checked=False, path=folder: self._prompt_for_tag(path)
            )
            if self.tag_for_folder(folder):
                clear_action = menu.addAction("Clear Display Tag")
                clear_action.triggered.connect(
                    lambda _checked=False, path=folder: self.set_tag(path, "")
                )
            return menu

        menu_controller.build_menu_for_item = build_menu_for_item

    def _prompt_for_tag(self, folder: Path) -> None:
        current = self.tag_for_folder(folder)
        text, accepted = QInputDialog.getText(
            self.tree,
            "Folder display tag",
            f"Display tag for {folder.name}",
            text=current,
        )
        if accepted:
            self.set_tag(folder, text)

    def _refresh_existing_documents(self) -> None:
        for document in self.window.documents.values():
            self._apply_document_tag(document)
            self._original_update_document_item(document)
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            raw_path = str(item.data(0, self.tree.PATH_ROLE) or "")
            if raw_path:
                self._refresh_folder_row(Path(raw_path))

    def _refresh_folder(self, folder: Path) -> None:
        key = self._folder_key(folder)
        for document in self.window.documents.values():
            source_path = getattr(document, "source_path", None)
            if isinstance(source_path, Path) and self._folder_key(source_path.parent) == key:
                self._apply_document_tag(document, folder_key=key)
                self._original_update_document_item(document)
        self._refresh_folder_row(folder, folder_key=key)
        self.window._render_selection(preserve_view=True)

        analysis = self.window.comparison_analysis_panel
        if analysis.last_results and analysis._histogram_specs:
            analysis._render(analysis.last_results, analysis._histogram_specs)
        line = self.window.line_profile_panel
        if line.last_results:
            line._render(line.last_results)

    def _refresh_folder_row(
        self,
        folder: Path | None,
        *,
        folder_key: str | None = None,
    ) -> None:
        if folder is None:
            return
        key = folder_key or self._folder_key(folder)
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            raw_path = str(item.data(0, self.tree.PATH_ROLE) or "")
            if not raw_path or raw_path.casefold() != key:
                continue
            tag = self._tags.get(key, "")
            item.setText(0, f"{folder.name} [{tag}]" if tag else folder.name)
            tooltip = str(folder)
            if tag:
                tooltip += f"\nDisplay tag: {tag}"
            item.setToolTip(0, tooltip)
            return


def install_folder_display_tags(window: Any) -> FolderDisplayTagController:
    existing = getattr(window, "folder_display_tag_controller", None)
    if isinstance(existing, FolderDisplayTagController):
        return existing
    controller = FolderDisplayTagController(window)
    window.folder_display_tag_controller = controller
    return controller