from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF

from pixelscope.ui.design_tokens import TOKENS

_ICON_SIZE = 18
_BASE_STROKE = QColor(TOKENS.text_secondary)
_BASE_FILL = QColor(TOKENS.panel_background)
_STATUS_BORDER = QColor(TOKENS.workspace_background)
_STATUS_REGISTERED = QColor(TOKENS.text_disabled)
_STATUS_LOADING = QColor(TOKENS.warning)
_STATUS_CACHED = QColor("#58b97a")
_STATUS_ERROR = QColor(TOKENS.error)
_STATUS_FOREGROUND = QColor("#ffffff")


def document_residency_state(loading_state: str, resident: bool) -> str:
    """Return the icon state for a document's actual memory residency."""

    if loading_state == "error":
        return "error"
    if loading_state == "loading":
        return "loading"
    if resident:
        return "cached"
    return "registered"


@lru_cache(maxsize=32)
def file_status_icon(file_type: str, state: str) -> QIcon:
    """Create a file-kind glyph with a small, unambiguous residency badge."""

    pixmap = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(_BASE_STROKE, 1.25))
    painter.setBrush(_BASE_FILL)

    normalized_type = file_type.upper()
    if normalized_type == "RAW":
        _draw_raw_sensor(painter)
    elif normalized_type == "GEN":
        _draw_generated_image(painter)
    else:
        _draw_image_file(painter)
    _draw_status_badge(painter, state)
    painter.end()
    return QIcon(pixmap)


def _draw_image_file(painter: QPainter) -> None:
    frame = QRectF(1.5, 2.0, 12.0, 10.5)
    painter.drawRoundedRect(frame, 1.5, 1.5)
    painter.setBrush(_BASE_STROKE)
    painter.drawEllipse(QRectF(3.3, 4.0, 2.0, 2.0))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    mountains = QPolygonF(
        (
            QPointF(2.8, 10.6),
            QPointF(6.2, 7.0),
            QPointF(8.2, 8.9),
            QPointF(10.0, 6.8),
            QPointF(12.3, 10.6),
        )
    )
    painter.drawPolyline(mountains)


def _draw_raw_sensor(painter: QPainter) -> None:
    frame = QRectF(1.5, 1.5, 12.0, 12.0)
    painter.drawRoundedRect(frame, 1.5, 1.5)
    painter.setBrush(_BASE_STROKE)
    for row in range(3):
        for column in range(3):
            painter.drawEllipse(
                QRectF(3.2 + column * 3.1, 3.2 + row * 3.1, 1.3, 1.3)
            )


def _draw_generated_image(painter: QPainter) -> None:
    frame = QRectF(1.5, 2.0, 12.0, 10.5)
    painter.drawRoundedRect(frame, 1.5, 1.5)
    painter.setBrush(_BASE_STROKE)
    painter.drawEllipse(QRectF(5.2, 5.0, 4.2, 4.2))


def _draw_status_badge(painter: QPainter, state: str) -> None:
    badge = QRectF(10.5, 10.5, 7.0, 7.0)
    if state == "loading":
        painter.setBrush(_STATUS_BORDER)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(badge)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(_STATUS_LOADING, 1.8))
        painter.drawArc(QRectF(11.6, 11.6, 4.8, 4.8), 35 * 16, 285 * 16)
        return

    if state == "cached":
        fill = _STATUS_CACHED
    elif state == "error":
        fill = _STATUS_ERROR
    else:
        fill = _STATUS_REGISTERED

    painter.setPen(QPen(_STATUS_BORDER, 1.0))
    painter.setBrush(fill if state != "registered" else _STATUS_BORDER)
    painter.drawEllipse(badge)
    if state == "registered":
        painter.setPen(QPen(fill, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(12.0, 12.0, 4.0, 4.0))
    elif state == "error":
        painter.setPen(QPen(_STATUS_FOREGROUND, 1.0))
        painter.drawLine(QPointF(12.7, 12.7), QPointF(15.3, 15.3))
        painter.drawLine(QPointF(15.3, 12.7), QPointF(12.7, 15.3))
