from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from pixelscope.io.raw_format import (
    BitAlignment,
    ContainerDType,
    Endianness,
    StorageFormat,
    container_bit_count,
    container_byte_count,
    minimum_row_bytes,
    storage_format_spec,
)
from pixelscope.io.raw_profile import RawProfile

RAW_DIALOG_WIDTH = 280
FORM_LABEL_WIDTH = 100
FIELD_WIDTH = 120
DIALOG_BUTTON_WIDTH = 92


class AlignedFormGrid(QGridLayout):
    """Three-column form: fixed label, adaptive gap, fixed field."""

    def __init__(self) -> None:
        super().__init__()
        self._labels: dict[QWidget, QLabel] = {}
        self.setContentsMargins(0, 0, 0, 0)
        self.setHorizontalSpacing(0)
        self.setVerticalSpacing(6)
        self.setColumnMinimumWidth(0, FORM_LABEL_WIDTH)
        self.setColumnStretch(0, 0)
        self.setColumnStretch(1, 1)
        self.setColumnMinimumWidth(2, FIELD_WIDTH)
        self.setColumnStretch(2, 0)

    def add_field_row(self, label: str | QLabel, field: QWidget) -> int:
        row = self.rowCount()
        label_widget = QLabel(label) if isinstance(label, str) else label
        label_widget.setFixedWidth(FORM_LABEL_WIDTH)
        label_widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.addWidget(label_widget, row, 0)
        self.addWidget(
            field,
            row,
            2,
            alignment=(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
        )
        self._labels[field] = label_widget
        return row

    def add_spanning_row(self, widget: QWidget) -> int:
        row = self.rowCount()
        self.addWidget(widget, row, 0, 1, 3)
        return row

    def labelForField(self, field: QWidget) -> QLabel | None:
        """Match the QFormLayout lookup API used by existing tests and code."""

        return self._labels.get(field)


class RawOpenDialog(QDialog):
    """Editable RAW profile form with source-file compatibility diagnostics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("RAW profile")
        self.setSizeGripEnabled(True)
        self._last_auto_fit_size: QSize | None = None
        self._profile_name = "unpacked_raw"
        self._source_path: Path | None = None
        self._actual_file_size: int | None = None
        self._json_option_available = False
        self._file_size_state = "unavailable"
        self._unpacked_container: ContainerDType = "uint16"
        self._unpacked_endianness: Endianness = "little"
        self._unpacked_alignment: BitAlignment = "lsb"
        self._unpacked_bit_depth = 12
        self._stride_is_auto = True
        self._updating_stride = False

        self.width_box = self._spin(1, 1_000_000, 640)
        self.height_box = self._spin(1, 1_000_000, 480)
        self.stride = self._spin(1, 2_000_000_000, 1280)
        self.offset = self._spin(0, 2_000_000_000, 0)

        self.storage_format = self._data_combo(
            [
                ("Unpacked", "unpacked"),
                ("MIPI RAW10", "mipi_raw10"),
                ("MIPI RAW12", "mipi_raw12"),
                ("MIPI RAW14", "mipi_raw14"),
            ],
            "unpacked",
        )
        self.container = self._data_combo(
            [
                ("uint8", "uint8"),
                ("uint16", "uint16"),
            ],
            "uint16",
        )
        self.bit_depth = self._spin(1, 16, 12)
        self.byte_order = self._data_combo(
            [
                ("little", "little"),
                ("big", "big"),
            ],
            "little",
        )
        self.bit_alignment = self._data_combo(
            [
                ("LSB aligned", "lsb"),
                ("MSB aligned", "msb"),
            ],
            "lsb",
        )
        self.layout_kind = self._combo(["GRAY", "BAYER"], "GRAY")
        self.bayer_pattern = self._combo(
            ["RGGB", "GRBG", "GBRG", "BGGR"],
            "RGGB",
        )

        # Compatibility aliases for code that still locates the old widgets.
        self.packing = self.storage_format
        self.dtype = self.container
        self.endian = self.byte_order

        self.minimum_stride_icon = QLabel()
        self.minimum_stride_icon.setFixedSize(18, 18)
        self.minimum_stride_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.minimum_stride_icon.setPixmap(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(16, 16)
        )
        self.minimum_stride_value = QLabel()
        self.minimum_stride_value.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.minimum_stride_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.minimum_stride_value.setWordWrap(True)
        self.minimum_stride_value.setMinimumWidth(0)
        self.minimum_stride_value.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.minimum_stride_row = QWidget()
        minimum_stride_layout = QHBoxLayout(self.minimum_stride_row)
        minimum_stride_layout.setContentsMargins(0, 2, 0, 2)
        minimum_stride_layout.setSpacing(6)
        minimum_stride_layout.addWidget(self.minimum_stride_icon)
        minimum_stride_layout.addWidget(self.minimum_stride_value, 1)

        layout_form = AlignedFormGrid()
        layout_form.add_field_row("Width", self.width_box)
        layout_form.add_field_row("Height", self.height_box)
        layout_form.add_field_row("Stride bytes", self.stride)
        layout_form.add_spanning_row(self.minimum_stride_row)
        layout_form.add_field_row("Offset bytes", self.offset)
        layout_form.add_field_row("Storage format", self.storage_format)
        layout_form.add_field_row("Container", self.container)
        layout_form.add_field_row("Bit depth", self.bit_depth)
        layout_form.add_field_row("Byte order", self.byte_order)
        layout_form.add_field_row("Bit alignment", self.bit_alignment)
        layout_form.add_field_row("Pixel layout", self.layout_kind)
        layout_form.add_field_row("Bayer pattern", self.bayer_pattern)
        self.form = layout_form

        data_layout_group = QGroupBox("1. Data layout")
        data_layout = QVBoxLayout(data_layout_group)
        data_layout.setContentsMargins(10, 8, 10, 8)
        data_layout.addLayout(layout_form)

        self.expected_file_size_label = QLabel("Expected size")
        self.actual_file_size_label = QLabel("Actual size")
        self.expected_file_size_value = self._value_label("—")
        self.actual_file_size_value = self._value_label("—")
        self.expected_size_value = self.expected_file_size_value
        self.actual_size_value = self.actual_file_size_value

        self.file_size_form = AlignedFormGrid()
        self.file_size_form.add_field_row(
            self.expected_file_size_label,
            self.expected_file_size_value,
        )
        self.file_size_form.add_field_row(
            self.actual_file_size_label,
            self.actual_file_size_value,
        )

        self.file_status_icon = QLabel()
        self.file_status_icon.setFixedSize(20, 20)
        self.file_status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_status = QLabel()
        self.file_status.setWordWrap(True)
        self.file_status.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.file_status_row = QHBoxLayout()
        self.file_status_row.setContentsMargins(0, 2, 0, 0)
        self.file_status_row.setSpacing(6)
        self.file_status_row.addWidget(self.file_status_icon)
        self.file_status_row.addWidget(self.file_status, 1)

        file_size_group = QGroupBox("2. File size")
        file_size_layout = QVBoxLayout(file_size_group)
        file_size_layout.setContentsMargins(10, 8, 10, 8)
        file_size_layout.setSpacing(6)
        file_size_layout.addLayout(self.file_size_form)
        file_size_layout.addLayout(self.file_status_row)

        self.black_gray = self._spin(0, 65535, 0)
        self.black_r = self._spin(0, 65535, 0)
        self.black_gr = self._spin(0, 65535, 0)
        self.black_gb = self._spin(0, 65535, 0)
        self.black_b = self._spin(0, 65535, 0)
        self.black = QLineEdit("0")
        self.black.hide()
        self.white = self._spin(1, 65535, 4095)

        gray_levels_page = QWidget()
        gray_levels_form = AlignedFormGrid()
        gray_levels_form.add_field_row("Black level", self.black_gray)
        gray_levels_page.setLayout(gray_levels_form)

        bayer_levels_page = QWidget()
        bayer_levels_form = AlignedFormGrid()
        bayer_levels_form.add_field_row("Black level R", self.black_r)
        bayer_levels_form.add_field_row("Black level Gr", self.black_gr)
        bayer_levels_form.add_field_row("Black level Gb", self.black_gb)
        bayer_levels_form.add_field_row("Black level B", self.black_b)
        bayer_levels_page.setLayout(bayer_levels_form)

        self.black_level_stack = QStackedWidget()
        self.black_level_stack.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self.black_level_stack.addWidget(gray_levels_page)
        self.black_level_stack.addWidget(bayer_levels_page)

        white_level_form = AlignedFormGrid()
        white_level_form.add_field_row("White level", self.white)

        signal_levels_group = QGroupBox("3. Signal levels")
        signal_levels_layout = QVBoxLayout(signal_levels_group)
        signal_levels_layout.setContentsMargins(10, 8, 10, 8)
        signal_levels_layout.setSpacing(6)
        signal_levels_layout.addWidget(self.black_level_stack)
        signal_levels_layout.addLayout(white_level_form)

        self.load_button = QPushButton("Load Profile…")
        self.save_button = QPushButton("Save Profile…")
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.ok_button.setDefault(True)
        self.ok_button.setFixedWidth(DIALOG_BUTTON_WIDTH)
        self.cancel_button.setFixedWidth(DIALOG_BUTTON_WIDTH)
        for button in (self.load_button, self.save_button):
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            button.setAutoDefault(False)
        self.cancel_button.setAutoDefault(False)
        self.load_button.clicked.connect(self._load)  # type: ignore[attr-defined]
        self.save_button.clicked.connect(self._save)  # type: ignore[attr-defined]
        self.ok_button.clicked.connect(self._accept_validated)  # type: ignore[attr-defined]
        self.cancel_button.clicked.connect(self.reject)  # type: ignore[attr-defined]

        self.json_actions_layout = QHBoxLayout()
        self.json_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.json_actions_layout.setSpacing(8)
        self.json_actions_layout.addWidget(self.load_button, 1)
        self.json_actions_layout.addWidget(self.save_button, 1)

        self.dont_show_json_profiles = QCheckBox("Don't show JSON profiles next time")
        self.dont_show_json_profiles.hide()
        self.skip_json_confirmation = self.dont_show_json_profiles

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)

        self.dialog_actions_layout = QHBoxLayout()
        self.dialog_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.dialog_actions_layout.setSpacing(8)
        self.dialog_actions_layout.addStretch(1)
        self.dialog_actions_layout.addWidget(self.ok_button)
        self.dialog_actions_layout.addWidget(self.cancel_button)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(10, 10, 10, 8)
        body_layout.setSpacing(8)
        body_layout.addWidget(data_layout_group)
        body_layout.addWidget(file_size_group)
        body_layout.addWidget(signal_levels_group)
        body_layout.addSpacing(2)
        body_layout.addLayout(self.json_actions_layout)
        body_layout.addWidget(self.dont_show_json_profiles)
        body_layout.addStretch(1)

        self.body_scroll = QScrollArea()
        self.body_scroll.setObjectName("rawProfileBodyScroll")
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_scroll.setWidget(body)
        self.body_scroll.setMinimumSize(0, 0)
        self.body_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.footer = QWidget()
        footer_layout = QVBoxLayout(self.footer)
        footer_layout.setContentsMargins(10, 0, 10, 10)
        footer_layout.setSpacing(8)
        footer_layout.addWidget(separator)
        footer_layout.addLayout(self.dialog_actions_layout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.body_scroll, 1)
        layout.addWidget(self.footer)

        self.storage_format.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._storage_format_changed
        )
        self.container.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._container_changed
        )
        self.byte_order.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._byte_order_changed
        )
        self.bit_alignment.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._bit_alignment_changed
        )
        self.layout_kind.currentTextChanged.connect(  # type: ignore[attr-defined]
            self._pixel_layout_changed
        )
        self.width_box.valueChanged.connect(self._width_changed)  # type: ignore[attr-defined]
        self.height_box.valueChanged.connect(self._update_diagnostics)  # type: ignore[attr-defined]
        self.stride.valueChanged.connect(self._stride_changed)  # type: ignore[attr-defined]
        self.offset.valueChanged.connect(self._update_diagnostics)  # type: ignore[attr-defined]
        self.bit_depth.valueChanged.connect(self._bit_depth_changed)  # type: ignore[attr-defined]
        for control in (
            self.black_gray,
            self.black_r,
            self.black_gr,
            self.black_gb,
            self.black_b,
        ):
            control.valueChanged.connect(  # type: ignore[attr-defined]
                self._update_legacy_black_text
            )

        self._storage_format_changed()
        self._pixel_layout_changed(self.layout_kind.currentText())
        self._update_diagnostics()
        self.resize(RAW_DIALOG_WIDTH, self.sizeHint().height())
        self._last_auto_fit_size = self.size()
        self._resize_dialog_to_content()

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        if not hasattr(self, "body_scroll") or not hasattr(self, "footer"):
            return hint
        body = self.body_scroll.widget()
        if body is None:
            return hint
        return QSize(
            hint.width(),
            body.sizeHint().height() + self.footer.sizeHint().height(),
        )

    @staticmethod
    def _spin(minimum: int, maximum: int, value: int) -> QSpinBox:
        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        box.setFixedWidth(FIELD_WIDTH)
        return box

    @staticmethod
    def _combo(items: list[str], current: str) -> QComboBox:
        combo = QComboBox()
        combo.addItems(items)
        combo.setCurrentText(current)
        combo.setFixedWidth(FIELD_WIDTH)
        return combo

    @staticmethod
    def _data_combo(items: list[tuple[str, Any]], current: Any) -> QComboBox:
        combo = QComboBox()
        for label, data in items:
            combo.addItem(label, data)
        index = combo.findData(current)
        combo.setCurrentIndex(max(0, index))
        combo.setFixedWidth(FIELD_WIDTH)
        return combo

    @staticmethod
    def _set_combo_data(combo: QComboBox, data: Any) -> None:
        index = combo.findData(data)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _value_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setFixedWidth(FIELD_WIDTH)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @staticmethod
    def _format_bytes(value: int) -> str:
        return f"{value:,} bytes"

    @property
    def file_size_state(self) -> str:
        return self._file_size_state

    @property
    def stride_is_auto(self) -> bool:
        return self._stride_is_auto

    @property
    def storage_format_key(self) -> StorageFormat:
        return cast(StorageFormat, self.storage_format.currentData())

    @property
    def container_dtype(self) -> ContainerDType | None:
        return cast(ContainerDType | None, self.container.currentData())

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
        self._json_option_available = visible
        self.dont_show_json_profiles.setChecked(False)
        self.dont_show_json_profiles.setVisible(visible)

    def dont_show_json_profiles_requested(self) -> bool:
        return self._json_option_available and self.dont_show_json_profiles.isChecked()

    def skip_json_confirmation_requested(self) -> bool:
        return self.dont_show_json_profiles_requested()

    def sample_size_bytes(self) -> int:
        container = self.container_dtype
        if self.storage_format_key != "unpacked" or container is None:
            return 0
        return container_byte_count(container)

    def minimum_stride_bytes(self) -> int:
        return minimum_row_bytes(
            self.width_box.value(),
            self.storage_format_key,
            self.container_dtype,
        )

    def expected_file_size(self) -> int:
        return (
            self.offset.value()
            + (self.height_box.value() - 1) * self.stride.value()
            + self.minimum_stride_bytes()
        )

    def expected_minimum_file_size(self) -> int:
        return self.expected_file_size()

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

        storage_format = self.storage_format_key
        container = self.container_dtype if storage_format == "unpacked" else None
        endianness: Endianness | None = None
        alignment: BitAlignment | None = None
        if container == "uint16":
            endianness = cast(Endianness, self.byte_order.currentData())
        if container is not None and self.bit_depth.value() < container_bit_count(container):
            alignment = cast(BitAlignment, self.bit_alignment.currentData())

        return RawProfile(
            name=self._profile_name,
            width=self.width_box.value(),
            height=self.height_box.value(),
            stride_bytes=self.stride.value(),
            offset_bytes=self.offset.value(),
            storage_format=storage_format,
            container_dtype=container,
            endianness=endianness,
            bit_depth=self.bit_depth.value(),
            bit_alignment=alignment,
            channel_layout=layout,
            bayer_pattern=(self.bayer_pattern.currentText() if layout == "BAYER" else None),
            black_level=black_level,
            white_level=self.white.value(),
        )

    def set_profile(self, profile: RawProfile, *, stride_is_auto: bool = False) -> None:
        self._profile_name = profile.name
        self.width_box.setValue(profile.width)
        self.height_box.setValue(profile.height)
        self._set_stride_value(profile.stride_bytes)
        self._stride_is_auto = stride_is_auto
        self.offset.setValue(profile.offset_bytes)

        self._set_combo_data(self.storage_format, profile.storage_format)
        if profile.storage_format == "unpacked":
            if profile.container_dtype is not None:
                self._unpacked_container = profile.container_dtype
                self._set_combo_data(self.container, profile.container_dtype)
            if profile.endianness is not None:
                self._unpacked_endianness = profile.endianness
                self._set_combo_data(self.byte_order, profile.endianness)
            if profile.bit_alignment is not None:
                self._unpacked_alignment = profile.bit_alignment
                self._set_combo_data(self.bit_alignment, profile.bit_alignment)
            self._unpacked_bit_depth = profile.bit_depth
        self.bit_depth.setValue(profile.bit_depth)
        self._storage_format_changed()
        if self._stride_is_auto:
            self._sync_auto_stride()

        self.layout_kind.setCurrentText(profile.channel_layout)
        if profile.bayer_pattern is not None:
            self.bayer_pattern.setCurrentText(profile.bayer_pattern)
        if isinstance(profile.black_level, tuple):
            levels = profile.black_level
            gray_level = profile.black_level[0]
        else:
            levels = (profile.black_level,) * 4
            gray_level = profile.black_level
        self.black_gray.setValue(gray_level)
        for control, value in zip(
            (self.black_r, self.black_gr, self.black_gb, self.black_b),
            levels,
            strict=True,
        ):
            control.setValue(value)
        self.white.setValue(profile.white_level)
        self._update_legacy_black_text()
        self._update_diagnostics()

    def _set_stride_value(self, value: int) -> None:
        self._updating_stride = True
        try:
            self.stride.setValue(value)
        finally:
            self._updating_stride = False

    def _sync_auto_stride(self) -> None:
        if not self._stride_is_auto:
            return
        try:
            minimum_stride = self.minimum_stride_bytes()
        except ValueError:
            return
        self._set_stride_value(minimum_stride)

    def _width_changed(self, _value: int) -> None:
        self._sync_auto_stride()
        self._update_diagnostics()

    def _stride_changed(self, _value: int) -> None:
        if not self._updating_stride:
            self._stride_is_auto = False
        self._update_diagnostics()

    def _storage_format_changed(self, _index: int | None = None) -> None:
        storage_format = self.storage_format_key
        spec = storage_format_spec(storage_format)
        packed = spec.is_packed

        self._set_form_row_visible(self.container, not packed)
        self.bit_depth.setEnabled(not packed)
        if packed:
            self.bit_depth.setValue(int(spec.fixed_bit_depth or 1))
            self._set_form_row_visible(self.byte_order, False)
            self._set_form_row_visible(self.bit_alignment, False)
        else:
            self._set_combo_data(self.container, self._unpacked_container)
            self.bit_depth.setValue(self._unpacked_bit_depth)
            self._update_unpacked_control_states()
        self._bit_depth_changed(self.bit_depth.value())
        self._sync_auto_stride()
        self._update_diagnostics()
        QTimer.singleShot(0, self._resize_dialog_to_content)

    def _container_changed(self, _index: int | None = None) -> None:
        if self.storage_format_key != "unpacked":
            return
        container = self.container_dtype
        if container is None:
            return
        self._unpacked_container = container
        maximum_depth = container_bit_count(container)
        self.bit_depth.setMaximum(maximum_depth)
        if self.bit_depth.value() > maximum_depth:
            self.bit_depth.setValue(maximum_depth)
        self._update_unpacked_control_states()
        self._sync_auto_stride()
        self._update_diagnostics()

    def _byte_order_changed(self, _index: int | None = None) -> None:
        value = self.byte_order.currentData()
        if self.storage_format_key == "unpacked" and value in ("little", "big"):
            self._unpacked_endianness = cast(Endianness, value)
        self._update_diagnostics()

    def _bit_alignment_changed(self, _index: int | None = None) -> None:
        value = self.bit_alignment.currentData()
        if self.storage_format_key == "unpacked" and value in ("lsb", "msb"):
            self._unpacked_alignment = cast(BitAlignment, value)
        self._update_diagnostics()

    def _update_unpacked_control_states(self) -> None:
        container = self.container_dtype or self._unpacked_container
        container_bits = container_bit_count(container)
        self.bit_depth.setMaximum(container_bits)
        if self.bit_depth.value() > container_bits:
            self.bit_depth.setValue(container_bits)

        byte_order_visible = container == "uint16"
        self._set_form_row_visible(self.byte_order, byte_order_visible)
        if byte_order_visible:
            self._set_combo_data(self.byte_order, self._unpacked_endianness)

        alignment_visible = self.bit_depth.value() < container_bits
        self._set_form_row_visible(self.bit_alignment, alignment_visible)
        if alignment_visible:
            self._set_combo_data(self.bit_alignment, self._unpacked_alignment)
        QTimer.singleShot(0, self._resize_dialog_to_content)

    def _bit_depth_changed(self, depth: int) -> None:
        if self.storage_format_key == "unpacked":
            self._unpacked_bit_depth = depth
            self._update_unpacked_control_states()
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
        self.black_level_stack.setCurrentIndex(1 if is_bayer else 0)
        self._fit_black_level_stack_to_current_page()
        self._update_legacy_black_text()

    def _fit_black_level_stack_to_current_page(self) -> None:
        current_page = self.black_level_stack.currentWidget()
        if current_page is None:
            return
        current_page.adjustSize()
        self.black_level_stack.setFixedHeight(current_page.sizeHint().height())
        self.black_level_stack.updateGeometry()
        QTimer.singleShot(0, self._resize_dialog_to_content)

    def _resize_dialog_to_content(self) -> None:
        if self._last_auto_fit_size is not None and self.size() != self._last_auto_fit_size:
            return
        body = self.body_scroll.widget()
        if body is not None:
            body.adjustSize()
            body.updateGeometry()
        self.body_scroll.updateGeometry()
        dialog_layout = self.layout()
        if dialog_layout is not None:
            dialog_layout.invalidate()
            dialog_layout.activate()
        target_height = body.sizeHint().height() + self.footer.sizeHint().height()
        if self.height() != target_height:
            self.resize(self.width(), target_height)
        self._last_auto_fit_size = self.size()

    def _set_form_row_visible(self, field: QWidget, visible: bool) -> None:
        label = self.form.labelForField(field)
        if label is not None:
            label.setVisible(visible)
        field.setVisible(visible)

    def _update_legacy_black_text(self, _value: object = None) -> None:
        values: tuple[int, ...]
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

    def _set_status(
        self,
        state: str,
        text: str,
        icon: QStyle.StandardPixmap,
    ) -> None:
        self._file_size_state = state
        pixmap = self.style().standardIcon(icon).pixmap(18, 18)
        self.file_status_icon.setPixmap(pixmap)
        self.file_status.setText(text)

    def _format_dimension_error(self) -> str | None:
        spec = storage_format_spec(self.storage_format_key)
        if not spec.is_packed:
            return None
        if self.width_box.value() % spec.width_alignment:
            return f"Width must align to {spec.width_alignment}-pixel " f"{spec.label} groups."
        if self.height_box.value() % 2:
            return f"Height must be even for {spec.label}."
        return None

    def _update_diagnostics(self, _value: object = None) -> None:
        dimension_error = self._format_dimension_error()
        try:
            minimum_stride = self.minimum_stride_bytes()
        except ValueError:
            minimum_stride = 0
        if minimum_stride:
            self.minimum_stride_value.setText(
                f"Minimum stride: {self._format_bytes(minimum_stride)}"
            )
        else:
            self.minimum_stride_value.setText("Minimum stride: unavailable")

        stride_valid = minimum_stride > 0 and self.stride.value() >= minimum_stride
        stride_aligned = True
        container = self.container_dtype
        if self.storage_format_key == "unpacked" and container is not None:
            stride_aligned = self.stride.value() % container_byte_count(container) == 0

        expected = 0
        if dimension_error is None and minimum_stride:
            expected = self.expected_file_size()
            self.expected_file_size_value.setText(self._format_bytes(expected))
        else:
            self.expected_file_size_value.setText("Unavailable")

        if dimension_error is not None:
            self.actual_file_size_value.setText(
                "—" if self._source_path is None else self.actual_file_size_value.text()
            )
            self._set_status(
                "error",
                dimension_error,
                QStyle.StandardPixmap.SP_MessageBoxCritical,
            )
            self.ok_button.setEnabled(False)
            return

        if self._source_path is None:
            self.actual_file_size_value.setText("—")
            if not stride_valid:
                self._set_status(
                    "error",
                    f"Stride is {minimum_stride - self.stride.value():,} bytes too small.",
                    QStyle.StandardPixmap.SP_MessageBoxCritical,
                )
            elif not stride_aligned:
                item_size = self.sample_size_bytes()
                self._set_status(
                    "error",
                    f"Stride must align to {item_size}-byte containers.",
                    QStyle.StandardPixmap.SP_MessageBoxCritical,
                )
            else:
                self._set_status(
                    "unavailable",
                    "Select a RAW file to check size.",
                    QStyle.StandardPixmap.SP_MessageBoxInformation,
                )
            self.ok_button.setEnabled(stride_valid and stride_aligned)
            return

        if self._actual_file_size is None:
            self.actual_file_size_value.setText("Unavailable")
            self._set_status(
                "error",
                "File size is unavailable.",
                QStyle.StandardPixmap.SP_MessageBoxCritical,
            )
            self.ok_button.setEnabled(False)
            return

        actual = self._actual_file_size
        self.actual_file_size_value.setText(self._format_bytes(actual))
        if not stride_valid:
            self._set_status(
                "error",
                f"Stride is {minimum_stride - self.stride.value():,} bytes too small.",
                QStyle.StandardPixmap.SP_MessageBoxCritical,
            )
            self.ok_button.setEnabled(False)
        elif not stride_aligned:
            item_size = self.sample_size_bytes()
            self._set_status(
                "error",
                f"Stride must align to {item_size}-byte containers.",
                QStyle.StandardPixmap.SP_MessageBoxCritical,
            )
            self.ok_button.setEnabled(False)
        elif actual < expected:
            self._set_status(
                "error",
                f"File is {expected - actual:,} bytes too small.",
                QStyle.StandardPixmap.SP_MessageBoxCritical,
            )
            self.ok_button.setEnabled(False)
        elif actual > expected:
            self._set_status(
                "warning",
                f"{actual - expected:,} trailing bytes will be ignored.",
                QStyle.StandardPixmap.SP_MessageBoxWarning,
            )
            self.ok_button.setEnabled(True)
        else:
            self._set_status(
                "match",
                "File size matches.",
                QStyle.StandardPixmap.SP_DialogApplyButton,
            )
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
            QMessageBox.warning(
                self,
                "Invalid RAW source",
                self.file_status.text(),
            )
            return
        self.accept()

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load RAW profile",
            "",
            "JSON (*.json)",
        )
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
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save RAW profile",
            "",
            "JSON (*.json)",
        )
        if path:
            profile.save_json(Path(path))