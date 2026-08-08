from __future__ import annotations

from pathlib import Path
from threading import Event, Lock

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QSettings

import pixelscope.app.main_window as main_window_module
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.path_discovery import discover_image_inputs
from pixelscope.io.raw_profile import RawProfile
from pixelscope.workers.task_worker import TaskWorker


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    QSettings().clear()


def _write_images(folder: Path, count: int) -> None:
    folder.mkdir()
    for index in range(count):
        assert cv2.imwrite(
            str(folder / f"frame-{index + 1}.png"),
            np.full((3, 4), index + 1, dtype=np.uint8),
        )


def _register_folder(window: MainWindow, folder: Path) -> list[str]:
    return window._register_inputs(discover_image_inputs((folder,)), select_all=False)


def _wait_for_running_preload(qtbot: object, window: MainWindow) -> None:
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: any(
            window.preload_controller.request_is_running(request)
            for request in window._preload_worker_requests.values()
        ),
        timeout=3000,
    )


def _raw_profile() -> RawProfile:
    return RawProfile(
        name="promotion-raw",
        width=4,
        height=2,
        stride_bytes=8,
        container_dtype="uint16",
        endianness="little",
        bit_depth=12,
        bit_alignment="lsb",
        channel_layout="GRAY",
        white_level=4095,
    )


def test_promoted_failure_uses_foreground_error_semantics_once(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "failure"
    _write_images(folder, 2)
    preload_started = Event()
    preload_release = Event()

    class FailureWorker(TaskWorker):
        def __init__(self, path: Path, *_args: object, **_kwargs: object) -> None:
            source_path = Path(path)

            def decode() -> ImageDocument:
                if source_path.name == "frame-2.png":
                    preload_started.set()
                    preload_release.wait(3)
                    raise RuntimeError("promoted decode failed")
                return ImageDocument.from_array(
                    np.ones((2, 2), dtype=np.uint8),
                    source_path.name,
                    source_path=source_path,
                )

            super().__init__(decode)

    monkeypatch.setattr(main_window_module, "ImageLoadWorker", FailureWorker)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    ids = _register_folder(window, folder)
    qtbot.waitUntil(preload_started.is_set, timeout=3000)  # type: ignore[attr-defined]
    _wait_for_running_preload(qtbot, window)

    window.next_folder_position()
    assert window.documents[ids[1]].loading_state == "loading"
    assert window.preload_controller.diagnostics.promotion_count == 1

    preload_release.set()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[ids[1]].loading_state == "error",
        timeout=4000,
    )

    snapshot = window.runtime_diagnostics_snapshot()
    assert snapshot.preload.failure_count == 0
    foreground_failures = [
        failure for failure in snapshot.recent_failures if failure.subsystem == "foreground-load"
    ]
    preload_failures = [
        failure for failure in snapshot.recent_failures if failure.subsystem == "preload"
    ]
    assert len(foreground_failures) == 1
    assert not preload_failures
    assert foreground_failures[0].category == "decode"


def test_navigation_away_stales_late_promoted_result(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "late"
    _write_images(folder, 3)
    preload_started = Event()
    preload_release = Event()
    calls: dict[str, int] = {}
    lock = Lock()

    class AdvisoryWorker(TaskWorker):
        def __init__(self, path: Path, *_args: object, **_kwargs: object) -> None:
            source_path = Path(path)
            with lock:
                calls[source_path.name] = calls.get(source_path.name, 0) + 1

            def decode() -> ImageDocument:
                if source_path.name == "frame-2.png":
                    preload_started.set()
                    preload_release.wait(3)
                    value = 111
                else:
                    value = 200 + int(source_path.stem.split("-")[-1])
                return ImageDocument.from_array(
                    np.full((2, 2), value, dtype=np.uint8),
                    source_path.name,
                    source_path=source_path,
                )

            super().__init__(decode)

        def cancel(self) -> None:
            """Simulate a decoder that cannot stop after advisory cancellation."""

            return

    monkeypatch.setattr(main_window_module, "ImageLoadWorker", AdvisoryWorker)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    ids = _register_folder(window, folder)
    qtbot.waitUntil(preload_started.is_set, timeout=3000)  # type: ignore[attr-defined]
    _wait_for_running_preload(qtbot, window)

    window.next_folder_position()
    assert window.preload_controller.diagnostics.promotion_count == 1
    assert calls["frame-2.png"] == 1

    window.next_folder_position()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[ids[2]].source is not None,
        timeout=3000,
    )
    assert window.selected_documents[0].document_id == ids[2]

    preload_release.set()
    qtbot.waitUntil(lambda: not window._preload_workers, timeout=4000)  # type: ignore[attr-defined]

    assert window.documents[ids[1]].source is None
    assert window.documents[ids[1]].loading_state == "pending"
    assert window.documents[ids[2]].source is not None
    assert window._normal_load_stale_drop_count >= 1
    assert calls["frame-2.png"] == 1


