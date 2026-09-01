from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

import pixelscope.app.main_window as main_window_module
import pixelscope.app.raw_input_compatibility as raw_compatibility_module
from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.app.raw_input_compatibility import install_raw_input_compatibility
from pixelscope.app.settings import ApplicationSettings
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.path_discovery import discover_image_inputs
from pixelscope.io.raw_profile import RawProfile

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _raw_profile(*, name: str = "wp-b", black_level: int = 0, stride_bytes: int = 8) -> RawProfile:
    return RawProfile(
        name=name,
        width=4,
        height=2,
        stride_bytes=stride_bytes,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=12,
        bit_alignment="lsb",
        channel_layout="GRAY",
        black_level=black_level,
        white_level=4095,
    )


def _write_binary(path: Path) -> np.ndarray:
    values = np.arange(8, dtype="<u2").reshape(2, 4)
    path.write_bytes(values.tobytes())
    return values


def test_production_composition_preserves_folder_display_tags_for_all_local_inputs(
    qtbot: object,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "tagged-inputs"
    folder.mkdir()
    png_path = folder / "frame-1.png"
    raw_path = folder / "frame-2.raw"
    data_path = folder / "frame-3.data"
    yuv_path = folder / "frame-4.yuv"
    assert cv2.imwrite(str(png_path), np.ones((2, 4), dtype=np.uint8))
    for path in (raw_path, data_path, yuv_path):
        _write_binary(path)

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    tag_controller = window.folder_display_tag_controller
    tag_controller.set_tag(folder, "PAIR-A")

    document_ids = window._register_inputs(
        discover_image_inputs((folder,)),
        resolve_raw_profiles=False,
    )

    assert len(document_ids) == 4
    expected_names = {
        "[PAIR-A] frame-1.png",
        "[PAIR-A] frame-2.raw",
        "[PAIR-A] frame-3.data",
        "[PAIR-A] frame-4.yuv",
    }
    assert {window.documents[item].display_name for item in document_ids} == expected_names

    folder_row = next(
        window.document_list.topLevelItem(index)
        for index in range(window.document_list.topLevelItemCount())
        if str(
            window.document_list.topLevelItem(index).data(
                0,
                window.document_list.PATH_ROLE,
            )
            or ""
        ).casefold()
        == str(folder.resolve()).casefold()
    )
    assert folder_row.text(0) == f"{folder.name} [PAIR-A]"
    window.close()


@pytest.mark.parametrize("suffix", [".data", ".yuv"])
def test_production_preload_skips_unresolved_raw_like_without_prompt_or_decode(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
) -> None:
    target_path = tmp_path / f"unresolved{suffix}"
    _write_binary(target_path)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    target = ImageDocument.pending_document(target_path)
    window.add_document(target, select=False)

    monkeypatch.setattr(
        window,
        "_confirm_raw_profile",
        lambda *_args, **_kwargs: pytest.fail("speculative preload must not prompt"),
    )
    starts: list[tuple[object, ...]] = []
    monkeypatch.setattr(window, "_start_preload", lambda *args: starts.append(args))
    monkeypatch.setattr(
        window,
        "_plan_folder_navigation",
        lambda _delta: SimpleNamespace(document_ids=(target.document_id,)),
    )

    window._refresh_preload_plan()

    assert starts == []
    assert target.source is None
    assert target.loading_state == "pending"
    assert window.preload_controller.pending_document_ids == ()
    window.close()


@pytest.mark.parametrize("suffix", [".png", ".raw", ".data", ".yuv"])
def test_production_preload_preserves_profile_identity_and_exact_size_policy(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
) -> None:
    target_path = tmp_path / f"target{suffix}"
    expected: np.ndarray | None = None
    profile: RawProfile | None = None
    if suffix == ".png":
        expected = np.arange(8, dtype=np.uint8).reshape(2, 4)
        assert cv2.imwrite(str(target_path), expected)
    else:
        expected = _write_binary(target_path)
        profile = _raw_profile(name=f"profile-{suffix[1:]}")

    application = ApplicationSettings(require_exact_raw_file_size=True)
    window = MainWindow(application, application.performance_settings())
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    target = ImageDocument.pending_document(target_path)
    window.add_document(target, select=False)
    if profile is not None:
        window._raw_profiles[target.document_id] = profile

    original_worker = main_window_module.ImageLoadWorker
    worker_calls: list[tuple[Path, RawProfile | None, bool]] = []

    def recording_worker(
        path: Path,
        raw_profile: RawProfile | None = None,
        *,
        require_exact_raw_size: bool = False,
    ) -> object:
        worker_calls.append((Path(path), raw_profile, require_exact_raw_size))
        return original_worker(
            path,
            raw_profile,
            require_exact_raw_size=require_exact_raw_size,
        )

    monkeypatch.setattr(main_window_module, "ImageLoadWorker", recording_worker)
    monkeypatch.setattr(
        window,
        "_plan_folder_navigation",
        lambda _delta: SimpleNamespace(document_ids=(target.document_id,)),
    )

    window._refresh_preload_plan()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window._preload_workers
        and window.documents[target.document_id].source is not None,
        timeout=4000,
    )

    target_calls = [call for call in worker_calls if call[0] == target_path]
    assert len(target_calls) == 1
    _, worker_profile, exact_size = target_calls[0]
    assert exact_size is True
    if profile is None:
        assert worker_profile is None
    else:
        assert worker_profile is profile
        assert window.documents[target.document_id].raw_profile is profile
    assert np.array_equal(window.documents[target.document_id].source, expected)
    window.close()


