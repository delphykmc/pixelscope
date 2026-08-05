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


def test_raw_dialog_separates_storage_format_container_and_bit_depth(
    qtbot: object,
) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.width_box.setValue(12)

    assert _form_label(dialog, dialog.storage_format) == "Storage format"
    assert _form_label(dialog, dialog.container) == "Container"
    assert _form_label(dialog, dialog.bit_depth) == "Bit depth"
    assert _form_label(dialog, dialog.byte_order) == "Byte order"
    assert _form_label(dialog, dialog.bit_alignment) == "Bit alignment"
    assert dialog.storage_format.currentData() == "unpacked"
    assert dialog.container.currentData() == "uint16"
    assert dialog.minimum_stride_bytes() == 24
    assert dialog.minimum_stride_value.text() == "Minimum stride: 24 bytes"

    dialog.container.setCurrentIndex(dialog.container.findData("uint8"))
    assert dialog.bit_depth.maximum() == 8
    assert not dialog.byte_order.isEnabled()
    assert dialog.byte_order.currentData() is None
    assert dialog.minimum_stride_bytes() == 12

    dialog.container.setCurrentIndex(dialog.container.findData("uint16"))
    dialog.bit_depth.setValue(10)
    assert dialog.byte_order.isEnabled()
    assert dialog.bit_alignment.isEnabled()
    assert dialog.bit_alignment.currentData() == "lsb"
    dialog.bit_depth.setValue(16)
    assert not dialog.bit_alignment.isEnabled()
    assert dialog.bit_alignment.currentData() is None


