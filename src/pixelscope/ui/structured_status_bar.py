from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from pixelscope.ui.design_tokens import TOKENS


class StructuredStatusBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.active_file = QLabel("No active file")
        self.image_info = QLabel("—")
        self.coordinate = QLabel("Position (   -,    -)")
        self.pixel_value = QLabel("—")
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
        self.active_file.setToolTip(name)
        self.image_info.setText(info or "—")
