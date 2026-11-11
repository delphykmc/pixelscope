"""Worker-side presentation images: exact crop above a readable metadata footer."""
from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QImageWriter, QPainter


def annotate_memo_crop(payload: bytes, basename: str, coordinates: str) -> bytes:
    image = QImage.fromData(payload)
    if image.isNull():
        raise ValueError("Saved ROI crop cannot be decoded")
    font = QFont("Segoe UI", 10)
    font.setPixelSize(13)
    width, height = max(image.width(), 320), image.height() + 84
    if width * height > 16 * 1024 * 1024:
        raise ValueError("Crop exceeds annotated report image budget; original remains in Memo")
    canvas = QImage(width, height, QImage.Format.Format_ARGB32)
    if canvas.isNull():
        raise ValueError("Cannot allocate report image; original remains in Memo")
    canvas.fill(QColor("#f1f4f7"))
    painter = QPainter(canvas)
    try:
        painter.drawImage((width - image.width()) // 2, 0, image)
        painter.setFont(font)
        painter.setPen(QColor("#233142"))
        metrics = painter.fontMetrics()
        name = metrics.elidedText(basename, Qt.TextElideMode.ElideMiddle, canvas.width() - 24)
        painter.drawText(
            QRect(12, image.height() + 6, canvas.width() - 24, 24), Qt.AlignmentFlag.AlignLeft, name
        )
        painter.drawText(
            QRect(12, image.height() + 32, canvas.width() - 24, 48),
            Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
            coordinates,
        )
    finally:
        painter.end()
    canvas.setText("Source", basename)
    canvas.setText("ROI", coordinates)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    writer = QImageWriter(buffer, QByteArray(b"png"))
    if not writer.write(canvas):
        raise OSError("Annotated Memo PNG could not be encoded")
    return buffer.data().data()