def test_raw_dialog_packed_formats_define_dependent_fields(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.width_box.setValue(1920)
    dialog.height_box.setValue(1080)

    cases = (
        ("mipi_raw10", 10, 2400),
        ("mipi_raw12", 12, 2880),
        ("mipi_raw14", 14, 3360),
    )
    for storage_format, bit_depth, minimum_stride in cases:
        dialog.storage_format.setCurrentIndex(dialog.storage_format.findData(storage_format))
        assert dialog.bit_depth.value() == bit_depth
        assert not dialog.bit_depth.isEnabled()
        assert dialog.container.currentData() is None
        assert not dialog.container.isEnabled()
        assert dialog.byte_order.currentData() is None
        assert not dialog.byte_order.isEnabled()
        assert dialog.bit_alignment.currentData() is None
        assert not dialog.bit_alignment.isEnabled()
        assert dialog.minimum_stride_bytes() == minimum_stride

    dialog.storage_format.setCurrentIndex(dialog.storage_format.findData("unpacked"))
    assert dialog.container.isEnabled()
    assert dialog.bit_depth.isEnabled()
    assert dialog.container.currentData() == "uint16"


def test_raw_dialog_rejects_invalid_mipi_dimensions(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.storage_format.setCurrentIndex(dialog.storage_format.findData("mipi_raw10"))
    dialog.width_box.setValue(1918)
    assert dialog.file_size_state == "error"
    assert dialog.file_status.text() == ("Width must align to 4-pixel MIPI RAW10 groups.")
    assert not dialog.ok_button.isEnabled()

    dialog.width_box.setValue(1920)
    dialog.height_box.setValue(1079)
    assert dialog.file_status.text() == "Height must be even for MIPI RAW10."


def test_raw_dialog_compares_expected_and_actual_packed_file_size(
    qtbot: object,
    tmp_path: Path,
) -> None:
    raw_path = tmp_path / "frame.raw"
    raw_path.write_bytes(bytes(10))
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.set_profile(
        RawProfile(
            name="frame",
            width=4,
            height=2,
            stride_bytes=5,
            storage_format="mipi_raw10",
            container_dtype=None,
            endianness=None,
            bit_depth=10,
            bit_alignment=None,
            channel_layout="BAYER",
            bayer_pattern="RGGB",
            black_level=(0, 0, 0, 0),
            white_level=1023,
        )
    )
    dialog.set_source_path(raw_path)

    assert dialog.expected_file_size() == 10
    assert dialog.expected_file_size_value.text() == "10 bytes"
    assert dialog.actual_file_size_value.text() == "10 bytes"
    assert dialog.file_size_state == "match"
    assert dialog.ok_button.isEnabled()

    dialog.stride.setValue(6)
    assert dialog.expected_file_size() == 11
    assert dialog.file_size_state == "error"
    assert not dialog.ok_button.isEnabled()


def test_raw_dialog_round_trips_alignment_and_bayer_levels(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    profile = RawProfile(
        name="camera",
        width=8,
        height=6,
        stride_bytes=20,
        offset_bytes=16,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="big",
        bit_depth=12,
        bit_alignment="msb",
        channel_layout="BAYER",
        bayer_pattern="GBRG",
        black_level=(64, 65, 66, 67),
        white_level=4095,
    )
    dialog.set_profile(profile)

    assert dialog.storage_format.currentData() == "unpacked"
    assert dialog.container.currentData() == "uint16"
    assert dialog.byte_order.currentData() == "big"
    assert dialog.bit_alignment.currentData() == "msb"
    assert dialog.layout_kind.currentText() == "BAYER"
    assert [
        control.value()
        for control in (dialog.black_r, dialog.black_gr, dialog.black_gb, dialog.black_b)
    ] == [64, 65, 66, 67]
    assert dialog.profile() == profile


def test_raw_dialog_gray_bayer_gray_restores_compact_height(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: dialog.height() == dialog.sizeHint().height(),
        timeout=1000,
    )

    gray_stack_height = dialog.black_level_stack.height()
    gray_dialog_height = dialog.height()
    dialog.layout_kind.setCurrentText("BAYER")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: dialog.height() > gray_dialog_height,
        timeout=1000,
    )
    bayer_dialog_height = dialog.height()
    assert dialog.black_level_stack.height() > gray_stack_height

    dialog.layout_kind.setCurrentText("GRAY")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: dialog.height() < bayer_dialog_height,
        timeout=1000,
    )
    assert dialog.black_level_stack.height() == gray_stack_height
    assert dialog.height() == gray_dialog_height


def test_raw_dialog_uses_fixed_edges_with_an_adaptive_middle_gap(
    qtbot: object,
) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.width() == RAW_DIALOG_WIDTH == 280
    assert FORM_LABEL_WIDTH == 100
    assert FIELD_WIDTH == 120
    assert dialog.form.columnStretch(0) == 0
    assert dialog.form.columnStretch(1) == 1
    assert dialog.form.columnStretch(2) == 0

    fields = (
        dialog.width_box,
        dialog.height_box,
        dialog.stride,
        dialog.offset,
        dialog.storage_format,
        dialog.container,
        dialog.bit_depth,
        dialog.byte_order,
        dialog.bit_alignment,
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

    assert dialog.load_button.sizePolicy().horizontalPolicy() == (QSizePolicy.Policy.Expanding)
    assert dialog.save_button.sizePolicy().horizontalPolicy() == (QSizePolicy.Policy.Expanding)
    assert dialog.ok_button.width() == DIALOG_BUTTON_WIDTH
    assert dialog.cancel_button.width() == DIALOG_BUTTON_WIDTH
    assert dialog.dialog_actions_layout.itemAt(0).spacerItem() is not None
    assert dialog.expected_file_size_value.alignment() & Qt.AlignmentFlag.AlignLeft


def test_raw_dialog_dont_show_option_is_opt_in(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.dont_show_json_profiles.isHidden()
    assert not dialog.dont_show_json_profiles_requested()
    dialog.set_json_confirmation_option_visible(True)
    assert not dialog.dont_show_json_profiles.isHidden()
    dialog.dont_show_json_profiles.setChecked(True)
    assert dialog.dont_show_json_profiles_requested()
