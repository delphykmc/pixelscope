from __future__ import annotations

from pathlib import Path

RAW_DIALOG = Path("src/pixelscope/ui/raw_open_dialog.py")
RAW_DIALOG_TEST = Path("tests/ui/test_p1c_raw_dialog.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_raw_dialog(text: str) -> str:
    if 'self.setFixedWidth(440)' in text and 'QPushButton("Set this stride")' in text:
        print("RAW dialog compact layout already applied")
        return text

    text = replace_once(
        text,
        '        self.setMinimumWidth(520)\n',
        '        self.setFixedWidth(440)\n',
        "dialog width",
    )
    text = replace_once(
        text,
        '''        self.dtype = QComboBox()
        self.dtype.addItems(["uint8", "uint16"])
        self.dtype.setCurrentText("uint16")
        self.endian = QComboBox()
        self.endian.addItems(["little", "big"])
''',
        '''        self.dtype = QComboBox()
        self.dtype.addItems(["uint8", "uint16"])
        self.dtype.setCurrentText("uint16")
        self.dtype.setFixedWidth(112)
        self.endian = QComboBox()
        self.endian.addItems(["little", "big"])
        self.endian.setFixedWidth(112)
''',
        "data type controls",
    )
    text = replace_once(
        text,
        '''        self.packing = QComboBox()
        self.packing.addItems(["unpacked_u8", "unpacked_u16"])
        self.packing.setCurrentText("unpacked_u16")
        self.layout_kind = QComboBox()
        self.layout_kind.addItems(["GRAY", "BAYER"])
        self.bayer_pattern = QComboBox()
        self.bayer_pattern.addItems(["RGGB", "GRBG", "GBRG", "BGGR"])
''',
        '''        self.packing = QComboBox()
        self.packing.addItems(["unpacked_u8", "unpacked_u16"])
        self.packing.setCurrentText("unpacked_u16")
        self.packing.setFixedWidth(148)
        self.layout_kind = QComboBox()
        self.layout_kind.addItems(["GRAY", "BAYER"])
        self.layout_kind.setFixedWidth(112)
        self.bayer_pattern = QComboBox()
        self.bayer_pattern.addItems(["RGGB", "GRBG", "GBRG", "BGGR"])
        self.bayer_pattern.setFixedWidth(112)
''',
        "packing and pixel layout controls",
    )
    text = replace_once(
        text,
        '''        self.set_minimum_stride_button = QPushButton("Set stride to minimum")
        self.set_minimum_stride_button.setAutoDefault(False)
        self.set_minimum_stride_button.setDefault(False)
''',
        '''        self.minimum_stride_value.setFixedWidth(96)
        self.set_minimum_stride_button = QPushButton("Set this stride")
        self.set_minimum_stride_button.setFixedWidth(112)
        self.set_minimum_stride_button.setAutoDefault(False)
        self.set_minimum_stride_button.setDefault(False)
''',
        "minimum stride helper",
    )
    text = replace_once(
        text,
        '''        layout_form = QFormLayout()
        layout_form.addRow("Width", self.width_box)
''',
        '''        layout_form = QFormLayout()
        layout_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint
        )
        layout_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout_form.addRow("Width", self.width_box)
''',
        "compact form policy",
    )
    old_file_size = '''        self.file_status_icon = QLabel()
        self.file_status_icon.setFixedSize(24, 24)
        self.file_status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_status = QLabel()
        self.file_status.setWordWrap(True)

        file_size_layout = QGridLayout()
        file_size_layout.setContentsMargins(10, 8, 10, 8)
        file_size_layout.setColumnStretch(1, 1)
        file_size_layout.addWidget(QLabel("Expected file size"), 0, 0)
        file_size_layout.addWidget(self.expected_file_size_value, 0, 1)
        file_size_layout.addWidget(QLabel("Actual file size"), 1, 0)
        file_size_layout.addWidget(self.actual_file_size_value, 1, 1)
        file_size_layout.addWidget(self.file_status_icon, 2, 0)
        file_size_layout.addWidget(self.file_status, 2, 1)
        file_size_frame = QFrame()
        file_size_frame.setFrameShape(QFrame.Shape.StyledPanel)
        file_size_frame.setLayout(file_size_layout)

        data_layout_group = QGroupBox("Data layout")
        data_layout = QVBoxLayout(data_layout_group)
        data_layout.addLayout(layout_form)
        data_layout.addSpacing(6)
        data_layout.addWidget(QLabel("File size check"))
        data_layout.addWidget(file_size_frame)
'''
    new_file_size = '''        self.file_status_icon = QLabel()
        self.file_status_icon.setFixedSize(20, 20)
        self.file_status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_status = QLabel()
        self.file_status.setWordWrap(True)
        self.file_status.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.expected_file_size_label = QLabel("Expected")
        self.actual_file_size_label = QLabel("Actual")
        file_size_values = QGridLayout()
        file_size_values.setContentsMargins(0, 0, 0, 0)
        file_size_values.setHorizontalSpacing(12)
        file_size_values.setVerticalSpacing(4)
        file_size_values.setColumnStretch(1, 1)
        file_size_values.addWidget(self.expected_file_size_label, 0, 0)
        file_size_values.addWidget(self.expected_file_size_value, 0, 1)
        file_size_values.addWidget(self.actual_file_size_label, 1, 0)
        file_size_values.addWidget(self.actual_file_size_value, 1, 1)

        self.file_status_row = QHBoxLayout()
        self.file_status_row.setContentsMargins(0, 0, 0, 0)
        self.file_status_row.setSpacing(6)
        self.file_status_row.addWidget(self.file_status_icon)
        self.file_status_row.addWidget(self.file_status, 1)

        file_size_group = QGroupBox("File size")
        file_size_group_layout = QVBoxLayout(file_size_group)
        file_size_group_layout.setContentsMargins(10, 8, 10, 8)
        file_size_group_layout.setSpacing(6)
        file_size_group_layout.addLayout(file_size_values)
        file_size_group_layout.addLayout(self.file_status_row)

        data_layout_group = QGroupBox("Data layout")
        data_layout = QVBoxLayout(data_layout_group)
        data_layout.addLayout(layout_form)
'''
    text = replace_once(text, old_file_size, new_file_size, "file size presentation")
    text = replace_once(
        text,
        '''        layout = QVBoxLayout(self)
        layout.addWidget(data_layout_group)
        layout.addWidget(signal_levels_group)
''',
        '''        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(data_layout_group)
        layout.addWidget(file_size_group)
        layout.addWidget(signal_levels_group)
''',
        "top-level compact layout",
    )
    text = replace_once(
        text,
        '''        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        return box
''',
        '''        box = QSpinBox()
        box.setRange(minimum, maximum)
        box.setValue(value)
        box.setFixedWidth(112)
        return box
''',
        "spin box width",
    )
    text = replace_once(
        text,
        '''        self.minimum_stride_value.setText(
            f"{self._format_bytes(minimum_stride)} for current width and data type"
        )
''',
        '''        self.minimum_stride_value.setText(self._format_bytes(minimum_stride))
''',
        "minimum stride text",
    )
    text = replace_once(
        text,
        '                "Select a RAW file to validate its size.",\n',
        '                "Select a RAW file to check size.",\n',
        "unavailable size message",
    )
    text = replace_once(
        text,
        '                "The RAW file cannot be accessed.",\n',
        '                "File size is unavailable.",\n',
        "file access message",
    )
    text = replace_once(
        text,
        '''                f"Stride is {minimum_stride - self.stride.value():,} bytes smaller "
                "than one image row.",
''',
        '''                f"Stride is {minimum_stride - self.stride.value():,} bytes too small.",
''',
        "stride error message",
    )
    text = replace_once(
        text,
        '                f"Stride must align to the {item_size}-byte sample size.",\n',
        '                f"Stride must align to {item_size}-byte samples.",\n',
        "stride alignment message",
    )
    text = replace_once(
        text,
        '''                f"The file is {expected - actual:,} bytes smaller than the current "
                "layout requires.",
''',
        '''                f"File is {expected - actual:,} bytes too small.",
''',
        "file too small message",
    )
    text = replace_once(
        text,
        '''                f"The current layout uses {self._format_bytes(expected)}; "
                f"{actual - expected:,} trailing bytes will be ignored.",
''',
        '''                f"{actual - expected:,} trailing bytes will be ignored.",
''',
        "trailing data message",
    )
    text = replace_once(
        text,
        '                "File size matches the current data layout.",\n',
        '                "File size matches.",\n',
        "matching size message",
    )
    return text


def patch_test(text: str) -> str:
    text = replace_once(
        text,
        '''    assert "26 bytes" in dialog.minimum_stride_value.text()
    assert "current width and data type" in dialog.minimum_stride_value.text()
    assert dialog.set_minimum_stride_button.text() == "Set stride to minimum"
''',
        '''    assert dialog.minimum_stride_value.text() == "26 bytes"
    assert dialog.set_minimum_stride_button.text() == "Set this stride"
''',
        "minimum stride assertions",
    )
    text = replace_once(
        text,
        '    assert "8 bytes smaller" in dialog.file_status.text()\n',
        '    assert "8 bytes too small" in dialog.file_status.text()\n',
        "too-small message assertion",
    )
    text = replace_once(
        text,
        '''    assert dialog.file_status_icon.pixmap() is not None
    assert dialog.ok_button.isEnabled()
''',
        '''    assert dialog.file_status_icon.pixmap() is not None
    assert dialog.expected_file_size_label.text() == "Expected"
    assert dialog.actual_file_size_label.text() == "Actual"
    assert dialog.file_status_row.indexOf(dialog.file_status_icon) == 0
    assert dialog.file_status_row.indexOf(dialog.file_status) == 1
    assert dialog.width() == 440
    assert dialog.ok_button.isEnabled()
''',
        "compact file size assertions",
    )
    return text


def update(path: Path, patcher: object) -> None:
    original = path.read_text(encoding="utf-8")
    updated = patcher(original)  # type: ignore[operator]
    if updated == original:
        print(f"No changes required: {path}")
        return
    path.write_text(updated, encoding="utf-8")
    print(f"Updated: {path}")


def main() -> int:
    update(RAW_DIALOG, patch_raw_dialog)
    update(RAW_DIALOG_TEST, patch_test)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
