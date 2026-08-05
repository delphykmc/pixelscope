from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.raw_open_dialog import RawOpenDialog


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
    assert dialog.minimum_stride_value.text() == "26 bytes"
    assert dialog.set_minimum_stride_button.text() == "Set this stride"
    assert not dialog.set_minimum_stride_button.isCheckable()
    assert dialog.endian.isEnabled()

    dialog.packing.setCurrentText("unpacked_u8")
    assert dialog.dtype.currentText() == "uint8"
    assert dialog.packing.currentText() == "unpacked_u8"
    assert dialog.minimum_stride_bytes() == 13
    assert not dialog.endian.isEnabled()
    assert dialog.bit_depth.maximum() == 8

    dialog.dtype.setCurrentText("uint16")
    assert dialog.packing.currentText() == "unpacked_u16"
    assert dialog.endian.isEnabled()
    dialog.stride.setValue(99)
    dialog.set_minimum_stride_button.click()
    assert dialog.stride.value() == 26


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
    assert "matches" in dialog.file_status.text()
    assert dialog.file_status_icon.pixmap() is not None
    assert dialog.expected_file_size_label.text() == "Expected"
    assert dialog.actual_file_size_label.text() == "Actual"
    assert dialog.file_status_row.indexOf(dialog.file_status_icon) == 0
    assert dialog.file_status_row.indexOf(dialog.file_status) == 1
    assert dialog.ok_button.isEnabled()

    dialog.height_box.setValue(5)
    assert dialog.expected_file_size() == 40
    assert dialog.file_size_state == "error"
    assert "8 bytes too small" in dialog.file_status.text()
    assert not dialog.ok_button.isEnabled()

    dialog.height_box.setValue(3)
    assert dialog.expected_file_size() == 24
    assert dialog.file_size_state == "warning"
    assert "8 trailing bytes" in dialog.file_status.text()
    assert dialog.ok_button.isEnabled()


def test_raw_dialog_uses_explicit_bayer_black_level_controls(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()

    assert dialog.black_level_stack.currentIndex() == 0
    assert dialog.black_gray.isVisible()
    assert not dialog.black_r.isVisible()

    dialog.layout_kind.setCurrentText("BAYER")
    assert dialog.black_level_stack.currentIndex() == 1
    assert not dialog.black_gray.isVisible()
    assert all(
        control.isVisible()
        for control in (dialog.black_r, dialog.black_gr, dialog.black_gb, dialog.black_b)
    )
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
    dialog.black_gray.setValue(21)
    assert dialog.profile().black_level == 21


def test_raw_dialog_renames_fields_and_uses_compact_action_alignment(
    qtbot: object,
) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert _form_label(dialog, dialog.dtype) == "Data type"
    assert _form_label(dialog, dialog.endian) == "Byte order"
    assert _form_label(dialog, dialog.layout_kind) == "Pixel layout"

    assert dialog.width() == 380
    assert dialog.load_button.width() == 112
    assert dialog.save_button.width() == 112
    assert dialog.ok_button.width() == 92
    assert dialog.cancel_button.width() == 92

    assert dialog.json_actions_layout.indexOf(dialog.load_button) == 0
    assert dialog.json_actions_layout.indexOf(dialog.save_button) == 1
    assert dialog.json_actions_layout.contentsMargins().left() == 92

    assert dialog.dont_show_layout.indexOf(dialog.dont_show_json_profiles) == 0
    assert dialog.dont_show_layout.contentsMargins().left() == 92

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
