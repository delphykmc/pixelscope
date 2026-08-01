from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelscope.io.raw_profile import RawProfile


class RawOpenDialog(QDialog):
    """Editable/loadable profile form for unpacked RAW files."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RAW profile")
        self._profile_name = "unpacked_raw"
        self.width_box = self._spin(1, 1_000_000, 640)
        self.height_box = self._spin(1, 1_000_000, 480)
        self.stride = self._spin(1, 2_000_000_000, 1280)
        self.offset = self._spin(0, 2_000_000_000, 0)
        self.dtype = QComboBox()
        self.dtype.addItems(["uint8", "uint16"])
        self.dtype.setCurrentText("uint16")
        self.endian = QComboBox()
        self.endian.addItems(["little", "big"])
        self.bit_depth = self._spin(1, 16, 12)
        self.packing = QComboBox()
        self.packing.addItems(["unpacked_u8", "unpacked_u16"])
        self.packing.setCurrentText("unpacked_u16")
        self.layout_kind = QComboBox()
        self.layout_kind.addItems(["GRAY", "BAYER"])
        self.bayer_pattern = QComboBox()
        self.bayer_pattern.addItems(["RGGB", "GRBG", "GBRG", "BGGR"])
        self.black = QLineEdit("0")
        self.white = self._spin(1, 65535, 4095)
        form = QFormLayout()
        rows: tuple[tuple[str, QWidget], ...] = (
            ("Width", self.width_box),
            ("Height", self.height_box),
            ("Stride bytes", self.stride),
            ("Offset bytes", self.offset),
            ("dtype", self.dtype),
            ("Endianness", self.endian),
            ("Bit depth", self.bit_depth),
            ("Packing", self.packing),
            ("Channel layout", self.layout_kind),
            ("Bayer pattern", self.bayer_pattern),
            ("Black level", self.black),
            ("White level", self.white),
        )
        for title, widget in rows:
            form.addRow(title, widget)
        load_button = QPushButton("Load JSON…")
        save_button = QPushButton("Save JSON…")
        load_button.clicked.connect(self._load)  # type: ignore[attr-defined]
        save_button.clicked.connect(self._save)  # type: ignore[attr-defined]
        profile_buttons = QHBoxLayout()
        profile_buttons.addWidget(load_button)
        profile_buttons.addWidget(save_button)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_validated)  # type: ignore[attr-defined]
        buttons.rejected.connect(self.reject)  # type: ignore[attr-defined]
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        acceptance_buttons = QHBoxLayout()
        acceptance_buttons.addStretch(1)
        acceptance_buttons.addWidget(buttons)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(profile_buttons)
        layout.addWidget(separator)
        layout.addLayout(acceptance_buttons)
        self.layout_kind.currentTextChanged.connect(  # type: ignore[attr-defined]
            lambda layout_name: self.bayer_pattern.setEnabled(layout_name == "BAYER")
        )
        self.bayer_pattern.setEnabled(False)

    @staticmethod
    def _spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        return box

    def profile(self) -> RawProfile:
        dtype = self.dtype.currentText()
        layout = self.layout_kind.currentText()
        level_parts = self.black.text().replace(",", " ").split()
        if len(level_parts) not in (1, 4):
            raise ValueError("Black level requires one value or four Bayer values")
        parsed_levels = tuple(int(value) for value in level_parts)
        black_level: int | tuple[int, int, int, int] = (
            parsed_levels[0]
            if len(parsed_levels) == 1
            else (
                parsed_levels[0],
                parsed_levels[1],
                parsed_levels[2],
                parsed_levels[3],
            )
        )
        return RawProfile(
            name=self._profile_name,
            width=self.width_box.value(),
            height=self.height_box.value(),
            stride_bytes=self.stride.value(),
            offset_bytes=self.offset.value(),
            dtype=dtype,
            endianness=self.endian.currentText(),
            bit_depth=self.bit_depth.value(),
            packing=self.packing.currentText(),
            channel_layout=layout,
            bayer_pattern=self.bayer_pattern.currentText() if layout == "BAYER" else None,
            black_level=black_level,
            white_level=self.white.value(),
        )

    def set_profile(self, profile: RawProfile) -> None:
        self._profile_name = profile.name
        self.width_box.setValue(profile.width)
        self.height_box.setValue(profile.height)
        self.stride.setValue(profile.stride_bytes)
        self.offset.setValue(profile.offset_bytes)
        self.dtype.setCurrentText(profile.dtype)
        self.endian.setCurrentText(profile.endianness)
        self.bit_depth.setValue(profile.bit_depth)
        self.packing.setCurrentText(profile.packing)
        self.layout_kind.setCurrentText(profile.channel_layout)
        if profile.bayer_pattern is not None:
            self.bayer_pattern.setCurrentText(profile.bayer_pattern)
        levels = (
            (profile.black_level,) if isinstance(profile.black_level, int) else profile.black_level
        )
        self.black.setText(", ".join(str(level) for level in levels))
        self.white.setValue(profile.white_level)

    def _accept_validated(self) -> None:
        try:
            self.profile()
        except (ValueError, ValidationError) as exc:
            QMessageBox.warning(self, "Invalid RAW profile", str(exc))
            return
        self.accept()

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load RAW profile", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.set_profile(RawProfile.load_json(path))
        except (OSError, ValidationError) as exc:
            QMessageBox.warning(self, "Cannot load profile", str(exc))

    def _save(self) -> None:
        try:
            profile = self.profile()
        except (ValueError, ValidationError) as exc:
            QMessageBox.warning(self, "Invalid RAW profile", str(exc))
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save RAW profile", "", "JSON (*.json)")
        if path:
            profile.save_json(Path(path))
