from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy

from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.raw_open_dialog import (
    DIALOG_BUTTON_WIDTH,
    FIELD_WIDTH,
    FORM_LABEL_WIDTH,
    RAW_DIALOG_WIDTH,
    RawOpenDialog,
)


def _form_label(dialog: RawOpenDialog, field: object) -> str:
    label = dialog.form.labelForField(field)  # type: ignore[arg-type]
    assert label is not None
    return label.text()


def test_raw_dialog_links_packing_data_type_and_minimum_stride(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.width_box.setValue(13)

    assert dialog.dtype.currentText() == "uint16"
    assert dialog.packing.currentText() == "unpacked_u16"
    assert dialog.minimum_stride_bytes() == 26
    assert dialog.minimum_stride_value.text() == "Minimum stride: 26 bytes"
    assert dialog.minimum_stride_icon.pixmap() is not None

    stride_position = dialog.form.getItemPosition(
        dialog.form.indexOf(dialog.stride)
    )
    minimum_stride_position = dialog.form.getItemPosition(
        dialog.form.indexOf(dialog.minimum_stride_row)
    )
    assert minimum_stride_position[0] == stride_position[0] + 1
    assert minimum_stride_position[1:] == (0, 1, 3)

    assert not hasattr(dialog, "set_minimum_stride_button")
    assert dialog.endian.isEnabled()

    dialog.packing.setCurrentText("unpacked_u8")
    assert dialog.dtype.currentText() == "uint8"
    assert dialog.packing.currentText() == "unpacked_u8"
    assert dialog.minimum_stride_bytes() == 13
    assert dialog.minimum_stride_value.text() == "Minimum stride: 13 bytes"
    assert not dialog.endian.isEnabled()
    assert dialog.bit_depth.maximum() == 8

    dialog.dtype.setCurrentText("uint16")
    assert dialog.packing.currentText() == "unpacked_u16"
    assert dialog.endian.isEnabled()


def test_raw_dialog_compares_expected_and_actual_file_size_with_status_icons(
    qtbot: object,
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "frame.raw"
    raw_path.write_bytes(bytes(32))
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.set_profile(
        RawProfile(
            name="frame",
            width=4,
            height=4,
            dtype="uint16",
            stride_bytes=8,
            bit_depth=10,
            packing="unpacked_u16",
            channel_layout="GRAY",
            black_level=0,
            white_level=1023,
        )
    )
    dialog.set_source_path(raw_path)

    assert dialog.source_path == raw_path.resolve()
    assert not hasattr(dialog, "source_path_value")
    assert dialog.expected_file_size() == 32
    assert dialog.expected_file_size_value.text() == "32 bytes"
    assert dialog.actual_file_size_value.text() == "32 bytes"
    assert dialog.file_size_state == "match"
    assert dialog.file_status.text() == "File size matches."
    assert dialog.file_status_icon.pixmap() is not None
    assert dialog.ok_button.isEnabled()
    assert (
        dialog.file_size_form.labelForField(dialog.expected_file_size_value)
        is dialog.expected_file_size_label
    )
    assert (
        dialog.file_size_form.labelForField(dialog.actual_file_size_value)
        is dialog.actual_file_size_label
    )

    dialog.height_box.setValue(5)
    assert dialog.expected_file_size() == 40
    assert dialog.file_size_state == "error"
    assert dialog.file_status.text() == "File is 8 bytes too small."
    assert not dialog.ok_button.isEnabled()

    dialog.height_box.setValue(3)
    assert dialog.expected_file_size() == 24
    assert dialog.file_size_state == "warning"
    assert dialog.file_status.text() == "8 trailing bytes will be ignored."
    assert dialog.ok_button.isEnabled()


def test_raw_dialog_uses_explicit_bayer_black_level_controls(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: dialog.height() == dialog.sizeHint().height(),
        timeout=1000,
    )

    assert dialog.black_level_stack.currentIndex() == 0
    assert dialog.black_gray.isVisible()
    assert not dialog.black_r.isVisible()
    gray_stack_height = dialog.black_level_stack.height()
    gray_dialog_height = dialog.height()

    dialog.layout_kind.setCurrentText("BAYER")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: dialog.height() > gray_dialog_height,
        timeout=1000,
    )
    assert dialog.black_level_stack.currentIndex() == 1
    assert not dialog.black_gray.isVisible()
    assert all(
        control.isVisible()
        for control in (dialog.black_r, dialog.black_gr, dialog.black_gb, dialog.black_b)
    )
    bayer_stack_height = dialog.black_level_stack.height()
    bayer_dialog_height = dialog.height()
    assert bayer_stack_height > gray_stack_height

    dialog.black_r.setValue(10)
    dialog.black_gr.setValue(11)
    dialog.black_gb.setValue(12)
    dialog.black_b.setValue(13)
    assert dialog.profile().black_level == (10, 11, 12, 13)

    scalar_bayer_profile = RawProfile(
        name="scalar-bayer",
        width=4,
        height=4,
        dtype="uint16",
        stride_bytes=8,
        bit_depth=10,
        packing="unpacked_u16",
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=64,
        white_level=1023,
    )
    dialog.set_profile(scalar_bayer_profile)
    assert [
        control.value()
        for control in (dialog.black_r, dialog.black_gr, dialog.black_gb, dialog.black_b)
    ] == [64, 64, 64, 64]
    assert dialog.profile().black_level == (64, 64, 64, 64)

    dialog.layout_kind.setCurrentText("GRAY")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: dialog.height() < bayer_dialog_height,
        timeout=1000,
    )
    assert dialog.black_level_stack.height() == gray_stack_height
    assert dialog.height() == gray_dialog_height
    dialog.black_gray.setValue(21)
    assert dialog.profile().black_level == 21


