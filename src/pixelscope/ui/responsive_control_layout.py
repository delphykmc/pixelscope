from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QLabel, QLayout, QLayoutItem, QSizePolicy, QWidget


class ElidingContextLabel(QLabel):
    """Paint bounded context while retaining its complete logical text."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:
        super().setText(text)
        self.setToolTip(text)
        self.setAccessibleName(text)
        self.setAccessibleDescription(text)

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def _paint_text(self) -> str:
        return self.fontMetrics().elidedText(
            self.text(),
            Qt.TextElideMode.ElideLeft,
            max(0, self.contentsRect().width()),
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        self.style().drawItemText(
            painter,
            self.contentsRect(),
            self.alignment(),
            self.palette(),
            self.isEnabled(),
            self._paint_text(),
            QPalette.ColorRole.WindowText,
        )


class ResponsiveControlLayout(QLayout):
    """Lay controls out in one row when they fit, otherwise use compact rows."""

    def __init__(self, parent: QWidget | None = None, *, spacing: int = 0) -> None:
        super().__init__(parent)
        self.setSpacing(spacing)
        self._items: list[tuple[QLayoutItem, int]] = []
        self._next_compact_row = 0
        self._context_item: QLayoutItem | None = None

    def add_control(self, widget: QWidget, *, compact_row: int) -> None:
        self._next_compact_row = compact_row
        self.addWidget(widget)

    def add_context(self, widget: QWidget, *, compact_row: int) -> None:
        """Add the one context value, right-aligned in wide and compact rows."""

        if self._context_item is not None:
            raise ValueError("ResponsiveControlLayout accepts only one context item")
        self._next_compact_row = compact_row
        self.addWidget(widget)
        self._context_item = self._items[-1][0]

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append((item, self._next_compact_row))

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # type: ignore[override]
        if 0 <= index < len(self._items):
            return self._items[index][0]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # type: ignore[override]
        if 0 <= index < len(self._items):
            item = self._items.pop(index)[0]
            if item is self._context_item:
                self._context_item = None
            return item
        return None

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        margins = self.contentsMargins()
        available = max(0, width - margins.left() - margins.right())
        rows = self._rows_for_width(available)
        return (
            margins.top()
            + margins.bottom()
            + sum(self._row_height(row) for row in rows)
            + (max(0, len(rows) - 1) * self.spacing())
        )

    def sizeHint(self) -> QSize:
        return self._compact_size(minimum=False)

    def minimumSize(self) -> QSize:
        return self._compact_size(minimum=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        margins = self.contentsMargins()
        area = rect.adjusted(
            margins.left(),
            margins.top(),
            -margins.right(),
            -margins.bottom(),
        )
        rows = self._rows_for_width(area.width())
        y = area.y()
        for row in rows:
            row_height = self._row_height(row)
            self._set_row_geometry(row, QRect(area.x(), y, area.width(), row_height))
            y += row_height + self.spacing()

    def _visible_items(self) -> list[tuple[QLayoutItem, int]]:
        return [(item, row) for item, row in self._items if not item.isEmpty()]

    def _rows_for_width(self, width: int) -> list[list[QLayoutItem]]:
        visible = self._visible_items()
        if not visible:
            return []
        wide_row = [item for item, _row in visible]
        if width >= self._wide_row_width(wide_row):
            return [wide_row]
        row_numbers = sorted({row for _item, row in visible})
        return [[item for item, item_row in visible if item_row == row] for row in row_numbers]

    def _compact_size(self, *, minimum: bool) -> QSize:
        visible = self._visible_items()
        if not visible:
            return QSize()
        row_numbers = sorted({row for _item, row in visible})
        rows = [[item for item, item_row in visible if item_row == row] for row in row_numbers]
        margins = self.contentsMargins()
        width = max(self._row_width(row, minimum=minimum) for row in rows)
        height = sum(self._row_height(row) for row in rows)
        height += max(0, len(rows) - 1) * self.spacing()
        return QSize(
            width + margins.left() + margins.right(),
            height + margins.top() + margins.bottom(),
        )

    def _row_width(self, row: list[QLayoutItem], *, minimum: bool) -> int:
        widths = [
            item.minimumSize().width() if minimum else self._preferred_width(item) for item in row
        ]
        return sum(widths) + max(0, len(row) - 1) * self.spacing()

    def _wide_row_width(self, row: list[QLayoutItem]) -> int:
        """Keep context elastic so its full text does not trigger compact reflow."""

        widths = [
            item.minimumSize().width()
            if item is self._context_item
            else self._preferred_width(item)
            for item in row
        ]
        return sum(widths) + max(0, len(row) - 1) * self.spacing()

    @staticmethod
    def _row_height(row: list[QLayoutItem]) -> int:
        return max(
            (
                item.widget().sizeHint().height()
                if item.widget() is not None
                else item.sizeHint().height()
                for item in row
            ),
            default=0,
        )

    @staticmethod
    def _preferred_width(item: QLayoutItem) -> int:
        widget = item.widget()
        if widget is None:
            return item.sizeHint().width()
        return min(widget.sizeHint().width(), widget.maximumWidth())

    def _set_row_geometry(self, row: list[QLayoutItem], rect: QRect) -> None:
        spacing = self.spacing()
        desired = [self._preferred_width(item) for item in row]
        total = sum(desired) + max(0, len(row) - 1) * spacing
        context_index = next(
            (index for index, item in enumerate(row) if item is self._context_item),
            None,
        )
        flexible = [
            index
            for index, item in enumerate(row)
            if item.widget() is not None
            and item.widget().sizePolicy().horizontalPolicy()
            in (QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        ]
        overflow = max(0, total - rect.width())
        if overflow > 0 and context_index is not None:
            context_minimum = row[context_index].minimumSize().width()
            applied = min(
                overflow,
                max(0, desired[context_index] - context_minimum),
            )
            desired[context_index] -= applied
            overflow -= applied
            if context_index in flexible:
                flexible.remove(context_index)
        while overflow > 0 and flexible:
            reduction = max(1, (overflow + len(flexible) - 1) // len(flexible))
            next_flexible: list[int] = []
            for index in flexible:
                minimum = row[index].minimumSize().width()
                applied = min(reduction, max(0, desired[index] - minimum))
                desired[index] -= applied
                overflow -= applied
                if desired[index] > minimum:
                    next_flexible.append(index)
            if next_flexible == flexible and not any(
                desired[index] > row[index].minimumSize().width() for index in flexible
            ):
                break
            flexible = next_flexible
        context_x = None
        if context_index is not None:
            context_x = rect.right() - desired[context_index] + 1
        x = rect.x()
        for index, (item, width) in enumerate(zip(row, desired, strict=True)):
            if index == context_index and context_x is not None:
                x = max(x, context_x)
            item.setGeometry(QRect(x, rect.y(), width, rect.height()))
            x += width + spacing
