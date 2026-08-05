from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixelscope.io.raw_profile import RawProfile


class RawOpenDialog(QDialog):
    """Editable RAW profile form with source-file compatibility diagnostics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RAW profile")
        self.setMinimumWidth(520)
        self._profile_name = "unpacked_raw"
        self._source_path: Path | None = None
        self._actual_file_size: int | None = None

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

        self.black_gray = self._spin(0, 65535, 0)
        self.black_r = self._spin(0, 65535, 0)
        self.black_gr = self._spin(0, 65535, 0)
        self.black_gb = self._spin(0, 65535, 0)
        self.black_b = self._spin(0, 65535, 0)
        self.black = QLineEdit("0")
        self.black.hide()
        self.white = self._spin(1, 65535, 4095)

        self.minimum_stride_value = QLabel()
        self.minimum_stride_value.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.use_minimum_stride_button = QPushButton("Use minimum stride")
        minimum_stride_widget = QWidget()
        minimum_stride_layout = QHBoxLayout(minimum_stride_widget)
        minimum_stride_layout.setContentsMargins(0, 0, 0, 0)
        minimum_stride_layout.addWidget(self.minimum_stride_value, 1)
        minimum_stride_layout.addWidget(self.use_minimum_stride_button)

        self.form = QFormLayout()
        self.form.addRow("Width", self.width_box)
        self.form.addRow("Height", self.height_box)
        self.form.addRow("Stride bytes", self.stride)
        self.form.addRow("Minimum stride", minimum_stride_widget)
        self.form.addRow("Offset bytes", self.offset)
        self.form.addRow("Data type", self.dtype)
        self.form.addRow("Byte order", self.endian)
        self.form.addRow("Bit depth", self.bit_depth)
        self.form.addRow("Packing", self.packing)
        self.form.addRow("Pixel layout", self.layout_kind)
        self.form.addRow("Bayer pattern", self.bayer_pattern)
        self.form.addRow("Black level", self.black_gray)
        self.form.addRow("Black level R", self.black_r)
        self.form.addRow("Black level Gr", self.black_gr)
        self.form.addRow("Black level Gb", self.black_gb)
        self.form.addRow("Black level B", self.black_b)
        self.form.addRow("White level", self.white)

        self.source_path_value = QLabel("No RAW source selected")
        self.source_path_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.source_path_value.setWordWrap(True)
        self.expected_size_value = QLabel("Expected minimum file size: —")
        self.actual_size_value = QLabel("Actual file size: —")
        self.file_status = QLabel()
        self.file_status.setWordWrap(True)
        diagnostics = QFormLayout()
        diagnostics.addRow("RAW source", self.source_path_value)
        diagnostics.addRow("", self.expected_size_value)
        diagnostics.addRow("", self.actual_size_value)
        diagnostics.addRow("", self.file_status)

        self.load_button = QPushButton("Load JSON…")
        self.save_button = QPushButton("Save JSON…")
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        for button in (
            self.load_button,
            self.save_button,
            self.ok_button,
            self.cancel_button,
        ):
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
        self.load_button.clicked.connect(self._load)  # type: ignore[attr-defined]
        self.save_button.clicked.connect(self._save)  # type: ignore[attr-defined]
        self.ok_button.clicked.connect(self._accept_validated)  # type: ignore[attr-defined]
        self.cancel_button.clicked.connect(self.reject)  # type: ignore[attr-defined]

        self.skip_json_confirmation = QCheckBox(
            "Don't confirm JSON profiles next time"
        )
        self.skip_json_confirmation.hide()

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)

        self.button_grid = QGridLayout()
        self.button_grid.setContentsMargins(0, 0, 0, 0)
        self.button_grid.setHorizontalSpacing(8)
        self.button_grid.setVerticalSpacing(8)
        self.button_grid.setColumnStretch(0, 1)
        self.button_grid.setColumnStretch(1, 1)
        self.button_grid.addWidget(self.load_button, 0, 0)
        self.button_grid.addWidget(self.save_button, 0, 1)
        self.button_grid.addWidget(separator, 1, 0, 1, 2)
        self.button_grid.addWidget(self.skip_json_confirmation, 2, 0, 1, 2)
        self.button_grid.addWidget(self.ok_button, 3, 0)
        self.button_grid.addWidget(self.cancel_button, 3, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addSpacing(8)
        layout.addLayout(diagnostics)
        layout.addSpacing(8)
        layout.addLayout(self.button_grid)

        self.dtype.currentTextChanged.connect(  # type: ignore[attr-defined]
            self._data_type_changed
        )
        self.packing.currentTextChanged.connect(  # type: ignore[attr-defined]
            self._packing_changed
        )
        self.layout_kind.currentTextChanged.connect(  # type: ignore[attr-defined]
            self._pixel_layout_changed
        )
        self.width_box.valueChanged.connect(self._update_diagnostics)  # type: ignore[attr-defined]
        self.height_box.valueChanged.connect(self._update_diagnostics)  # type: ignore[attr-defined]
        self.stride.valueChanged.connect(self._update_diagnostics)  # type: ignore[attr-defined]
        self.offset.valueChanged.connect(self._update_diagnostics)  # type: ignore[attr-defined]
        self.bit_depth.valueChanged.connect(self._bit_depth_changed)  # type: ignore[attr-defined]
        self.use_minimum_stride_button.clicked.connect(  # type: ignore[attr-defined]
            lambda: self.stride.setValue(self.minimum_stride_bytes())
        )

        self._data_type_changed(self.dtype.currentText())
        self._pixel_layout_changed(self.layout_kind.currentText())
        self._update_diagnostics()

    @staticmethod
    def _spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        return box

    @staticmethod
    def _format_bytes(value: int) -> str:
        return f"{value:,} bytes"

    def set_source_path(self, path: str | Path | None) -> None:
        self._source_path = Path(path).resolve() if path is not None else None
        self._actual_file_size = None
        if self._source_path is not None:
            try:
                self._actual_file_size = self._source_path.stat().st_size
            except OSError:
                self._actual_file_size = None
        self._update_diagnostics()

    @property
    def source_path(self) -> Path | None:
        return self._source_path

    def set_json_confirmation_option_visible(self, visible: bool) -> None:
        self.skip_json_confirmation.setChecked(False)
        self.skip_json_confirmation.setVisible(visible)

    def skip_json_confirmation_requested(self) -> bool:
        return self.skip_json_confirmation.isVisible() and self.skip_json_confirmation.isChecked()

    def minimum_stride_bytes(self) -> int:
        item_size = 1 if self.dtype.currentText() == "uint8" else 2
        return self.width_box.value() * item_size

    def expected_minimum_file_size(self) -> int:
        return (
            self.offset.value()
            + (self.height_box.value() - 1) * self.stride.value()
            + self.minimum_stride_bytes()
        )

    def profile(self) -> RawProfile:
        layout = self.layout_kind.currentText()
        if layout == "BAYER":
            black_level: int | tuple[int, int, int, int] = (
                self.black_r.value(),
                self.black_gr.value(),
                self.black_gb.value(),
                self.black_b.value(),
            )
        else:
            black_level = self.black_gray.value()
        return RawProfile(
            name=self._profile_name,
            width=self.width_box.value(),
            height=self.height_box.value(),
            stride_bytes=self.stride.value(),
            offset_bytes=self.offset.value(),
            dtype=self.dtype.currentText(),
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
        self.dtype.setCurrentText(profile.dtype)
        self.packing.setCurrentText(profile.packing)
        self.stride.setValue(profile.stride_bytes)
        self.offset.setValue(profile.offset_bytes)
        self.endian.setCurrentText(profile.endianness)
        self.bit_depth.setValue(profile.bit_depth)
        self.layout_kind.setCurrentText(profile.channel_layout)
        if profile.bayer_pattern is not None:
            self.bayer_pattern.setCurrentText(profile.bayer_pattern)

        if isinstance(profile.black_level, tuple):
            levels = profile.black_level
        else:
            levels = (profile.black_level,) * 4
        self.black_gray.setValue(
            profile.black_level if isinstance(profile.black_level, int) else profile.black_level[0]
        )
        for control, value in zip(
            (self.black_r, self.black_gr, self.black_gb, self.black_b),
            levels,
            strict=True,
        ):
            control.setValue(value)
        self.black.setText(", ".join(str(level) for level in levels))
        self.white.setValue(profile.white_level)
        self._update_diagnostics()

    def _data_type_changed(self, data_type: str) -> None:
        expected_packing = "unpacked_u8" if data_type == "uint8" else "unpacked_u16"
        if self.packing.currentText() != expected_packing:
            self.packing.blockSignals(True)
            self.packing.setCurrentText(expected_packing)
            self.packing.blockSignals(False)
        self.endian.setEnabled(data_type == "uint16")
        maximum_depth = 8 if data_type == "uint8" else 16
        self.bit_depth.setMaximum(maximum_depth)
        if self.bit_depth.value() > maximum_depth:
            self.bit_depth.setValue(maximum_depth)
        self._bit_depth_changed(self.bit_depth.value())
        self._update_diagnostics()

    def _packing_changed(self, packing: str) -> None:
        expected_type = "uint8" if packing == "unpacked_u8" else "uint16"
        if self.dtype.currentText() != expected_type:
            self.dtype.setCurrentText(expected_type)
        else:
            self._update_diagnostics()

    def _bit_depth_changed(self, depth: int) -> None:
        maximum = (1 << depth) - 1
        self.white.setMaximum(maximum)
        for control in (
            self.black_gray,
            self.black_r,
            self.black_gr,
            self.black_gb,
            self.black_b,
        ):
            control.setMaximum(maximum)
        if self.white.value() > maximum:
            self.white.setValue(maximum)
        self._update_diagnostics()

    def _pixel_layout_changed(self, layout_name: str) -> None:
        is_bayer = layout_name == "BAYER"
        self.bayer_pattern.setEnabled(is_bayer)
        self._set_form_row_visible(self.bayer_pattern, is_bayer)
        self._set_form_row_visible(self.black_gray, not is_bayer)
        for control in (self.black_r, self.black_gr, self.black_gb, self.black_b):
            self._set_form_row_visible(control, is_bayer)
        self._update_legacy_black_text()

    def _set_form_row_visible(self, field: QWidget, visible: bool) -> None:
        label = self.form.labelForField(field)
        if label is not None:
            label.setVisible(visible)
        field.setVisible(visible)

    def _update_legacy_black_text(self) -> None:
        if self.layout_kind.currentText() == "BAYER":
            values = (
                self.black_r.value(),
                self.black_gr.value(),
                self.black_gb.value(),
                self.black_b.value(),
            )
        else:
            values = (self.black_gray.value(),)
        self.black.setText(", ".join(str(value) for value in values))

    def _update_diagnostics(self, _value: object = None) -> None:
        minimum_stride = self.minimum_stride_bytes()
        self.minimum_stride_value.setText(self._format_bytes(minimum_stride))
        expected = self.expected_minimum_file_size()
        self.expected_size_value.setText(
            f"Expected minimum file size: {self._format_bytes(expected)}"
        )

        if self._source_path is None:
            self.source_path_value.setText("No RAW source selected")
            self.actual_size_value.setText("Actual file size: —")
            self.file_status.setText("")
            self.ok_button.setEnabled(self.stride.value() >= minimum_stride)
            return

        self.source_path_value.setText(str(self._source_path))
        if self._actual_file_size is None:
            self.actual_size_value.setText("Actual file size: unavailable")
            self.file_status.setText("Error: the RAW source cannot be accessed")
            self.file_status.setStyleSheet("color: #ff5f56;")
            self.ok_button.setEnabled(False)
            return

        actual = self._actual_file_size
        self.actual_size_value.setText(
            f"Actual file size: {self._format_bytes(actual)}"
        )
        stride_valid = self.stride.value() >= minimum_stride
        if not stride_valid:
            self.file_status.setText(
                f"Error: stride is {minimum_stride - self.stride.value():,} bytes "
                "smaller than one image row"
            )
            self.file_status.setStyleSheet("color: #ff5f56;")
            self.ok_button.setEnabled(False)
        elif actual < expected:
            self.file_status.setText(
                f"Error: RAW file is {expected - actual:,} bytes too small"
            )
            self.file_status.setStyleSheet("color: #ff5f56;")
            self.ok_button.setEnabled(False)
        elif actual > expected:
            self.file_status.setText(
                f"Warning: {actual - expected:,} trailing bytes will be ignored"
            )
            self.file_status.setStyleSheet("color: #d6a53a;")
            self.ok_button.setEnabled(True)
        else:
            self.file_status.setText("RAW file size matches the profile")
            self.file_status.setStyleSheet("")
            self.ok_button.setEnabled(True)

    def _accept_validated(self) -> None:
        self._update_legacy_black_text()
        try:
            self.profile()
        except (ValueError, ValidationError) as exc:
            QMessageBox.warning(self, "Invalid RAW profile", str(exc))
            return
        self._update_diagnostics()
        if not self.ok_button.isEnabled():
            QMessageBox.warning(self, "Invalid RAW source", self.file_status.text())
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
        self._update_legacy_black_text()
        try:
            profile = self.profile()
        except (ValueError, ValidationError) as exc:
            QMessageBox.warning(self, "Invalid RAW profile", str(exc))
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save RAW profile", "", "JSON (*.json)")
        if path:
            profile.save_json(Path(path))
