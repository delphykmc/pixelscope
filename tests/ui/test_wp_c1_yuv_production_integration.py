from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

import pixelscope.app.main_window as main_window_module
import pixelscope.app.raw_input_compatibility as raw_compatibility_module
import pixelscope.app.yuv_input_semantics as yuv_semantics_module
from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.path_discovery import ImageInput, discover_image_inputs
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.yuv_profile import YuvProfile

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _yuv_profile(*, name: str = "native-yuv") -> YuvProfile:
    return YuvProfile(
        name=name,
        width=4,
        height=4,
        channel_layout="YUV420",
    )


def _write_yuv420(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y = np.arange(16, dtype=np.uint8).reshape(4, 4)
    u = np.array([[40, 50], [60, 70]], dtype=np.uint8)
    v = np.array([[180, 190], [200, 210]], dtype=np.uint8)
    uv = np.empty((2, 4), dtype=np.uint8)
    uv[:, 0::2] = u
    uv[:, 1::2] = v
    path.write_bytes(y.tobytes() + uv.tobytes())
    return y, u, v


def _raw_profile(*, name: str = "legacy-raw") -> RawProfile:
    return RawProfile(
        name=name,
        width=4,
        height=2,
        stride_bytes=8,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=12,
        bit_alignment="lsb",
        channel_layout="GRAY",
        black_level=0,
        white_level=4095,
    )


def _write_raw(path: Path) -> np.ndarray:
    values = np.arange(8, dtype="<u2").reshape(2, 4)
    path.write_bytes(values.tobytes())
    return values


def _window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def test_explicit_yuv_json_direct_open_reaches_native_worker_decode(
    qtbot: object,
    tmp_path: Path,
) -> None:
    source = tmp_path / "explicit.yuv"
    expected_y, expected_u, expected_v = _write_yuv420(source)
    profile = _yuv_profile(name="explicit-sidecar")
    profile.save_json(tmp_path / "explicit.json")
    window = _window(qtbot)

    image_input = discover_image_inputs((source,))[0]
    document_id = window._register_input(image_input, resolve_raw_profile=True)

    assert document_id is not None
    resolved = window._raw_profiles[document_id]
    assert isinstance(resolved, YuvProfile)
    assert resolved.name == "explicit-sidecar"
    document = window.documents[document_id]
    window._ensure_loaded(document)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document_id].yuv_frame is not None,
        timeout=4000,
    )

    loaded = window.documents[document_id]
    assert loaded.yuv_frame is not None
    np.testing.assert_array_equal(loaded.yuv_frame.y, expected_y)
    np.testing.assert_array_equal(loaded.yuv_frame.u, expected_u)
    np.testing.assert_array_equal(loaded.yuv_frame.v, expected_v)
    assert loaded.preview is not None and loaded.preview.shape == (4, 4, 3)
    window.close()


def test_unresolved_folder_yuv_resolves_only_on_foreground_use(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    source = folder / "pending.yuv"
    _write_yuv420(source)
    dialog_calls: list[Path] = []

    class AcceptYuvDialog:
        def __init__(self, _parent: object) -> None:
            self.source_path: Path | None = None

        def set_source_path(self, path: Path) -> None:
            self.source_path = Path(path)

        def set_profile(self, _profile: YuvProfile) -> None:
            return

        def exec(self) -> QDialog.DialogCode:
            assert self.source_path is not None
            dialog_calls.append(self.source_path)
            return QDialog.DialogCode.Accepted

        def uses_generic_raw(self) -> bool:
            return False

        def profile(self) -> YuvProfile:
            return _yuv_profile(name="foreground-resolved")

    monkeypatch.setattr(yuv_semantics_module, "YuvOpenDialog", AcceptYuvDialog)
    window = _window(qtbot)

    result = window.register_folders((folder,))
    assert result.image_count == 1
    document = next(
        candidate for candidate in window.documents.values() if candidate.source_path == source
    )
    assert document.loading_state == "pending"
    assert document.yuv_frame is None
    assert dialog_calls == []

    window._select_document_ids([document.document_id])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document.document_id].yuv_frame is not None,
        timeout=4000,
    )

    assert dialog_calls == [source]
    assert isinstance(window._raw_profiles[document.document_id], YuvProfile)
    window.close()