def test_runtime_json_sidecar_remains_authoritative_over_imgprops(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "precedence.data"
    _write_binary(source)
    json_profile = _raw_profile(name="json-authority", black_level=17, stride_bytes=12)
    json_profile.save_json(tmp_path / "precedence.json")
    (tmp_path / "precedence.imgprops").write_text(
        json.dumps(
            {
                "width": 4,
                "height": 2,
                "imageType": "BAYER12",
                "pattern": "RGGB",
                "sensorBitWidth": 12,
                "pedestal": 777,
            }
        ),
        encoding="utf-8",
    )

    class AcceptLoadedProfileDialog:
        def __init__(self, _parent: object) -> None:
            self.loaded: RawProfile | None = None

        def set_source_path(self, _path: Path) -> None:
            return

        def set_profile(self, profile: RawProfile, **_kwargs: object) -> None:
            self.loaded = profile

        def set_json_confirmation_option_visible(self, _visible: bool) -> None:
            return

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def profile(self) -> RawProfile:
            assert self.loaded is not None
            return self.loaded

        def dont_show_json_profiles_requested(self) -> bool:
            return False

    monkeypatch.setattr(main_window_module, "RawOpenDialog", AcceptLoadedProfileDialog)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_raw_input_compatibility(window)
    image_input = discover_image_inputs((source,))[0]
    assert image_input.raw_profile_path == tmp_path / "precedence.json"

    document_id = window._register_input(image_input, resolve_raw_profile=True)

    assert document_id is not None
    resolved = window._raw_profiles[document_id]
    assert resolved.name == "json-authority"
    assert resolved.black_level == 17
    assert resolved.stride_bytes == 12
    window.close()


def test_invalid_imgprops_falls_back_to_editable_default_profile_flow(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "fallback.yuv"
    _write_binary(source)
    (tmp_path / "fallback.imgprops").write_text("not-json", encoding="utf-8")
    fallback_profile = _raw_profile(name="editable-fallback", black_level=23)
    warnings: list[str] = []

    class AcceptFallbackDialog:
        def __init__(self, _parent: object) -> None:
            self.profile_was_set = False

        def set_source_path(self, _path: Path) -> None:
            return

        def set_profile(self, _profile: RawProfile, **_kwargs: object) -> None:
            self.profile_was_set = True
            pytest.fail("invalid .imgprops must fall back to editable defaults")

        def set_json_confirmation_option_visible(self, _visible: bool) -> None:
            return

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def profile(self) -> RawProfile:
            return fallback_profile

        def dont_show_json_profiles_requested(self) -> bool:
            return False

    monkeypatch.setattr(main_window_module, "RawOpenDialog", AcceptFallbackDialog)
    monkeypatch.setattr(
        raw_compatibility_module.QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(str(message)),
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    install_raw_input_compatibility(window)
    image_input = discover_image_inputs((source,))[0]
    assert image_input.raw_profile_path == tmp_path / "fallback.imgprops"

    document_id = window._register_input(image_input, resolve_raw_profile=True)

    assert document_id is not None
    assert warnings and "Using editable defaults" in warnings[0]
    assert window._raw_profiles[document_id] is fallback_profile
    window.close()
