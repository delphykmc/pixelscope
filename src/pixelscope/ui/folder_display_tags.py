from __future__ import annotations

import json
import weakref
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog

from pixelscope.core.source_presentation import (
    SourceLabelInput,
    normalized_label_key,
    resolve_display_aliases,
)
from pixelscope.ui.lifecycle_hooks import OwnerCallback


class FolderDisplayTagController:
    """Attach persistent display-only labels to registered source folders."""

    SETTINGS_KEY = "ui/folderDisplayTags"
    MAX_TAG_LENGTH = 64

    def __init__(self, window: Any) -> None:
        self._window_ref = weakref.ref(window)
        self._tree_ref = weakref.ref(window.document_list)
        self._tags = self._load_tags()
        self._original_update_document_item = OwnerCallback(window._update_document_item)
        self._original_register_input = OwnerCallback(window._register_input)
        self._original_add_document = OwnerCallback(window.add_document)
        self._original_remove_documents = OwnerCallback(window._remove_document_ids)
        self._source_groups: dict[str, set[str]] = {}
        self._group_by_source: dict[str, str] = {}
        self._pending_alias_groups: set[str] = set()
        self._bulk_registration_depth = 0
        self._pending_folder_rows: dict[str, Path] = {}
        self._install_document_hooks()
        self._install_context_menu_hook()
        self._install_tile_tag_actions()
        # The files-tree signal was connected to the original MainWindow slot
        # before this controller was installed; observe completed removals too.
        window.document_list.remove_requested.connect(self._removed_from_tree)
        self._refresh_existing_documents()

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None:
            raise RuntimeError("Folder display-tag window was destroyed")
        return window

    @property
    def tree(self) -> Any:
        tree = self._tree_ref()
        if tree is None:
            raise RuntimeError("Folder display-tag tree was destroyed")
        return tree

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
        """Set the inexpensive initial label before catalog registration."""
        path = getattr(document, "source_path", None)
        if not isinstance(path, Path):
            return
        key = folder_key or self._registration_folder_key(path)
        tag = self.tag_for_folder(path.parent, folder_key=key)
        document.display_name = f"[{tag}] {path.name}" if tag else path.name

    def _remember_source(self, document: Any) -> str | None:
        path = getattr(document, "source_path", None)
        if not isinstance(path, Path):
            return None
        source_id = document.document_id
        group = normalized_label_key(path.name)
        previous = self._group_by_source.get(source_id)
        if previous is not None and previous != group:
            self._source_groups.get(previous, set()).discard(source_id)
        self._group_by_source[source_id] = group
        self._source_groups.setdefault(group, set()).add(source_id)
        return group

    def _refresh_alias_groups(self, groups: set[str]) -> set[str]:
        """Only change presentation; no document registration or worker requests."""
        if self._bulk_registration_depth:
            self._pending_alias_groups.update(groups)
            return set()
        changed: set[str] = set()
        for group in groups:
            documents = [
                self.window.documents[source_id]
                for source_id in sorted(self._source_groups.get(group, ()))
                if source_id in self.window.documents
            ]
            inputs = [
                SourceLabelInput(
                    source_key=document.document_id,
                    source_path=document.source_path,
                    fallback_name=document.display_name,
                    display_tag=self.tag_for_folder(document.source_path.parent),
                )
                for document in documents
                if isinstance(document.source_path, Path)
            ]
            labels = resolve_display_aliases(inputs)
            for document in documents:
                label = labels.get(document.document_id)
                if label is not None and document.display_name != label.text:
                    document.display_name = label.text
                    self._original_update_document_item(document)
                    changed.add(document.document_id)
        return changed

    def _forget_removed_sources(self) -> set[str]:
        removed = set(self._group_by_source).difference(self.window.documents)
        changed_groups: set[str] = set()
        for source_id in removed:
            group = self._group_by_source.pop(source_id)
            self._source_groups[group].discard(source_id)
            if not self._source_groups[group]:
                del self._source_groups[group]
            changed_groups.add(group)
        return changed_groups

    def _removed_from_tree(self, _selected_ids: object) -> None:
        changed = self._refresh_alias_groups(self._forget_removed_sources())
        if changed:
            self._refresh_presentation()

    def _install_tile_tag_actions(self) -> None:
        viewers = (self.window.viewer, *self.window.multi_compare_view.viewers)
        for viewer in viewers:
            viewer.header.edit_tag_requested.connect(self._prompt_for_tag)

    def _refresh_presentation(self) -> None:
        """Refresh labels only; never re-enter selection/load/Calculate paths."""
        window = self.window
        difference = window._difference_document
        if difference is not None and window._difference_source_ids is not None:
            pair = window.difference_panel.selected_documents()
            if pair is not None and {doc.document_id for doc in pair} == set(
                window._difference_source_ids
            ):
                difference.display_name = window.difference_panel._title()

        # Channel split documents are transient derived presentations, not
        # registered sources. Update their origin annotation in place without
        # regenerating arrays or changing derived document identities.
        def refresh_derived(document: Any) -> None:
            source_id, marker, channel = document.document_id.partition(":split:")
            if not marker:
                return
            origin = window.documents.get(source_id)
            if origin is not None:
                document.display_name = f"{origin.display_name} · {channel}"

        for derived in window._channel_view_cache.values():
            for document in derived:
                refresh_derived(document)
        viewers = (window.viewer, *window.multi_compare_view.viewers)
        for viewer in viewers:
            document = viewer.presented_document
            if document is None:
                continue
            refresh_derived(document)
            viewer.set_header(viewer.header.text())

        if window.viewer.presented_document is not None:
            displayed_id = window.viewer.presented_document.document_id
            window._set_single_navigation(
                "difference" if window.viewer.presented_document is difference else displayed_id
            )

        analysis = window.comparison_analysis_panel
        if analysis.last_results and analysis._histogram_specs:
            analysis._render(analysis.last_results, analysis._histogram_specs)
        line = window.line_profile_panel
        if line.last_results:
            line._render(line.last_results)

        # Never call DifferencePanel.set_documents(): it owns a generation-keyed
        # cache, worker state and the explicit Calculate contract.
        for selector in (window.difference_panel.a_selector, window.difference_panel.b_selector):
            previously_blocked = selector.blockSignals(True)
            try:
                for index in range(selector.count()):
                    document = window.documents.get(selector.itemData(index))
                    if document is not None:
                        selector.setItemText(index, document.display_name)
            finally:
                selector.blockSignals(previously_blocked)

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
                changed = self._refresh_alias_groups(set(self._pending_alias_groups))
                self._pending_alias_groups.clear()
                for folder_key, folder in pending:
                    self._refresh_folder_row(folder, folder_key=folder_key)
                if changed.intersection(self.window._selection_order):
                    self._refresh_presentation()

    def _queue_folder_row_refresh(self, folder: Path, folder_key: str | None) -> None:
        key = folder_key or self._folder_key(folder)
        if self._bulk_registration_depth:
            self._pending_folder_rows[key] = folder
            return
        self._refresh_folder_row(folder, folder_key=key)

    def _install_document_hooks(self) -> None:
        def update_document_item(document: Any, *, folder_key: str | None = None) -> None:
            self._apply_document_tag(document, folder_key=folder_key)
            group = self._remember_source(document)
            if group is not None:
                self._refresh_alias_groups({group})
            self._original_update_document_item(document)

        def register_input(*args: Any, **kwargs: Any) -> str | None:
            document_id = cast(str | None, self._original_register_input(*args, **kwargs))
            if document_id is not None:
                document = self.window.documents.get(document_id)
                if document is not None:
                    path = getattr(document, "source_path", None)
                    folder = path.parent if isinstance(path, Path) else None
                    folder_key = (
                        self._registration_folder_key(path) if isinstance(path, Path) else None
                    )
                    update_document_item(document, folder_key=folder_key)
                    if folder is not None:
                        self._queue_folder_row_refresh(folder, folder_key)
            return document_id

        def add_document(document: Any, *args: Any, **kwargs: Any) -> None:
            self._apply_document_tag(document)
            self._original_add_document(document, *args, **kwargs)
            group = self._remember_source(document)
            if group is not None:
                changed = self._refresh_alias_groups({group})
                if changed.intersection(self.window._selection_order):
                    self._refresh_presentation()
            path = getattr(document, "source_path", None)
            self._refresh_folder_row(path.parent if isinstance(path, Path) else None)

        def remove_documents(selected_ids: object) -> None:
            self._original_remove_documents(selected_ids)
            self._removed_from_tree(selected_ids)

        self.window._update_document_item = update_document_item
        self.window._register_input = register_input
        self.window.add_document = add_document
        self.window._remove_document_ids = remove_documents

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
            self._remember_source(document)
        self._refresh_alias_groups(set(self._source_groups))
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            raw_path = str(item.data(0, self.tree.PATH_ROLE) or "")
            if raw_path:
                self._refresh_folder_row(Path(raw_path))

    def _refresh_folder(self, folder: Path) -> None:
        key = self._folder_key(folder)
        groups: set[str] = set()
        for document in self.window.documents.values():
            path = getattr(document, "source_path", None)
            if isinstance(path, Path) and self._folder_key(path.parent) == key:
                group = self._remember_source(document)
                if group is not None:
                    groups.add(group)
        self._refresh_alias_groups(groups)
        self._refresh_folder_row(folder, folder_key=key)
        self._refresh_presentation()

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
