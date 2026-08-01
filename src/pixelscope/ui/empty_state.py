from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from pixelscope.ui.design_tokens import TOKENS, empty_state_style


class EmptyWorkspace(QWidget):
    open_images_requested = Signal()
    open_folder_requested = Signal()
    open_raw_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setStyleSheet(empty_state_style())
        title = QLabel("Drop images or a folder here")
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel(
            "PNG · BMP · RAW   |   Ctrl+O images   |   Ctrl+Shift+O folder\n"
            "Ctrl/Alt drag creates ROI or line profile"
        )
        hint.setObjectName("emptyHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        buttons = QHBoxLayout()
        buttons.setSpacing(TOKENS.spacing_sm)
        for text, signal in (
            ("Open Image", self.open_images_requested),
            ("Open Folder", self.open_folder_requested),
            ("Open RAW", self.open_raw_requested),
        ):
            button = QPushButton(text)
            button.setMinimumHeight(TOKENS.control_height)
            button.clicked.connect(signal)  # type: ignore[attr-defined]
            buttons.addWidget(button)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(TOKENS.spacing_lg)
        layout.addStretch(1)
        layout.addWidget(title)
        layout.addLayout(buttons)
        layout.addWidget(hint)
        layout.addStretch(1)