def test_yuv_with_legacy_raw_json_stays_on_generic_raw_path(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "legacy-json.yuv"
    expected = _write_raw(source)
    profile = _raw_profile(name="raw-json")
    profile.save_json(tmp_path / "legacy-json.json")

    class AcceptRawJsonDialog:
        def __init__(self, _parent: object) -> None:
            self.loaded: RawProfile | None = None

        def set_source_path(self, _path: Path) -> None:
            return

        def set_profile(self, profile_arg: RawProfile, **_kwargs: object) -> None:
            self.loaded = profile_arg

        def set_json_confirmation_option_visible(self, _visible: bool) -> None:
            return

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def profile(self) -> RawProfile:
            assert self.loaded is not None
            return self.loaded

        def dont_show_json_profiles_requested(self) -> bool:
            return False

    monkeypatch.setattr(main_window_module, "RawOpenDialog", AcceptRawJsonDialog)
    window = _window(qtbot)
    image_input = discover_image_inputs((source,))[0]

    document_id = window._register_input(image_input, resolve_raw_profile=True)

    assert document_id is not None
    assert isinstance(window._raw_profiles[document_id], RawProfile)
    window._ensure_loaded(window.documents[document_id])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document_id].source is not None,
        timeout=4000,
    )
    loaded = window.documents[document_id]
    assert loaded.yuv_frame is None
    np.testing.assert_array_equal(loaded.source, expected)
    window.close()


def test_yuv_with_imgprops_stays_on_generic_raw_path(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "legacy-imgprops.yuv"
    _write_raw(source)
    (tmp_path / "legacy-imgprops.imgprops").write_text(
        '{"width":4,"height":2,"imageType":"BAYER12",'
        '"pattern":"RGGB","sensorBitWidth":12,"pedestal":0}',
        encoding="utf-8",
    )

    class AcceptImgpropsDialog:
        def __init__(self, _parent: object) -> None:
            self.loaded: RawProfile | None = None

        def set_source_path(self, _path: Path) -> None:
            return

        def set_profile(self, profile_arg: RawProfile, **_kwargs: object) -> None:
            self.loaded = profile_arg

        def set_json_confirmation_option_visible(self, _visible: bool) -> None:
            return

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def profile(self) -> RawProfile:
            assert self.loaded is not None
            return self.loaded

    monkeypatch.setattr(raw_compatibility_module, "RawOpenDialog", AcceptImgpropsDialog)
    window = _window(qtbot)
    image_input = discover_image_inputs((source,))[0]

    document_id = window._register_input(image_input, resolve_raw_profile=True)

    assert document_id is not None
    resolved = window._raw_profiles[document_id]
    assert isinstance(resolved, RawProfile)
    assert resolved.channel_layout == "BAYER"
    assert window.documents[document_id].yuv_frame is None
    window.close()


def test_resolved_native_yuv_uses_bounded_preload_worker_lifecycle(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "preload.yuv"
    expected_y, _u, _v = _write_yuv420(source)
    profile = _yuv_profile(name="preload-resolved")
    window = _window(qtbot)
    document = ImageDocument.pending_document(source)
    window.add_document(document, select=False)
    window._raw_profiles[document.document_id] = profile
    monkeypatch.setattr(
        window,
        "_plan_folder_navigation",
        lambda _delta: SimpleNamespace(document_ids=(document.document_id,)),
    )

    window._refresh_preload_plan()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window._preload_workers
        and window.documents[document.document_id].yuv_frame is not None,
        timeout=4000,
    )

    loaded = window.documents[document.document_id]
    assert isinstance(loaded.raw_profile, YuvProfile)
    assert loaded.raw_profile.name == "preload-resolved"
    assert loaded.yuv_frame is not None
    np.testing.assert_array_equal(loaded.yuv_frame.y, expected_y)
    assert window.preload_controller.pending_document_ids == ()
    window.close()


def test_yuv_profile_change_invalidates_generation_and_reloads_native_frame(
    qtbot: object,
    tmp_path: Path,
) -> None:
    source = tmp_path / "reload.yuv"
    _write_yuv420(source)
    first = _yuv_profile(name="first")
    second = _yuv_profile(name="second")
    window = _window(qtbot)
    document = ImageDocument.pending_document(source)
    window.add_document(document, select=False)
    window._raw_profiles[document.document_id] = first
    window._ensure_loaded(document)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document.document_id].yuv_frame is not None,
        timeout=4000,
    )
    generation = window.documents[document.document_id].generation

    window._raw_profiles[document.document_id] = second
    window._mark_raw_for_reload(document.document_id, second)

    pending = window.documents[document.document_id]
    assert pending.generation == generation + 1
    assert pending.source is None
    assert pending.preview is None
    assert pending.yuv_frame is None
    assert pending.loading_state == "pending"
    assert pending.raw_profile is second

    window._ensure_loaded(pending)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document.document_id].yuv_frame is not None,
        timeout=4000,
    )
    reloaded = window.documents[document.document_id]
    assert reloaded.generation == generation + 1
    assert isinstance(reloaded.raw_profile, YuvProfile)
    assert reloaded.raw_profile.name == "second"
    window.close()


