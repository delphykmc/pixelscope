"""A lean Qt delegate for verified *official* A/B difference values.

Rows stay in supplier order. The chart axis is supplied independently of the
spatial-map color range. Neither a missing value nor unknown axis draws a
misleading zero-length comparison bar.
"""

from __future__ import annotations

from typing import Protocol, cast

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from pixelscope_enterprise.iqa.analysis_model import AttributeDisplay, official_chart_fraction

ATTRIBUTE_ROLE = int(Qt.ItemDataRole.UserRole) + 1

# Two distinct color families: quality-oriented A/B and unoriented signed-only.
_A_COLOR = QColor(222, 88, 79)
_B_COLOR = QColor(69, 139, 212)
_POS_COLOR = QColor(177, 90, 191)
_NEG_COLOR = QColor(43, 155, 155)


class _OptionFields(Protocol):
    """Actual Qt6 style fields omitted from some supported PySide6 stubs."""

    state: QStyle.StateFlag
    palette: QPalette
    rect: QRect


class RelativeDifferenceDelegate(QStyledItemDelegate):
    """Paint one small, keyboard-selectable bipolar bar in a table column."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        styled = cast(_OptionFields, option)
        attribute = index.data(ATTRIBUTE_ROLE)
        if not isinstance(attribute, AttributeDisplay):
            super().paint(painter, option, index)
            return
        selected = bool(styled.state & QStyle.StateFlag.State_Selected)
        text_color = (
            styled.palette.highlightedText().color() if selected else styled.palette.text().color()
        )
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(
            styled.rect, styled.palette.highlight() if selected else styled.palette.base()
        )
        box = styled.rect.adjusted(10, 3, -10, -3)
        fraction = official_chart_fraction(attribute)
        if attribute.official_value is None:
            painter.setPen(text_color)
            painter.drawText(
                box, Qt.AlignmentFlag.AlignVCenter, f"{attribute.official_availability.upper()} · —"
            )
            painter.restore()
            return
        if fraction is None:
            painter.setPen(text_color)
            painter.drawText(
                box,
                Qt.AlignmentFlag.AlignVCenter,
                f"{attribute.official_value:+.3f} {attribute.unit}\nAxis not supplied",
            )
            painter.restore()
            return

        axis = attribute.chart_axis_range
        assert axis is not None  # guaranteed by official_chart_fraction
        top = QRect(box.left(), box.top(), box.width(), 18)
        painter.setPen(text_color)
        suffix = " · clipped" if abs(attribute.official_value) > axis else ""
        painter.drawText(
            top,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{attribute.official_value:+.3f} {attribute.unit}{suffix}",
        )

        x = box.left() + 12
        width = max(16, box.width() - 24)
        middle = x + width // 2
        y = box.top() + 24
        painter.fillRect(QRect(x, y, width, 9), styled.palette.midlight())
        painter.fillRect(QRect(middle, y - 4, 1, 17), styled.palette.text())
        extent = round(abs(fraction) * width / 2)
        if extent:
            if fraction > 0:
                painter.fillRect(
                    QRect(middle + 1, y, extent, 9),
                    _A_COLOR if attribute.quality_oriented else _POS_COLOR,
                )
            else:
                painter.fillRect(
                    QRect(middle - extent, y, extent, 9),
                    _B_COLOR if attribute.quality_oriented else _NEG_COLOR,
                )
        bottom = QRect(box.left(), y + 12, box.width(), 18)
        painter.setPen(text_color)
        direction = "B better" if attribute.quality_oriented else "signed −"
        opposite = "A better" if attribute.quality_oriented else "signed +"
        painter.drawText(
            bottom, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, direction
        )
        painter.drawText(
            bottom,
            Qt.AlignmentFlag.AlignCenter,
            f"0  ·  ±{axis:g} {attribute.unit}",
        )
        painter.drawText(
            bottom, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, opposite
        )
        painter.restore()
