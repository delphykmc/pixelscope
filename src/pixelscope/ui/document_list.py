from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import (
    QItemSelection,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QRect,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QIcon,
    QKeyEvent,
    QPainter,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
)

from pixelscope.io.path_discovery import natural_sort_key
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.file_status_icons import document_residency_state, file_status_icon


class _DocumentItemDelegate(QStyledItemDelegate):
    """Draw a stable active-document accent without replacing selection styling."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        super().paint(painter, option, index)
        if index.column() != 0 or not bool(index.data(DocumentListWidget.ACTIVE_ROLE)):
            return
        # PySide6 6.4 stubs omit QStyleOptionViewItem.rect.
        rect = getattr(option, "rect")  # noqa: B009
        accent = QRect(
            rect.left(),
            rect.top() + 2,
            3,
            max(0, rect.height() - 4),
        )
        painter.fillRect(accent, QColor(TOKENS.accent))


class DocumentListWidget(QTreeWidget):
    """Folder-grouped, multi-select file tree with local path drop support."""

    paths_dropped = Signal(object)
    previous_position_requested = Signal()
    next_position_requested = Signal()
    activate_requested = Signal(str)
    selection_changing = Signal()
    remove_changing = Signal(object)
    remove_requested = Signal(object)
    compare_requested = Signal()
    focus_requested = Signal(str)
    PATH_ROLE = Qt.ItemDataRole.UserRole + 1
    BASE_TEXT_ROLE = Qt.ItemDataRole.UserRole + 2
    FILE_TYPE_ROLE = Qt.ItemDataRole.UserRole + 3
    ACTIVE_ROLE = Qt.ItemDataRole.UserRole + 4
    DETAIL_ROLE = Qt.ItemDataRole.UserRole + 5

    def __init__(self) -> None:
        super().__init__()
        self._groups: dict[str, QTreeWidgetItem] = {}
        self._group_sort_keys: dict[str, list[tuple[object, ...]]] = {}
        self._document_items: dict[str, QTreeWidgetItem] = {}
        self._bulk_update_depth = 0
        self._bulk_update_dirty = False
        self._registration_metadata: tuple[
            Path,
            Path,
            str,
            tuple[object, ...],
        ] | None = None
        self.setColumnCount(2)
        self.setHeaderLabels(["File", "Type"])
        self.setHeaderHidden(False)
        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.setIndentation(18)
        self.setRootIsDecorated(True)
        self.setItemsExpandable(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setUniformRowHeights(True)
        self.setItemDelegate(_DocumentItemDelegate(self))
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

    @contextmanager
    def bulk_update(self) -> Iterator[None]:
        """Suppress intermediate paints while a bounded registration chunk mutates rows."""

        outermost = self._bulk_update_depth == 0
        if outermost:
            self.setUpdatesEnabled(False)
        self._bulk_update_depth += 1
        try:
            yield
        finally:
            self._bulk_update_depth -= 1
            if outermost:
                self.setUpdatesEnabled(True)
                if self._bulk_update_dirty:
                    self.viewport().update()
                self._bulk_update_dirty = False

    @contextmanager
    def registration_metadata(
        self,
        *,
        source_path: Path,
        folder_path: Path,
        folder_key: str,
        sort_key: tuple[object, ...],
    ) -> Iterator[None]:
        """Reuse worker-computed path metadata for one async registration mutation."""

        previous = self._registration_metadata
        self._registration_metadata = (source_path, folder_path, folder_key, sort_key)
        try:
            yield
        finally:
            self._registration_metadata = previous

    def add_document_item(
        self,
        document_id: str,
        text: str,
        source_path: Path | None,
        tooltip: str = "",
        *,
        loading_state: str = "pending",
        resident: bool = False,
    ) -> QTreeWidgetItem:
        trusted = self._registration_metadata
        if source_path is not None and trusted is not None and trusted[0] == source_path:
            folder = trusted[1]
            group_key = trusted[2]
            new_key: tuple[object, ...] | None = trusted[3]
        else:
            folder = source_path.parent.resolve() if source_path is not None else None
            group_key = str(folder).casefold() if folder is not None else "<generated>"
            new_key = natural_sort_key(source_path) if source_path is not None else None

        group = self._groups.get(group_key)
        if group is None:
            group_name = folder.name if folder is not None else "Generated"
            group = QTreeWidgetItem([group_name, "Folder"])
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
            self._group_sort_keys[group_key] = []

        file_type = source_path.suffix.upper().lstrip(".") if source_path is not None else "GEN"
        item = QTreeWidgetItem([text, file_type])
        item.setData(0, Qt.ItemDataRole.UserRole, document_id)
        item.setData(0, self.PATH_ROLE, str(source_path or ""))
        item.setData(0, self.BASE_TEXT_ROLE, text)
        item.setData(0, self.FILE_TYPE_ROLE, file_type)
        item.setData(0, self.ACTIVE_ROLE, False)
        item.setData(0, self.DETAIL_ROLE, tooltip)
        insert_at = group.childCount()
        if new_key is not None:
            group_keys = self._group_sort_keys.setdefault(group_key, [])
            insert_at = bisect_right(group_keys, new_key)
            group_keys.insert(insert_at, new_key)
        group.insertChild(insert_at, item)
        self._document_items[document_id] = item
        self.set_document_state(
            document_id,
            loading_state=loading_state,
            resident=resident,
        )
        return item

    def update_document_item(self, document_id: str, text: str, tooltip: str) -> None:
        item = self._document_items.get(document_id)
        if item is None:
            return
        item.setData(0, self.BASE_TEXT_ROLE, text)
        item.setData(0, self.DETAIL_ROLE, tooltip)
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
        group_path = str(group.data(0, self.PATH_ROLE) or "")
        group_key = group_path.casefold() if group_path else "<generated>"
        child_index = group.indexOfChild(item)
        group.removeChild(item)
        group_keys = self._group_sort_keys.get(group_key)
        if group_keys is not None and 0 <= child_index < len(group_keys):
            group_keys.pop(child_index)
        if group.childCount() == 0:
            index = self.indexOfTopLevelItem(group)
            self.takeTopLevelItem(index)
            self._groups.pop(group_key, None)
            self._group_sort_keys.pop(group_key, None)

    def set_document_state(
        self,
        document_id: str,
        *,
        visible: bool = False,
        active: bool = False,
        role: str = "",
        slot: int | None = None,
        loading_state: str = "ready",
        resident: bool = False,
    ) -> None:
        item = self._document_items.get(document_id)
        if item is None:
            return
        del role, slot
        file_type = str(item.data(0, self.FILE_TYPE_ROLE) or item.text(1))
        residency_state = document_residency_state(loading_state, resident)
        item.setIcon(0, self._document_icon(file_type, residency_state))
        item.setData(0, self.ACTIVE_ROLE, active)
        font = item.font(0)
        font.setBold(active)
        item.setFont(0, font)
        item.setForeground(0, QColor(TOKENS.text_primary))

        base_tooltip = str(item.data(0, self.PATH_ROLE) or item.text(0))
        detail = str(item.data(0, self.DETAIL_ROLE) or "")
        lines = [base_tooltip, self._residency_text(residency_state)]
        if detail and detail != base_tooltip:
            lines.append(detail)
        if active:
            lines.append("Active in workspace")
        elif visible:
            lines.append("Visible in workspace")
        item.setToolTip(0, "\n".join(lines))
        if self._bulk_update_depth:
            self._bulk_update_dirty = True
        else:
            self.viewport().update(self.visualItemRect(item))

    @staticmethod
    def _document_icon(file_type: str, residency_state: str) -> QIcon:
        return file_status_icon(file_type, residency_state)

    @staticmethod
    def _residency_text(residency_state: str) -> str:
        if residency_state == "cached":
            return "Cached in memory"
        if residency_state == "loading":
            return "Loading into memory"
        if residency_state == "error":
            return "Load failed"
        return "Not cached"

    @staticmethod
    def _local_paths(
        event: QDragEnterEvent | QDragMoveEvent | QDropEvent,
    ) -> list[Path]:
        return [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]

    def selectionChanged(  # noqa: N802
        self,
        selected: QItemSelection,
        deselected: QItemSelection,
    ) -> None:
        """Expose a safe pre-mutation boundary before Qt emits itemSelectionChanged."""

        self.selection_changing.emit()
        super().selectionChanged(selected, deselected)

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
                self.previous_position_requested.emit()
                return
            if event.key() == Qt.Key.Key_PageDown:
                event.accept()
                self.next_position_requested.emit()
                return
        super().keyPressEvent(event)

    def _activate_item(self, item: QTreeWidgetItem, _column: int) -> None:
        document_id = item.data(0, Qt.ItemDataRole.UserRole)
        if document_id is not None:
            self.activate_requested.emit(str(document_id))

    def _emit_remove_request(self, document_ids: list[str]) -> None:
        """Emit pre/post remove signals without rewriting existing MainWindow ownership."""

        self.remove_changing.emit(document_ids)
        self.remove_requested.emit(document_ids)

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
            self._emit_remove_request(
                [
                    str(candidate.data(0, Qt.ItemDataRole.UserRole))
                    for candidate in self.selected_document_items()
                ]
            )