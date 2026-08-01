from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QDragEnterEvent, QDragMoveEvent, QDropEvent, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
)

from pixelscope.io.path_discovery import natural_sort_key
from pixelscope.ui.design_tokens import TOKENS


class DocumentListWidget(QTreeWidget):
    """Folder-grouped, multi-select file tree with local path drop support."""

    paths_dropped = Signal(object)
    previous_pair_requested = Signal()
    next_pair_requested = Signal()
    activate_requested = Signal(str)
    remove_requested = Signal(object)
    compare_requested = Signal()
    compare_role_requested = Signal(str, str)
    focus_requested = Signal(str)
    PATH_ROLE = Qt.ItemDataRole.UserRole + 1
    BASE_TEXT_ROLE = Qt.ItemDataRole.UserRole + 2

    def __init__(self) -> None:
        super().__init__()
        self._groups: dict[str, QTreeWidgetItem] = {}
        self._document_items: dict[str, QTreeWidgetItem] = {}
        self.setColumnCount(3)
        self.setHeaderLabels(["File", "State", "Type"])
        self.headerItem().setToolTip(1, "Visibility, loading, and comparison state")
        self.setHeaderHidden(False)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.setIndentation(18)
        self.setRootIsDecorated(True)
        self.setItemsExpandable(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(  # type: ignore[attr-defined]
            self._show_context_menu
        )
        self.itemDoubleClicked.connect(  # type: ignore[attr-defined]
            self._activate_item
        )

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
            group = QTreeWidgetItem([group_name, "", "Folder"])
            group.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            group.setToolTip(0, str(folder or "Generated documents"))
            group.setData(0, self.PATH_ROLE, str(folder) if folder is not None else "")
            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            font = group.font(0)
            font.setBold(True)
            group.setFont(0, font)
            self.addTopLevelItem(group)
            group.setExpanded(True)
            self._groups[group_key] = group

        file_type = source_path.suffix.upper().lstrip(".") if source_path is not None else "GEN"
        item = QTreeWidgetItem([text, "", file_type])
        icon_kind = (
            QStyle.StandardPixmap.SP_DriveHDIcon
            if file_type == "RAW"
            else QStyle.StandardPixmap.SP_FileIcon
        )
        item.setIcon(0, self.style().standardIcon(icon_kind))
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
        return item

    def update_document_item(self, document_id: str, text: str, tooltip: str) -> None:
        item = self._document_items.get(document_id)
        if item is None:
            return
        item.setData(0, self.BASE_TEXT_ROLE, text)
        item.setToolTip(0, tooltip)
        item.setText(0, text)

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

    def set_document_state(
        self,
        document_id: str,
        *,
        visible: bool = False,
        active: bool = False,
        role: str = "",
        slot: int | None = None,
        loading_state: str = "ready",
    ) -> None:
        item = self._document_items.get(document_id)
        if item is None:
            return
        del slot
        state = role
        if loading_state == "pending":
            state = "…"
        elif loading_state == "error":
            state = "!"
        item.setText(1, state)
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignCenter)
        font = item.font(0)
        font.setBold(active)
        item.setFont(0, font)
        item.setForeground(0, QColor(TOKENS.accent if active else TOKENS.text_primary))
        base_tooltip = str(item.data(0, self.PATH_ROLE) or item.text(0))
        visibility = "Visible in workspace" if visible else "Registered"
        item.setToolTip(0, f"{base_tooltip}\n{visibility}")

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

    def _activate_item(self, item: QTreeWidgetItem, _column: int) -> None:
        document_id = item.data(0, Qt.ItemDataRole.UserRole)
        if document_id is not None:
            self.activate_requested.emit(str(document_id))

    def _show_context_menu(self, position: QPoint) -> None:
        item = self.itemAt(position)
        if item is None or item.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        menu = QMenu(self)
        open_action = menu.addAction("Open in viewer")
        focus_action = menu.addAction("Set as focus")
        compare_action = menu.addAction("Show selected in multi-view")
        menu.addSeparator()
        remove_action = menu.addAction("Remove selected")
        selected = menu.exec(self.viewport().mapToGlobal(position))
        if selected is open_action:
            self.activate_requested.emit(str(item.data(0, Qt.ItemDataRole.UserRole)))
        elif selected is focus_action:
            self.focus_requested.emit(str(item.data(0, Qt.ItemDataRole.UserRole)))
        elif selected is compare_action:
            self.compare_requested.emit()
        elif selected is remove_action:
            self.remove_requested.emit(
                [
                    str(candidate.data(0, Qt.ItemDataRole.UserRole))
                    for candidate in self.selected_document_items()
                ]
            )
