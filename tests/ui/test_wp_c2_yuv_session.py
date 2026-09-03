from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QDialog

import pixelscope.app.yuv_input_semantics as yuv_semantics_module
from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_set import Session, SessionDifference, SessionSource
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.io.path_discovery import ImageInput
from pixelscope.io.yuv_profile import YuvProfile

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def _yuv_profile(*, name: str = "native-yuv") -> YuvProfile:
    return YuvProfile(
        name=name,
        width=4,
        height=4,
        channel_layout="YUV420",
    )


def _write_yuv420(path: Path, *, u_delta: int = 0) -> None:
    y = np.arange(16, dtype=np.uint8).reshape(4, 4)
    u = np.array([[40, 50], [60, 70]], dtype=np.uint8)
    v = np.array([[180, 190], [200, 210]], dtype=np.uint8)
    if u_delta:
        u = (u.astype(np.uint16) + u_delta).astype(np.uint8)
    uv = np.empty((2, 4), dtype=np.uint8)
    uv[:, 0::2] = u
    uv[:, 1::2] = v
    path.write_bytes(y.tobytes() + uv.tobytes())


@pytest.mark.parametrize("channel", ("Y", "U", "V"))
def test_session_repository_round_trips_native_yuv_difference_channels(
    tmp_path: Path,
    channel: str,
) -> None:
    first = (tmp_path / "first.yuv").resolve()
    second = (tmp_path / "second.yuv").resolve()
    session = Session(
        registered_sources=(
            SessionSource(str(first), _yuv_profile().dict()),
            SessionSource(str(second), _yuv_profile().dict()),
        ),
        selected_paths=(str(first), str(second)),
        difference=SessionDifference(
            image_a_path=str(first),
            image_b_path=str(second),
            channel=channel,
        ),
    )
    target = tmp_path / f"{channel.lower()}-difference.pixelscope"
    repository = ComparisonSetRepository()

    repository.save(target, session)
    restored = repository.load(target)

    assert restored.difference is not None
    assert restored.difference.channel == channel


def test_session_save_and_restore_preserves_native_yuv_difference_channel(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_path = tmp_path / "first.yuv"
    second_path = tmp_path / "second.yuv"
    _write_yuv420(first_path)
    _write_yuv420(second_path, u_delta=7)
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
    first_id = window._register_input(ImageInput(first_path, None), resolve_raw_profile=True)
    second_id = window._register_input(ImageInput(second_path, None), resolve_raw_profile=True)

    assert first_id is not None
    assert second_id is not None
    window._select_document_ids([first_id, second_id])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.yuv_frame is not None for document in window.selected_documents),
        timeout=4000,
    )
    panel = window.difference_panel
    panel.channel.setCurrentText("U")
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=3000,
    )

    target = tmp_path / "yuv-difference-session.pixelscope"
    saved = window.session_controller.save_to_path(target)
    assert saved.difference is not None
    assert saved.difference.channel == "U"
    window.close()

    class FailIfPrompted:
        def __init__(self, _parent: object) -> None:
            pytest.fail("Session-restored YUV profile must not prompt")

    monkeypatch.setattr(yuv_semantics_module, "YuvOpenDialog", FailIfPrompted)
    reopened = _window(qtbot)
    loaded, missing = reopened.session_controller.open_from_path(target)

    assert loaded == 2
    assert missing == ()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: reopened._difference_document is not None
        and reopened.difference_panel.channel.currentText() == "U",
        timeout=4000,
    )

    restored_difference = reopened._difference_document
    assert restored_difference is not None
    assert restored_difference.source is not None
    assert restored_difference.source.shape == (2, 2)
    assert restored_difference.reference_shape == (4, 4)
    assert restored_difference.sample_channel == "U"
    assert prompt_count == 2
    reopened.close()
