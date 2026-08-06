from __future__ import annotations

from functools import cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

from pixelscope.ui.design_tokens import TOKENS

_ICON_KINDS = {
    "fit",
    "actual_size",
    "zoom_in",
    "zoom_out",
    "split_channels",
    "sync",
    "difference",
    "plots",
    "dock",
    "export",
    "pin",
    "flag",
}
_DISABLED_ICON_COLOR = "#737980"


def _line_pen(color: QColor, width: float = 1.5) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _draw_arrow_head(
    painter: QPainter,
    tip: QPointF,
    first: QPointF,
    second: QPointF,
) -> None:
    painter.drawLine(tip, first)
    painter.drawLine(tip, second)


def _draw_icon(kind: str, color_name: str, *, filled: bool = False) -> QPixmap:
    if kind not in _ICON_KINDS:
        raise ValueError(f"unsupported toolbar icon: {kind}")

    scale = 2
    logical_size = TOKENS.icon_size
    pixmap = QPixmap(logical_size * scale, logical_size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(scale)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = QColor(color_name)
    painter.setPen(_line_pen(color))
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if kind == "fit":
        painter.drawLine(QPointF(2.5, 6.0), QPointF(2.5, 2.5))
        painter.drawLine(QPointF(2.5, 2.5), QPointF(6.0, 2.5))
        painter.drawLine(QPointF(10.0, 2.5), QPointF(13.5, 2.5))
        painter.drawLine(QPointF(13.5, 2.5), QPointF(13.5, 6.0))
        painter.drawLine(QPointF(2.5, 10.0), QPointF(2.5, 13.5))
        painter.drawLine(QPointF(2.5, 13.5), QPointF(6.0, 13.5))
        painter.drawLine(QPointF(10.0, 13.5), QPointF(13.5, 13.5))
        painter.drawLine(QPointF(13.5, 13.5), QPointF(13.5, 10.0))
        painter.drawRect(QRectF(5.0, 5.0, 6.0, 6.0))
    elif kind == "actual_size":
        painter.drawRect(QRectF(2.0, 2.5, 12.0, 11.0))
        painter.drawLine(QPointF(4.0, 6.0), QPointF(5.0, 5.0))
        painter.drawLine(QPointF(5.0, 5.0), QPointF(5.0, 11.0))
        painter.drawPoint(QPointF(8.0, 7.0))
        painter.drawPoint(QPointF(8.0, 10.0))
        painter.drawLine(QPointF(10.0, 6.0), QPointF(11.0, 5.0))
        painter.drawLine(QPointF(11.0, 5.0), QPointF(11.0, 11.0))
    elif kind in {"zoom_in", "zoom_out"}:
        painter.drawEllipse(QRectF(2.0, 2.0, 8.5, 8.5))
        painter.drawLine(QPointF(9.0, 9.0), QPointF(13.5, 13.5))
        painter.drawLine(QPointF(4.0, 6.25), QPointF(8.5, 6.25))
        if kind == "zoom_in":
            painter.drawLine(QPointF(6.25, 4.0), QPointF(6.25, 8.5))
    elif kind == "split_channels":
        painter.drawRect(QRectF(2.0, 2.0, 12.0, 12.0))
        painter.drawLine(QPointF(8.0, 2.0), QPointF(8.0, 14.0))
        painter.drawLine(QPointF(2.0, 8.0), QPointF(14.0, 8.0))
        painter.drawPoint(QPointF(5.0, 5.0))
        painter.drawPoint(QPointF(11.0, 5.0))
        painter.drawPoint(QPointF(5.0, 11.0))
        painter.drawPoint(QPointF(11.0, 11.0))
    elif kind == "sync":
        arc = QRectF(2.25, 2.25, 11.5, 11.5)
        painter.drawArc(arc, 30 * 16, 130 * 16)
        painter.drawArc(arc, 210 * 16, 130 * 16)
        _draw_arrow_head(
            painter,
            QPointF(12.7, 5.2),
            QPointF(10.6, 4.7),
            QPointF(12.2, 7.2),
        )
        _draw_arrow_head(
            painter,
            QPointF(3.3, 10.8),
            QPointF(5.4, 11.3),
            QPointF(3.8, 8.8),
        )
    elif kind == "difference":
        painter.drawRect(QRectF(2.0, 2.0, 8.5, 8.5))
        painter.drawRect(QRectF(5.5, 5.5, 8.5, 8.5))
        painter.drawLine(QPointF(6.5, 12.5), QPointF(12.5, 6.5))
        painter.drawLine(QPointF(8.7, 13.5), QPointF(13.5, 8.7))
    elif kind == "plots":
        painter.drawLine(QPointF(2.5, 2.5), QPointF(2.5, 13.5))
        painter.drawLine(QPointF(2.5, 13.5), QPointF(13.5, 13.5))
        painter.drawPolyline(
            QPolygonF(
                (
                    QPointF(3.5, 11.0),
                    QPointF(6.0, 8.0),
                    QPointF(8.0, 9.5),
                    QPointF(10.5, 5.0),
                    QPointF(13.0, 6.5),
                )
            )
        )
    elif kind == "dock":
        painter.drawRect(QRectF(2.0, 2.0, 12.0, 12.0))
        painter.drawLine(QPointF(2.0, 10.0), QPointF(14.0, 10.0))
        painter.drawLine(QPointF(8.0, 3.5), QPointF(8.0, 8.0))
        _draw_arrow_head(
            painter,
            QPointF(8.0, 8.0),
            QPointF(5.8, 5.8),
            QPointF(10.2, 5.8),
        )
    elif kind == "export":
        painter.drawRect(QRectF(3.0, 2.0, 8.0, 7.0))
        painter.drawLine(QPointF(5.0, 4.0), QPointF(9.0, 4.0))
        painter.drawLine(QPointF(5.0, 6.0), QPointF(8.0, 6.0))
        painter.drawLine(QPointF(8.0, 7.5), QPointF(8.0, 13.0))
        _draw_arrow_head(
            painter,
            QPointF(8.0, 13.0),
            QPointF(5.8, 10.8),
            QPointF(10.2, 10.8),
        )
        painter.drawLine(QPointF(3.0, 14.0), QPointF(13.0, 14.0))
    elif kind == "pin":
        painter.drawLine(QPointF(4.0, 3.0), QPointF(12.0, 3.0))
        painter.drawLine(QPointF(5.0, 3.0), QPointF(6.0, 7.0))
        painter.drawLine(QPointF(11.0, 3.0), QPointF(10.0, 7.0))
        painter.drawLine(QPointF(4.5, 7.0), QPointF(11.5, 7.0))
        painter.drawLine(QPointF(8.0, 7.0), QPointF(8.0, 13.5))
        painter.drawLine(QPointF(8.0, 13.5), QPointF(7.0, 12.2))
    elif kind == "flag":
        painter.drawLine(QPointF(4.0, 2.0), QPointF(4.0, 14.0))
        flag = QPolygonF(
            (
                QPointF(4.0, 2.5),
                QPointF(12.5, 4.0),
                QPointF(10.5, 8.0),
                QPointF(4.0, 6.5),
            )
        )
        if filled:
            painter.setBrush(color)
        painter.drawPolygon(flag)

    painter.end()
    return pixmap


@cache
def toolbar_icon(kind: str) -> QIcon:
    """Return one high-DPI icon with explicit normal, checked, and disabled states."""

    if kind not in _ICON_KINDS:
        raise ValueError(f"unsupported toolbar icon: {kind}")
    icon = QIcon()
    normal = _draw_icon(kind, TOKENS.text_primary)
    active = _draw_icon(kind, TOKENS.accent)
    checked = _draw_icon(kind, TOKENS.accent, filled=kind == "flag")
    disabled = _draw_icon(kind, _DISABLED_ICON_COLOR)
    disabled_checked = _draw_icon(kind, _DISABLED_ICON_COLOR, filled=kind == "flag")
    icon.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(checked, QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(active, QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(checked, QIcon.Mode.Active, QIcon.State.On)
    icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.Off)
    icon.addPixmap(disabled_checked, QIcon.Mode.Disabled, QIcon.State.On)
    return icon