def test_raw_dialog_uses_fixed_edges_with_an_adaptive_middle_gap(
    qtbot: object,
) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert _form_label(dialog, dialog.dtype) == "Data type"
    assert _form_label(dialog, dialog.endian) == "Byte order"
    assert _form_label(dialog, dialog.layout_kind) == "Pixel layout"

    assert dialog.width() == RAW_DIALOG_WIDTH == 280
    assert FORM_LABEL_WIDTH == 100
    assert FIELD_WIDTH == 120
    assert dialog.form.columnStretch(0) == 0
    assert dialog.form.columnStretch(1) == 1
    assert dialog.form.columnStretch(2) == 0

    width_label = dialog.form.labelForField(dialog.width_box)
    assert width_label is not None
    assert width_label.width() == FORM_LABEL_WIDTH

    width_label_position = dialog.form.getItemPosition(
        dialog.form.indexOf(width_label)
    )
    width_field_position = dialog.form.getItemPosition(
        dialog.form.indexOf(dialog.width_box)
    )
    assert width_label_position[0] == width_field_position[0]
    assert width_label_position[1:] == (0, 1, 1)
    assert width_field_position[1:] == (2, 1, 1)

    fields = (
        dialog.width_box,
        dialog.height_box,
        dialog.stride,
        dialog.offset,
        dialog.dtype,
        dialog.endian,
        dialog.bit_depth,
        dialog.packing,
        dialog.layout_kind,
        dialog.bayer_pattern,
        dialog.expected_file_size_value,
        dialog.actual_file_size_value,
        dialog.black_gray,
        dialog.black_r,
        dialog.black_gr,
        dialog.black_gb,
        dialog.black_b,
        dialog.white,
    )
    assert all(field.width() == FIELD_WIDTH for field in fields)

    dialog.setFixedWidth(320)
    assert all(field.width() == FIELD_WIDTH for field in fields)
    assert dialog.form.columnStretch(1) == 1

    assert dialog.load_button.sizePolicy().horizontalPolicy() == (
        QSizePolicy.Policy.Expanding
    )
    assert dialog.save_button.sizePolicy().horizontalPolicy() == (
        QSizePolicy.Policy.Expanding
    )
    assert dialog.json_actions_layout.indexOf(dialog.load_button) == 0
    assert dialog.json_actions_layout.indexOf(dialog.save_button) == 1

    assert dialog.ok_button.width() == DIALOG_BUTTON_WIDTH
    assert dialog.cancel_button.width() == DIALOG_BUTTON_WIDTH
    assert dialog.dialog_actions_layout.itemAt(0).spacerItem() is not None
    assert dialog.dialog_actions_layout.indexOf(dialog.ok_button) == 1
    assert dialog.dialog_actions_layout.indexOf(dialog.cancel_button) == 2

    assert dialog.expected_file_size_value.alignment() & Qt.AlignmentFlag.AlignLeft
    assert dialog.actual_file_size_value.alignment() & Qt.AlignmentFlag.AlignLeft


def test_raw_dialog_dont_show_option_is_opt_in(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.dont_show_json_profiles.text() == (
        "Don't show JSON profiles next time"
    )
    assert dialog.dont_show_json_profiles.isHidden()
    assert not dialog.dont_show_json_profiles_requested()
    dialog.set_json_confirmation_option_visible(True)
    assert not dialog.dont_show_json_profiles.isHidden()
    assert not dialog.dont_show_json_profiles_requested()
    dialog.dont_show_json_profiles.setChecked(True)
    assert dialog.dont_show_json_profiles_requested()
