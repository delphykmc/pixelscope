from __future__ import annotations

from pathlib import Path

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
    dialog.use_minimum_stride_button.click()
    assert dialog.stride.value() == 26


def test_raw_dialog_compares_expected_and_actual_file_size(
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
    assert dialog.expected_minimum_file_size() == 32
    assert "32 bytes" in dialog.expected_size_value.text()
    assert "32 bytes" in dialog.actual_size_value.text()
    assert "matches" in dialog.file_status.text()
    assert dialog.ok_button.isEnabled()

    dialog.height_box.setValue(5)
    assert dialog.expected_minimum_file_size() == 40
    assert "8 bytes too small" in dialog.file_status.text()
    assert not dialog.ok_button.isEnabled()

    dialog.height_box.setValue(3)
    assert dialog.expected_minimum_file_size() == 24
    assert "8 trailing bytes" in dialog.file_status.text()
    assert dialog.ok_button.isEnabled()


def test_raw_dialog_uses_layout_specific_black_level_controls(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()

    assert dialog.black_gray.isVisible()
    assert not dialog.black_r.isVisible()
    dialog.layout_kind.setCurrentText("BAYER")
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

    dialog.layout_kind.setCurrentText("GRAY")
    dialog.black_gray.setValue(21)
    assert dialog.profile().black_level == 21


def test_raw_dialog_renames_fields_and_aligns_action_columns(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert _form_label(dialog, dialog.dtype) == "Data type"
    assert _form_label(dialog, dialog.endian) == "Byte order"
    assert _form_label(dialog, dialog.layout_kind) == "Pixel layout"
    assert dialog.button_grid.getItemPosition(
        dialog.button_grid.indexOf(dialog.load_button)
    ) == (0, 0, 1, 1)
    assert dialog.button_grid.getItemPosition(
        dialog.button_grid.indexOf(dialog.save_button)
    ) == (0, 1, 1, 1)
    assert dialog.button_grid.getItemPosition(
        dialog.button_grid.indexOf(dialog.ok_button)
    ) == (3, 0, 1, 1)
    assert dialog.button_grid.getItemPosition(
        dialog.button_grid.indexOf(dialog.cancel_button)
    ) == (3, 1, 1, 1)


def test_raw_dialog_json_skip_option_is_opt_in(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.skip_json_confirmation.isHidden()
    assert not dialog.skip_json_confirmation_requested()
    dialog.set_json_confirmation_option_visible(True)
    assert not dialog.skip_json_confirmation.isHidden()
    assert not dialog.skip_json_confirmation_requested()
    dialog.skip_json_confirmation.setChecked(True)
    assert dialog.skip_json_confirmation_requested()
