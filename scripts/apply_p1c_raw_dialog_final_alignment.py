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
    if (
        'self.setFixedWidth(380)' in text
        and 'self.json_actions_layout = QHBoxLayout()' in text
        and 'self.dialog_actions_layout = QHBoxLayout()' in text
    ):
        print("RAW dialog final alignment already applied")
        return text

    text = replace_once(
        text,
        '        self.setFixedWidth(440)\n',
        '        self.setFixedWidth(380)\n',
        "dialog width",
    )
    text = replace_once(
        text,
        '''        for value_label in (
            self.expected_file_size_value,
            self.actual_file_size_value,
        ):
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
''',
        '''        for value_label in (
            self.expected_file_size_value,
            self.actual_file_size_value,
        ):
            value_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            value_label.setFixedWidth(132)
''',
        "file size value alignment",
    )
    text = replace_once(
        text,
        '''        self.expected_file_size_label = QLabel("Expected")
        self.actual_file_size_label = QLabel("Actual")
''',
        '''        self.expected_file_size_label = QLabel("Expected")
        self.actual_file_size_label = QLabel("Actual")
        self.expected_file_size_label.setFixedWidth(82)
        self.actual_file_size_label.setFixedWidth(82)
''',
        "file size label widths",
    )
    text = replace_once(
        text,
        '''        self.load_button = QPushButton("Load JSON…")
        self.save_button = QPushButton("Save JSON…")
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
''',
        '''        self.load_button = QPushButton("Load JSON…")
        self.save_button = QPushButton("Save JSON…")
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Cancel")
        self.load_button.setFixedWidth(112)
        self.save_button.setFixedWidth(112)
        self.ok_button.setFixedWidth(92)
        self.cancel_button.setFixedWidth(92)
''',
        "button widths",
    )
    text = replace_once(
        text,
        '''            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
''',
        '''            button.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Fixed,
            )
''',
        "fixed button size policy",
    )
    old_buttons = '''        self.button_grid = QGridLayout()
        self.button_grid.setContentsMargins(0, 0, 0, 0)
        self.button_grid.setHorizontalSpacing(8)
        self.button_grid.setVerticalSpacing(8)
        self.button_grid.setColumnStretch(0, 1)
        self.button_grid.setColumnStretch(1, 1)
        self.button_grid.addWidget(self.load_button, 0, 0)
        self.button_grid.addWidget(self.save_button, 0, 1)
        self.button_grid.addWidget(self.dont_show_json_profiles, 1, 0, 1, 2)
        self.button_grid.addWidget(separator, 2, 0, 1, 2)
        self.button_grid.addWidget(self.ok_button, 3, 0)
        self.button_grid.addWidget(self.cancel_button, 3, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(data_layout_group)
        layout.addWidget(file_size_group)
        layout.addWidget(signal_levels_group)
        layout.addLayout(self.button_grid)
'''
    new_buttons = '''        self.json_actions_layout = QHBoxLayout()
        self.json_actions_layout.setContentsMargins(92, 0, 0, 0)
        self.json_actions_layout.setSpacing(8)
        self.json_actions_layout.addWidget(self.load_button)
        self.json_actions_layout.addWidget(self.save_button)
        self.json_actions_layout.addStretch(1)

        self.dont_show_layout = QHBoxLayout()
        self.dont_show_layout.setContentsMargins(92, 0, 0, 0)
        self.dont_show_layout.addWidget(self.dont_show_json_profiles)
        self.dont_show_layout.addStretch(1)

        self.dialog_actions_layout = QHBoxLayout()
        self.dialog_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.dialog_actions_layout.setSpacing(8)
        self.dialog_actions_layout.addStretch(1)
        self.dialog_actions_layout.addWidget(self.ok_button)
        self.dialog_actions_layout.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(data_layout_group)
        layout.addWidget(file_size_group)
        layout.addWidget(signal_levels_group)
        layout.addSpacing(2)
        layout.addLayout(self.json_actions_layout)
        layout.addLayout(self.dont_show_layout)
        layout.addWidget(separator)
        layout.addLayout(self.dialog_actions_layout)
'''
    text = replace_once(text, old_buttons, new_buttons, "bottom action layout")

    text = replace_once(
        text,
        '''        layout_form.addRow("Pixel layout", self.layout_kind)
        layout_form.addRow("Bayer pattern", self.bayer_pattern)
        self.form = layout_form
''',
        '''        layout_form.addRow("Pixel layout", self.layout_kind)
        layout_form.addRow("Bayer pattern", self.bayer_pattern)
        for field in (
            self.width_box,
            self.height_box,
            self.stride,
            stride_helper,
            self.offset,
            self.dtype,
            self.endian,
            self.bit_depth,
            self.packing,
            self.layout_kind,
            self.bayer_pattern,
        ):
            label = layout_form.labelForField(field)
            if label is not None:
                label.setFixedWidth(82)
        self.form = layout_form
''',
        "data layout label widths",
    )
    text = replace_once(
        text,
        '''        gray_levels_form.addRow("Black level", self.black_gray)
''',
        '''        gray_levels_form.addRow("Black level", self.black_gray)
        gray_label = gray_levels_form.labelForField(self.black_gray)
        if gray_label is not None:
            gray_label.setFixedWidth(82)
''',
        "gray signal label width",
    )
    text = replace_once(
        text,
        '''        bayer_levels_form.addRow("Black level R", self.black_r)
        bayer_levels_form.addRow("Black level Gr", self.black_gr)
        bayer_levels_form.addRow("Black level Gb", self.black_gb)
        bayer_levels_form.addRow("Black level B", self.black_b)
''',
        '''        bayer_levels_form.addRow("Black level R", self.black_r)
        bayer_levels_form.addRow("Black level Gr", self.black_gr)
        bayer_levels_form.addRow("Black level Gb", self.black_gb)
        bayer_levels_form.addRow("Black level B", self.black_b)
        for field in (self.black_r, self.black_gr, self.black_gb, self.black_b):
            label = bayer_levels_form.labelForField(field)
            if label is not None:
                label.setFixedWidth(82)
''',
        "Bayer signal label widths",
    )
    text = replace_once(
        text,
        '''        white_level_form = QFormLayout()
        white_level_form.addRow("White level", self.white)
''',
        '''        white_level_form = QFormLayout()
        white_level_form.addRow("White level", self.white)
        white_label = white_level_form.labelForField(self.white)
        if white_label is not None:
            white_label.setFixedWidth(82)
''',
        "white signal label width",
    )
    return text


def patch_test(text: str) -> str:
    if "test_raw_dialog_uses_compact_standard_action_alignment" in text:
        return text
    return text + '''


def test_raw_dialog_uses_compact_standard_action_alignment(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.width() == 380
    assert dialog.load_button.width() == 112
    assert dialog.save_button.width() == 112
    assert dialog.ok_button.width() == 92
    assert dialog.cancel_button.width() == 92
    assert dialog.json_actions_layout.contentsMargins().left() == 92
    assert dialog.dont_show_layout.contentsMargins().left() == 92
    assert dialog.dialog_actions_layout.itemAt(0).spacerItem() is not None
    assert dialog.expected_file_size_value.alignment() & Qt.AlignmentFlag.AlignLeft
    assert dialog.actual_file_size_value.alignment() & Qt.AlignmentFlag.AlignLeft
'''


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
