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

        self.title = QLabel("Drop images or a folder here")
        self.title.setObjectName("emptyTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.open_images_button = QPushButton("Open Images...")
        self.open_folder_button = QPushButton("Open Folder...")
        self.open_raw_button = QPushButton("Open RAW...")
        for button in (
            self.open_images_button,
            self.open_folder_button,
            self.open_raw_button,
        ):
            button.setMinimumHeight(TOKENS.control_height)

        self.open_images_button.clicked.connect(  # type: ignore[attr-defined]
            self.open_images_requested
        )
        self.open_folder_button.clicked.connect(  # type: ignore[attr-defined]
            self.open_folder_requested
        )
        self.open_raw_button.clicked.connect(  # type: ignore[attr-defined]
            self.open_raw_requested
        )

        buttons = QHBoxLayout()
        buttons.setSpacing(TOKENS.spacing_sm)
        buttons.addWidget(self.open_images_button)
        buttons.addWidget(self.open_folder_button)
        buttons.addWidget(self.open_raw_button)

        self.formats_hint = QLabel("PNG · JPEG · BMP · RAW")
        self.shortcuts_hint = QLabel("Ctrl+O images · Ctrl+Shift+O folder")
        self.gestures_hint = QLabel("On an image: Ctrl+drag ROI · Alt+drag line profile")
        for hint in (
            self.formats_hint,
            self.shortcuts_hint,
            self.gestures_hint,
        ):
            hint.setObjectName("emptyHint")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(TOKENS.spacing_lg)
        layout.addStretch(1)
        layout.addWidget(self.title)
        layout.addLayout(buttons)
        layout.addWidget(self.formats_hint)
        layout.addWidget(self.shortcuts_hint)
        layout.addWidget(self.gestures_hint)
        layout.addStretch(1)
