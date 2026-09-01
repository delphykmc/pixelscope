from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

from pixelscope.app.main_window import MainWindow
from pixelscope.app.raw_input_compatibility import install_raw_input_compatibility
from pixelscope.app.registration_controller import install_large_folder_registration
from pixelscope.io.path_discovery import discover_image_inputs
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.raw_open_dialog import RawOpenDialog

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_raw_dialog_tracks_minimum_stride_until_manual_override(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.stride_is_auto
    assert dialog.stride.value() == dialog.minimum_stride_bytes() == 1280

    dialog.width_box.setValue(100)
    assert dialog.stride.value() == 200

    dialog.container.setCurrentIndex(dialog.container.findData("uint8"))
    assert dialog.stride.value() == 100

    dialog.container.setCurrentIndex(dialog.container.findData("uint16"))
    dialog.storage_format.setCurrentIndex(dialog.storage_format.findData("mipi_raw12"))
    assert dialog.stride.value() == 150

    dialog.stride.setValue(192)
    assert not dialog.stride_is_auto
    dialog.width_box.setValue(120)
    assert dialog.minimum_stride_bytes() == 180
    assert dialog.stride.value() == 192

    dialog.storage_format.setCurrentIndex(dialog.storage_format.findData("unpacked"))
    assert dialog.minimum_stride_bytes() == 240
    assert dialog.stride.value() == 192

    dialog.container.setCurrentIndex(dialog.container.findData("uint8"))
    assert dialog.minimum_stride_bytes() == 120
    assert dialog.stride.value() == 192

    dialog.container.setCurrentIndex(dialog.container.findData("uint16"))
    assert dialog.stride.value() == 192
    assert not dialog.stride_is_auto


def test_explicit_profile_stride_remains_manual(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    profile = RawProfile(
        name="explicit",
        width=8,
        height=4,
        stride_bytes=20,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=12,
        bit_alignment="lsb",
        channel_layout="GRAY",
        black_level=0,
        white_level=4095,
    )

    dialog.set_profile(profile)
    assert not dialog.stride_is_auto
    dialog.width_box.setValue(9)
    assert dialog.minimum_stride_bytes() == 18
    assert dialog.stride.value() == 20


def test_raw_like_extensions_share_runtime_profile_and_decode_path(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    profile = RawProfile(
        name="binary",
        width=4,
        height=4,
        stride_bytes=8,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=12,
        bit_alignment="lsb",
        channel_layout="GRAY",
        black_level=64,
        white_level=4095,
    )

    raw_path = tmp_path / "a.raw"
    data_path = tmp_path / "b.data"
    yuv_path = tmp_path / "c.yuv"
    for path in (raw_path, data_path, yuv_path):
        np.arange(16, dtype=np.uint16).tofile(path)

    # Verify .raw can consume the lower-priority .imgprops path, while the
    # additional raw-like extensions preserve the existing PixelScope JSON path.
    (tmp_path / "a.imgprops").write_text(
        json.dumps(
            {
                "width": 4,
                "height": 4,
                "imageType": "BAYER12",
                "pattern": "RGGB",
                "sensorBitWidth": 12,
                "pedestal": 64,
            }
        ),
        encoding="utf-8",
    )
    profile.save_json(tmp_path / "b.json")
    profile.save_json(tmp_path / "c.json")

    class AcceptProfileDialog:
        def __init__(self, _parent: object) -> None:
            self.loaded: RawProfile | None = None

        def set_source_path(self, _path: Path) -> None:
            return

        def set_json_confirmation_option_visible(self, _visible: bool) -> None:
            return

        def set_profile(
            self,
            loaded: RawProfile,
            *,
            stride_is_auto: bool = False,
        ) -> None:
            del stride_is_auto
            self.loaded = loaded

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def profile(self) -> RawProfile:
            assert self.loaded is not None
            return self.loaded

        def dont_show_json_profiles_requested(self) -> bool:
            return False

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.app.main_window.RawOpenDialog",
        AcceptProfileDialog,
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.app.raw_input_compatibility.RawOpenDialog",
        AcceptProfileDialog,
    )

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_raw_input_compatibility(window)

    inputs = discover_image_inputs((raw_path, data_path, yuv_path))
    document_ids = window._register_inputs(inputs, resolve_raw_profiles=True)
    assert len(document_ids) == 3
    assert {window.documents[item].source_path.suffix for item in document_ids} == {
        ".raw",
        ".data",
        ".yuv",
    }

    raw_document = next(
        window.documents[item]
        for item in document_ids
        if window.documents[item].source_path == raw_path.resolve()
    )
    assert raw_document.raw_profile is None
    assert window._raw_profiles[raw_document.document_id].channel_layout == "BAYER"
    assert window._raw_profiles[raw_document.document_id].black_level == 64

    window._select_document_ids(document_ids)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(window.documents[item].source is not None for item in document_ids),
        timeout=5000,
    )
    assert all(window.documents[item].source.shape == (4, 4) for item in document_ids)
    window.close()


def test_wp_a_folder_registration_keeps_raw_like_inputs_lazy(
    qtbot: object,
    tmp_path: Path,
) -> None:
    data_path = tmp_path / "frame1.data"
    yuv_path = tmp_path / "frame2.yuv"
    data_path.write_bytes(b"binary")
    yuv_path.write_bytes(b"binary")

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_raw_input_compatibility(window)
    registration = install_large_folder_registration(window)

    registration.enqueue((tmp_path,))
    qtbot.waitUntil(lambda: registration.is_idle, timeout=5000)  # type: ignore[attr-defined]

    assert {document.source_path for document in window.documents.values()} == {
        data_path.resolve(),
        yuv_path.resolve(),
    }
    assert all(document.source is None for document in window.documents.values())
    assert all(document.loading_state == "pending" for document in window.documents.values())
    assert not window._raw_profiles
    assert not window.selected_documents
    window.close()
