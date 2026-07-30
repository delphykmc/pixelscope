from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QTreeWidget,
    QTreeWidgetItem,
)

from pixelscope.io.path_discovery import natural_sort_key


class DocumentListWidget(QTreeWidget):
    """Folder-grouped, multi-select file tree with local path drop support."""

    paths_dropped = Signal(object)
    previous_pair_requested = Signal()
    next_pair_requested = Signal()
    PATH_ROLE = Qt.ItemDataRole.UserRole + 1
    BASE_TEXT_ROLE = Qt.ItemDataRole.UserRole + 2

    def __init__(self) -> None:
        super().__init__()
        self._groups: dict[str, QTreeWidgetItem] = {}
        self._document_items: dict[str, QTreeWidgetItem] = {}
        self.setHeaderHidden(True)
        self.setIndentation(18)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

    @property
    def document_count(self) -> int:
        return len(self._document_items)

    def add_document_item(
        self,
        document_id: str,
        text: str,
        source_path: Path | None,
        tooltip: str = "",
    ) -> QTreeWidgetItem:
        folder = source_path.parent.resolve() if source_path is not None else None
        group_key = str(folder).casefold() if folder is not None else "<generated>"
        group = self._groups.get(group_key)
        if group is None:
            group_name = folder.name if folder is not None else "Generated"
            group = QTreeWidgetItem([group_name])
            group.setToolTip(0, str(folder or "Generated documents"))
            group.setData(0, self.PATH_ROLE, str(folder) if folder is not None else "")
            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = group.font(0)
            font.setBold(True)
            group.setFont(0, font)
            self.addTopLevelItem(group)
            group.setExpanded(True)
            self._groups[group_key] = group

        item = QTreeWidgetItem([text])
        item.setData(0, Qt.ItemDataRole.UserRole, document_id)
        item.setData(0, self.PATH_ROLE, str(source_path or ""))
        item.setData(0, self.BASE_TEXT_ROLE, text)
        item.setToolTip(0, tooltip)
        insert_at = group.childCount()
        if source_path is not None:
            new_key = natural_sort_key(source_path)
            for index in range(group.childCount()):
                existing_path = Path(str(group.child(index).data(0, self.PATH_ROLE)))
                if new_key < natural_sort_key(existing_path):
                    insert_at = index
                    break
        group.insertChild(insert_at, item)
        self._document_items[document_id] = item
        self._refresh_group_indices(group)
        return item

    def update_document_item(self, document_id: str, text: str, tooltip: str) -> None:
        item = self._document_items.get(document_id)
        if item is None:
            return
        item.setData(0, self.BASE_TEXT_ROLE, text)
        item.setToolTip(0, tooltip)
        group = item.parent()
        if group is not None:
            self._refresh_group_indices(group)

    def document_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []
        for group_index in range(self.topLevelItemCount()):
            group = self.topLevelItem(group_index)
            items.extend(group.child(index) for index in range(group.childCount()))
        return items

    def selected_document_items(self) -> list[QTreeWidgetItem]:
        return [
            item
            for item in self.selectedItems()
            if item.data(0, Qt.ItemDataRole.UserRole) is not None
        ]

    def document_item(self, document_id: str) -> QTreeWidgetItem | None:
        return self._document_items.get(document_id)

    def remove_document_item(self, document_id: str) -> None:
        item = self._document_items.pop(document_id, None)
        if item is None:
            return
        group = item.parent()
        if group is None:
            return
        group.removeChild(item)
        if group.childCount() == 0:
            group_key = next(
                (key for key, candidate in self._groups.items() if candidate is group),
                None,
            )
            index = self.indexOfTopLevelItem(group)
            self.takeTopLevelItem(index)
            if group_key is not None:
                self._groups.pop(group_key, None)
        else:
            self._refresh_group_indices(group)

    def _refresh_group_indices(self, group: QTreeWidgetItem) -> None:
        count = group.childCount()
        for index in range(count):
            child = group.child(index)
            base_text = str(child.data(0, self.BASE_TEXT_ROLE) or child.text(0))
            child.setText(0, f"[{index + 1}/{count}] {base_text}")

    @staticmethod
    def _local_paths(
        event: QDragEnterEvent | QDragMoveEvent | QDropEvent,
    ) -> list[Path]:
        return [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._local_paths(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._local_paths(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        paths = self._local_paths(event)
        if paths:
            event.acceptProposedAction()
            self.paths_dropped.emit(paths)
            return
        super().dropEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.NoModifier:
            if event.key() == Qt.Key.Key_PageUp:
                event.accept()
                self.previous_pair_requested.emit()
                return
            if event.key() == Qt.Key.Key_PageDown:
                event.accept()
                self.next_pair_requested.emit()
                return
        super().keyPressEvent(event)
