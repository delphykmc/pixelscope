from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QWidget

from pixelscope.ui.design_tokens import TOKENS


class _ElidingStatusLabel(QLabel):
    """Keep full logical text while painting a bounded status-bar value."""

    def __init__(
        self,
        text: str,
        elide_mode: Qt.TextElideMode,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._elide_mode = elide_mode
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
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
            self._elide_mode,
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


class StructuredStatusBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.active_file = _ElidingStatusLabel(
            "No active file",
            Qt.TextElideMode.ElideMiddle,
        )
        self.image_info = QLabel("—")
        self.coordinate = QLabel("Position (   -,    -)")
        self.pixel_value = _ElidingStatusLabel(
            "—",
            Qt.TextElideMode.ElideRight,
        )
        self.zoom = QLabel("Zoom —")
        self.task = QLabel("Ready")
        self.coordinate.setMinimumWidth(152)
        self.pixel_value.setMinimumWidth(210)
        self.coordinate.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.pixel_value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(TOKENS.spacing_sm, 0, TOKENS.spacing_sm, 0)
        layout.setSpacing(TOKENS.spacing_sm)
        for index, widget in enumerate(
            (
                self.active_file,
                self.image_info,
                self.coordinate,
                self.pixel_value,
                self.zoom,
                self.task,
            )
        ):
            if index:
                separator = QFrame()
                separator.setFrameShape(QFrame.Shape.VLine)
                separator.setFrameShadow(QFrame.Shadow.Sunken)
                layout.addWidget(separator)
            layout.addWidget(widget, 1 if index in (0, 3) else 0)

    def reset_cursor(self) -> None:
        self.coordinate.setText("Position (   -,    -)")
        self.pixel_value.setText("—")

    def set_active_document(self, name: str = "", info: str = "") -> None:
        self.active_file.setText(name or "No active file")
        self.image_info.setText(info or "—")
