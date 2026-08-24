from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

from pixelscope.app.main_window import MainWindow
from pixelscope.io.path_discovery import ImageInput
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.raw_open_dialog import RawOpenDialog

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_raw_dialog_prefills_all_bayer_profile_values(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    profile = RawProfile(
        name="camera",
        width=8,
        height=6,
        dtype="uint16",
        stride_bytes=20,
        offset_bytes=16,
        endianness="big",
        bit_depth=12,
        packing="unpacked_u16",
        channel_layout="BAYER",
        bayer_pattern="GBRG",
        black_level=(64, 65, 66, 67),
        white_level=4095,
    )
    dialog.set_profile(profile)
    assert not hasattr(dialog, "name")
    assert dialog.width_box.value() == 8
    assert dialog.height_box.value() == 6
    assert dialog.stride.value() == 20
    assert dialog.offset.value() == 16
    assert dialog.endian.currentText() == "big"
    assert dialog.bit_depth.value() == 12
    assert dialog.layout_kind.currentText() == "BAYER"
    assert dialog.bayer_pattern.currentText() == "GBRG"
    assert [
        control.value()
        for control in (dialog.black_r, dialog.black_gr, dialog.black_gb, dialog.black_b)
    ] == [64, 65, 66, 67]
    assert dialog.profile() == profile


def test_raw_sidecar_confirmation_and_same_path_reload(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    raw_path = tmp_path / "sensor.raw"
    np.arange(16, dtype=np.uint16).tofile(raw_path)
    sidecar = tmp_path / "sensor.json"
    initial_profile = RawProfile(
        name="initial",
        width=4,
        height=4,
        dtype="uint16",
        stride_bytes=8,
        bit_depth=10,
        packing="unpacked_u16",
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=(0, 0, 0, 0),
        white_level=1023,
    )
    initial_profile.save_json(sidecar)

    class ConfirmRawDialog:
        override: RawProfile | None = None
        loaded_profiles: list[RawProfile] = []

        def __init__(self, _parent: object) -> None:
            self.loaded: RawProfile | None = None

        def set_profile(self, profile: RawProfile) -> None:
            self.loaded = profile
            self.loaded_profiles.append(profile)

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def profile(self) -> RawProfile:
            assert self.loaded is not None
            return self.override or self.loaded

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.app.main_window.RawOpenDialog",
        ConfirmRawDialog,
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    image_input = ImageInput(raw_path, sidecar)
    window._handle_dropped_paths([raw_path])
    document_ids = list(window.documents)
    assert len(document_ids) == 1
    document_id = document_ids[0]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document_id].source is not None,
        timeout=3000,
    )
    first_document = window.documents[document_id]
    assert ConfirmRawDialog.loaded_profiles[0] == initial_profile
    assert first_document.shape == (4, 4)
    assert first_document.preview is not None
    assert np.all(first_document.preview[..., 1] >= first_document.preview[..., 0])

    ConfirmRawDialog.override = initial_profile.copy(
        update={
            "name": "reloaded",
            "width": 2,
            "height": 8,
            "stride_bytes": 4,
            "bayer_pattern": "BGGR",
        }
    )
    generation = first_document.generation
    reloaded_ids = window._register_inputs((image_input,), resolve_raw_profiles=True)
    window._select_document_ids(reloaded_ids)
    assert reloaded_ids == [document_id]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document_id].source is not None
        and window.documents[document_id].shape == (8, 2),
        timeout=3000,
    )
    reloaded = window.documents[document_id]
    assert len(window.documents) == 1
    assert reloaded.generation > generation
    assert reloaded.raw_profile.bayer_pattern == "BGGR"
    window.close()
