from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from pixelscope.io.yuv_profile import YuvProfile


class YuvOpenDialog(QDialog):
    """Minimal explicit WP-C1 interpretation dialog for ambiguous `.yuv` files."""

    GENERIC_RAW = "GENERIC_RAW"

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setWindowTitle("YUV profile")
        self._source_path: Path | None = None

        self.width_box = QSpinBox()
        self.width_box.setRange(1, 1_000_000)
        self.width_box.setValue(1920)
        self.height_box = QSpinBox()
        self.height_box.setRange(1, 1_000_000)
        self.height_box.setValue(1080)
        self.layout_kind = QComboBox()
        self.layout_kind.addItem("YUV420 · Y + interleaved UV", "YUV420")
        self.layout_kind.addItem("YUV422 · Y + interleaved UV", "YUV422")
        self.layout_kind.addItem("YUV444 · Y + interleaved UV", "YUV444")
        self.layout_kind.addItem("Generic RAW profile…", self.GENERIC_RAW)
        self.fixed_contract = QLabel("8-bit · UV order · BT.601 Full · tightly packed")
        self.fixed_contract.setWordWrap(True)
        self.file_size = QLabel("Expected size —")
        self.file_size.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form = QFormLayout()
        form.addRow("Width", self.width_box)
        form.addRow("Height", self.height_box)
        form.addRow("Interpretation", self.layout_kind)
        form.addRow("Contract", self.fixed_contract)
        form.addRow("File size", self.file_size)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_validated)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self.width_box.valueChanged.connect(self._update_file_size)  # type: ignore[attr-defined]
        self.height_box.valueChanged.connect(self._update_file_size)  # type: ignore[attr-defined]
        self.layout_kind.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._update_file_size
        )
        self._update_file_size()

    def set_source_path(self, path: str | Path) -> None:
        self._source_path = Path(path)
        self._update_file_size()

    def set_profile(self, profile: YuvProfile) -> None:
        self.width_box.setValue(profile.width)
        self.height_box.setValue(profile.height)
        index = self.layout_kind.findData(profile.channel_layout)
        if index >= 0:
            self.layout_kind.setCurrentIndex(index)
        self._update_file_size()

    def uses_generic_raw(self) -> bool:
        return self.layout_kind.currentData() == self.GENERIC_RAW

    def profile(self) -> YuvProfile:
        if self.uses_generic_raw():
            raise ValueError("Generic RAW selection does not define a YUV profile")
        return YuvProfile(
            name=self._source_path.stem if self._source_path is not None else "native_yuv",
            width=self.width_box.value(),
            height=self.height_box.value(),
            channel_layout=self.layout_kind.currentData(),
        )

    def _accept_validated(self) -> None:
        if self.uses_generic_raw():
            self.accept()
            return
        try:
            profile = self.profile()
        except (ValidationError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid YUV profile", str(exc))
            return
        if self._source_path is not None and self._source_path.is_file():
            actual = self._source_path.stat().st_size
            if actual != profile.expected_file_size:
                QMessageBox.warning(
                    self,
                    "YUV file size mismatch",
                    f"Expected {profile.expected_file_size} bytes but file has {actual} bytes.",
                )
                return
        self.accept()

    def _update_file_size(self) -> None:
        if self.uses_generic_raw():
            self.fixed_contract.setText("Use the existing generic RAW profile workflow")
            self.file_size.setText("Expected size —")
            return
        self.fixed_contract.setText("8-bit · UV order · BT.601 Full · tightly packed")
        try:
            profile = self.profile()
        except (ValidationError, ValueError):
            self.file_size.setText("Expected size —")
            return
        text = f"Expected {profile.expected_file_size:,} bytes"
        if self._source_path is not None and self._source_path.is_file():
            actual = self._source_path.stat().st_size
            state = "match" if actual == profile.expected_file_size else f"actual {actual:,}"
            text += f" · {state}"
        self.file_size.setText(text)