def test_pair_navigation_promotes_one_running_member_and_normally_loads_other(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    _write_images(folder_a, 3)
    _write_images(folder_b, 3)
    promoted_started = Event()
    promoted_release = Event()
    calls: dict[tuple[str, str], int] = {}
    lock = Lock()

    class PairWorker(TaskWorker):
        def __init__(self, path: Path, *_args: object, **_kwargs: object) -> None:
            source_path = Path(path)
            key = (source_path.parent.name, source_path.name)
            with lock:
                calls[key] = calls.get(key, 0) + 1

            def decode() -> ImageDocument:
                if key == ("a", "frame-2.png"):
                    promoted_started.set()
                    promoted_release.wait(3)
                return ImageDocument.from_array(
                    np.ones((2, 2), dtype=np.uint8),
                    source_path.name,
                    source_path=source_path,
                )

            super().__init__(decode)

    monkeypatch.setattr(main_window_module, "ImageLoadWorker", PairWorker)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.register_folder_group([folder_a, folder_b])
    qtbot.waitUntil(promoted_started.is_set, timeout=3000)  # type: ignore[attr-defined]
    _wait_for_running_preload(qtbot, window)

    next_plan = window._plan_folder_navigation(1)
    assert next_plan is not None
    promoted_id, normal_id = next_plan.document_ids
    window.next_folder_position()

    assert calls[("a", "frame-2.png")] == 1
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: calls.get(("b", "frame-2.png"), 0) == 1,
        timeout=3000,
    )
    assert window.documents[promoted_id].loading_state == "loading"
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[normal_id].source is not None,
        timeout=3000,
    )
    assert window._preload_pool.maxThreadCount() == 1
    assert window.preload_controller.diagnostics.promotion_count == 1

    promoted_release.set()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[promoted_id].source is not None
        and not window._preload_workers
        and not window._workers,
        timeout=4000,
    )

    assert calls[("a", "frame-2.png")] == 1
    assert calls[("b", "frame-2.png")] == 1
    assert [document.document_id for document in window.selected_documents] == list(
        next_plan.document_ids
    )
    assert window.documents[next_plan.document_ids[0]].source is not None
    assert window.documents[next_plan.document_ids[1]].source is not None


def test_running_raw_preload_promotes_only_with_exact_registered_identity(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "raw"
    folder.mkdir()
    first_path = folder / "frame-1.png"
    raw_path = folder / "frame-2.raw"
    assert cv2.imwrite(str(first_path), np.ones((2, 4), dtype=np.uint8))
    raw_path.write_bytes(np.arange(8, dtype="<u2").tobytes())
    profile = _raw_profile()
    raw_started = Event()
    raw_release = Event()
    raw_calls = 0

    class RawPromotionWorker(TaskWorker):
        def __init__(
            self,
            path: Path,
            raw_profile: RawProfile | None = None,
            **_kwargs: object,
        ) -> None:
            nonlocal raw_calls
            source_path = Path(path)
            if source_path.suffix.casefold() == ".raw":
                raw_calls += 1

            def decode() -> ImageDocument:
                if source_path.suffix.casefold() == ".raw":
                    raw_started.set()
                    raw_release.wait(3)
                    source = np.arange(8, dtype=np.uint16).reshape(2, 4)
                else:
                    source = np.ones((2, 4), dtype=np.uint8)
                return ImageDocument.from_array(
                    source,
                    source_path.name,
                    source_path=source_path,
                    channel_layout=raw_profile.channel_layout if raw_profile else "GRAY",
                    bit_depth=raw_profile.bit_depth if raw_profile else 8,
                    raw_profile=raw_profile,
                )

            super().__init__(decode)

    monkeypatch.setattr(main_window_module, "ImageLoadWorker", RawPromotionWorker)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first = ImageDocument.from_array(
        np.ones((2, 4), dtype=np.uint8),
        first_path.name,
        source_path=first_path,
    )
    target = ImageDocument.pending_document(raw_path)
    window.add_document(first, select=False)
    window.add_document(target, select=False)
    window._raw_profiles[target.document_id] = profile
    window._select_document_ids([first.document_id])
    qtbot.waitUntil(raw_started.is_set, timeout=3000)  # type: ignore[attr-defined]
    _wait_for_running_preload(qtbot, window)

    window.next_folder_position()

    assert raw_calls == 1
    assert window.preload_controller.diagnostics.promotion_count == 1
    assert window.documents[target.document_id].loading_state == "loading"

    raw_release.set()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[target.document_id].source is not None
        and not window._preload_workers,
        timeout=4000,
    )

    loaded = window.documents[target.document_id]
    assert raw_calls == 1
    assert loaded.raw_profile == profile
    assert loaded.source is not None
    assert np.array_equal(loaded.source, np.arange(8, dtype=np.uint16).reshape(2, 4))
