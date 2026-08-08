from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core.diagnostics import (
    RuntimeDiagnosticsSnapshot,
    format_runtime_diagnostics,
)


class DiagnosticsDialog(QDialog):
    """Display and export an observation-only runtime diagnostics snapshot."""

    def __init__(
        self,
        snapshot_provider: Callable[[], RuntimeDiagnosticsSnapshot],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Runtime Diagnostics")
        self.setObjectName("runtimeDiagnosticsDialog")
        self.setModal(True)
        self.resize(760, 580)
        self.setMinimumSize(620, 420)
        self._snapshot_provider = snapshot_provider

        self.text = QPlainTextEdit()
        self.text.setObjectName("runtimeDiagnosticsText")
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))

        self.refresh_button = QPushButton("Refresh")
        self.copy_button = QPushButton("Copy Diagnostics")
        self.save_button = QPushButton("Save as Text...")
        self.close_button = QPushButton("Close")
        self.close_button.setDefault(True)

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.copy_button)
        button_row.addWidget(self.save_button)
        button_row.addStretch(1)
        button_row.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.text, 1)
        layout.addLayout(button_row)

        self.refresh_button.clicked.connect(self.refresh)  # type: ignore[attr-defined]
        self.copy_button.clicked.connect(self.copy_diagnostics)  # type: ignore[attr-defined]
        self.save_button.clicked.connect(self.save_as_text)  # type: ignore[attr-defined]
        self.close_button.clicked.connect(self.accept)  # type: ignore[attr-defined]
        self.refresh()

    @property
    def displayed_text(self) -> str:
        return self.text.toPlainText()

    def refresh(self) -> None:
        self.text.setPlainText(format_runtime_diagnostics(self._snapshot_provider()))

    def copy_diagnostics(self) -> None:
        QApplication.clipboard().setText(self.displayed_text)

    def save_as_text(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Runtime Diagnostics",
            "pixelscope-diagnostics.txt",
            "Text files (*.txt);;All files (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(self.displayed_text, encoding="utf-8")
        except OSError:
            QMessageBox.warning(
                self,
                "Diagnostics save failed",
                "PixelScope could not save the diagnostics text.",
            )
