"""Compact official bipolar bars backed by an adapter-verified shared range.

No per-row endpoint labels, decorative ticks, or map-derived official scores.
The parent Inspector supplies one legend and the selected range control.
"""

from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from pixelscope_enterprise.iqa.analysis_model import AttributeDisplay, official_chart_fraction

ATTRIBUTE_ROLE = int(Qt.ItemDataRole.UserRole) + 1
DISPLAY_RANGE_ROLE = int(Qt.ItemDataRole.UserRole) + 2

_A_COLOR = QColor(222, 88, 79)
_B_COLOR = QColor(69, 139, 212)
_POS_COLOR = QColor(177, 90, 191)
_NEG_COLOR = QColor(43, 155, 155)


class _OptionFields(Protocol):
    """Qt6 fields omitted from some supported PySide6 6.4 type stubs."""

    state: QStyle.StateFlag
    palette: QPalette
    rect: QRect


class RelativeDifferenceDelegate(QStyledItemDelegate):
    """Draw a value and one centered bar with the current display span."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        attr = index.data(ATTRIBUTE_ROLE)
        if not isinstance(attr, AttributeDisplay):
            super().paint(painter, option, index)
            return
        fields = cast(_OptionFields, option)
        selected = bool(fields.state & QStyle.StateFlag.State_Selected)
        palette = fields.palette
        text_color = palette.highlightedText().color() if selected else palette.text().color()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(fields.rect, palette.highlight() if selected else palette.base())
        content = fields.rect.adjusted(6, 1, -7, -1)
        painter.setPen(text_color)
        if attr.official_value is None:
            painter.drawText(
                content, Qt.AlignmentFlag.AlignVCenter, f"{attr.official_availability.upper()} · —"
            )
            painter.restore()
            return

        supplied = index.data(DISPLAY_RANGE_ROLE)
        display_range = (
            float(supplied)
            if isinstance(supplied, int | float)
            else attr.chart_axis_range
        )
        fraction = official_chart_fraction(attr, display_range)
        value_text = f"{attr.official_value:+.3f} {attr.unit}"
        if fraction is None:
            painter.drawText(
                content, Qt.AlignmentFlag.AlignVCenter, value_text + " · unscaled"
            )
            painter.restore()
            return

        assert display_range is not None
        clipped = abs(attr.official_value) > display_range
        painter.drawText(
            QRect(content.left(), content.top(), content.width(), 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            value_text + ("  ↗ clipped" if clipped else ""),
        )
        x = content.left() + 4
        width = max(16, content.width() - 8)
        middle = x + width // 2
        y = content.top() + 20
        painter.fillRect(QRect(x, y, width, 7), palette.midlight())
        painter.fillRect(QRect(middle, y - 3, 1, 13), text_color)
        extent = round(abs(fraction) * width / 2)
        if extent:
            if fraction > 0:
                color = _A_COLOR if attr.quality_oriented else _POS_COLOR
                painter.fillRect(QRect(middle + 1, y, extent, 7), color)
            else:
                color = _B_COLOR if attr.quality_oriented else _NEG_COLOR
                painter.fillRect(QRect(middle - extent, y, extent, 7), color)
        painter.restore()