def test_sidecarless_native_yuv_session_round_trip_restores_without_prompt(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "session-only.yuv"
    _write_yuv420(source)
    profile = _yuv_profile(name="session-authority")
    prompt_count = 0

    class AcceptInitialDialog:
        def __init__(self, _parent: object) -> None:
            self.source_path: Path | None = None

        def set_source_path(self, path: Path) -> None:
            self.source_path = Path(path)

        def set_profile(self, _profile: YuvProfile) -> None:
            return

        def exec(self) -> QDialog.DialogCode:
            nonlocal prompt_count
            prompt_count += 1
            return QDialog.DialogCode.Accepted

        def uses_generic_raw(self) -> bool:
            return False

        def profile(self) -> YuvProfile:
            return profile

    monkeypatch.setattr(yuv_semantics_module, "YuvOpenDialog", AcceptInitialDialog)
    window = _window(qtbot)
    document_id = window._register_input(
        ImageInput(source, None),
        resolve_raw_profile=True,
    )
    assert document_id is not None
    window._select_document_ids([document_id])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document_id].yuv_frame is not None,
        timeout=4000,
    )
    target = tmp_path / "native-yuv.pixelscope"
    saved = window.session_controller.save_to_path(target)
    assert saved.registered_sources[0].raw_profile is not None
    assert saved.registered_sources[0].raw_profile["channel_layout"] == "YUV420"
    window.close()

    class FailIfPrompted:
        def __init__(self, _parent: object) -> None:
            pytest.fail("Session-restored YUV profile must not prompt")

    monkeypatch.setattr(yuv_semantics_module, "YuvOpenDialog", FailIfPrompted)
    reopened = _window(qtbot)
    loaded, missing = reopened.session_controller.open_from_path(target)

    assert loaded == 1
    assert missing == ()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: bool(reopened.selected_documents)
        and reopened.selected_documents[0].yuv_frame is not None,
        timeout=4000,
    )
    restored = reopened.selected_documents[0]
    assert prompt_count == 1
    assert isinstance(reopened._raw_profiles[restored.document_id], YuvProfile)
    assert isinstance(restored.raw_profile, YuvProfile)
    assert restored.raw_profile.name == "session-authority"
    reopened.close()
