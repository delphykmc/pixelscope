from __future__ import annotations

from pathlib import Path
from threading import Event, Lock

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QSettings

import pixelscope.app.main_window as main_window_module
from pixelscope.app.main_window import MainWindow
from pixelscope.app.settings import ApplicationSettings
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.performance_settings import PerformanceSettings
from pixelscope.io.path_discovery import discover_image_inputs
from pixelscope.io.raw_profile import RawProfile
from pixelscope.workers.task_worker import TaskWorker


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    QSettings().clear()


def _write_images(folder: Path, count: int, *, shape: tuple[int, int] = (3, 4)) -> None:
    folder.mkdir()
    for index in range(count):
        assert cv2.imwrite(
            str(folder / f"frame-{index + 1}.png"),
            np.full(shape, index + 1, dtype=np.uint8),
        )


def _register_folder(window: MainWindow, folder: Path) -> list[str]:
    return window._register_inputs(discover_image_inputs((folder,)), select_all=False)


def test_foreground_finishes_before_exactly_one_next_position_preloads(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "foreground-first"
    _write_images(folder, 3)
    foreground_started = Event()
    foreground_release = Event()
    preload_started = Event()

    class ControlledWorker(TaskWorker):
        def __init__(self, path: Path, *_args: object, **_kwargs: object) -> None:
            source_path = Path(path)

            def decode() -> ImageDocument:
                if source_path.name == "frame-1.png":
                    foreground_started.set()
                    foreground_release.wait(2)
                elif source_path.name == "frame-2.png":
                    preload_started.set()
                return ImageDocument.from_array(
                    np.ones((2, 2), dtype=np.uint8),
                    source_path.name,
                    source_path=source_path,
                )

            super().__init__(decode)

    monkeypatch.setattr(main_window_module, "ImageLoadWorker", ControlledWorker)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    ids = _register_folder(window, folder)

    qtbot.waitUntil(foreground_started.is_set, timeout=1500)  # type: ignore[attr-defined]
    assert window._load_pool.maxThreadCount() == 2
    assert window._preload_pool.maxThreadCount() == 1
    assert not preload_started.is_set()
    assert not window._preload_workers
    foreground_release.set()
    qtbot.waitUntil(preload_started.is_set, timeout=3000)  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: not window._preload_workers, timeout=3000)  # type: ignore[attr-defined]

    assert window.documents[ids[1]].source is not None
    assert window.documents[ids[2]].source is None
    assert window.preload_controller.current_plan is not None
    assert window.preload_controller.current_plan.document_ids == (ids[1],)


def test_single_folder_preload_is_reused_without_normal_redecode(
    qtbot: object, tmp_path: Path
) -> None:
    folder = tmp_path / "reuse"
    _write_images(folder, 3)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    ids = _register_folder(window, folder)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window._workers
        and not window._preload_workers
        and window.documents[ids[1]].source is not None,
        timeout=5000,
    )
    token_before = window._load_tokens.get(ids[1], 0)

    window.next_folder_position()

    assert window.selected_documents[0].document_id == ids[1]
    assert window.documents[ids[1]].source is not None
    assert window._load_tokens.get(ids[1], 0) == token_before
    next_plan = window._plan_folder_navigation(1)
    assert next_plan is not None
    assert next_plan.document_ids == (ids[2],)


def test_normal_navigation_does_not_wait_for_obsolete_preload_and_wins_authority(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "priority"
    _write_images(folder, 3)
    speculative_started = Event()
    speculative_release = Event()
    calls: dict[str, int] = {}
    lock = Lock()

    class ControlledWorker(TaskWorker):
        def __init__(self, path: Path, *_args: object, **_kwargs: object) -> None:
            source_path = Path(path)
            with lock:
                call_index = calls.get(source_path.name, 0)
                calls[source_path.name] = call_index + 1

            def decode() -> ImageDocument:
                value = 1
                if source_path.name == "frame-2.png" and call_index == 0:
                    speculative_started.set()
                    speculative_release.wait(3)
                    value = 111
                elif source_path.name == "frame-2.png":
                    value = 222
                return ImageDocument.from_array(
                    np.full((2, 2), value, dtype=np.uint8),
                    source_path.name,
                    source_path=source_path,
                )

            super().__init__(decode)

        def cancel(self) -> None:
            """Model a decoder that cannot stop after cancellation is requested."""

            return

    monkeypatch.setattr(main_window_module, "ImageLoadWorker", ControlledWorker)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    ids = _register_folder(window, folder)
    qtbot.waitUntil(speculative_started.is_set, timeout=3000)  # type: ignore[attr-defined]

    window.next_folder_position()
    replacement_plan = window.preload_controller.current_plan
    assert replacement_plan is not None
    assert replacement_plan.document_ids == (ids[2],)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[ids[1]].source is not None
        and int(window.documents[ids[1]].source[0, 0]) == 222,
        timeout=3000,
    )
    assert window._preload_workers
    speculative_release.set()
    qtbot.waitUntil(lambda: not window._preload_workers, timeout=4000)  # type: ignore[attr-defined]

    loaded = window.documents[ids[1]]
    assert loaded.source is not None
    assert int(loaded.source[0, 0]) == 222
    diagnostics = window.preload_controller.diagnostics
    assert diagnostics.cancellation_request_count >= 1
    assert diagnostics.stale_drop_count >= 1


def test_preload_uses_ordinary_residency_and_may_be_evicted_without_loop(
    qtbot: object, tmp_path: Path
) -> None:
    folder = tmp_path / "budget"
    _write_images(folder, 2, shape=(2, 2))
    performance = PerformanceSettings(
        difference_cache_bytes=8,
        source_residency_bytes=4,
        preload_enabled=True,
    )
    window = MainWindow(ApplicationSettings(), performance)
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    ids = _register_folder(window, folder)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window._workers and not window._preload_workers,
        timeout=5000,
    )
    qtbot.wait(50)  # type: ignore[attr-defined]

    assert window.documents[ids[0]].source is not None
    assert window.documents[ids[1]].source is None
    assert window.documents[ids[1]].loading_state == "pending"
    assert window.preload_controller.pending_document_ids == ()
    assert window.preload_controller.diagnostics.successful_retained_count == 0
    assert window.residency_manager.used_bytes == 4


def test_disabled_runtime_starts_no_preload_but_navigation_is_unchanged(
    qtbot: object, tmp_path: Path
) -> None:
    folder = tmp_path / "disabled"
    _write_images(folder, 2)
    application = ApplicationSettings(preload_enabled=False)
    window = MainWindow(application, application.performance_settings())
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    ids = _register_folder(window, folder)
    qtbot.waitUntil(lambda: not window._workers, timeout=3000)  # type: ignore[attr-defined]

    assert not window._preload_workers
    assert window.documents[ids[1]].source is None
    window.next_folder_position()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window._workers and window.documents[ids[1]].source is not None,
        timeout=3000,
    )
    assert window.selected_documents[0].document_id == ids[1]


def _raw_profile(width: int = 4, height: int = 2) -> RawProfile:
    return RawProfile(
        name="preload-raw",
        width=width,
        height=height,
        stride_bytes=width * 2,
        container_dtype="uint16",
        endianness="little",
        bit_depth=12,
        bit_alignment="lsb",
        channel_layout="GRAY",
        white_level=4095,
    )


def test_raw_preload_reuses_registered_profile_without_dialog(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "raw-valid"
    folder.mkdir()
    first_path = folder / "frame-1.png"
    raw_path = folder / "frame-2.raw"
    assert cv2.imwrite(str(first_path), np.ones((2, 4), dtype=np.uint8))
    values = np.arange(8, dtype="<u2").reshape(2, 4)
    raw_path.write_bytes(values.tobytes())
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
    profile = _raw_profile()
    window._raw_profiles[target.document_id] = profile
    monkeypatch.setattr(  # type: ignore[attr-defined]
        main_window_module.QMessageBox,
        "warning",
        lambda *_args, **_kwargs: pytest.fail("preload must not show a warning"),
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        main_window_module.RawOpenDialog,
        "exec",
        lambda *_args, **_kwargs: pytest.fail("preload must not open a RAW dialog"),
    )

    window._select_document_ids([first.document_id])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window._preload_workers
        and window.documents[target.document_id].source is not None,
        timeout=3000,
    )

    loaded = window.documents[target.document_id]
    assert loaded.raw_profile == profile
    assert loaded.source is not None
    assert np.array_equal(loaded.source, values)


def test_raw_preload_exact_size_failure_is_silent_and_retryable(
    qtbot: object, tmp_path: Path
) -> None:
    folder = tmp_path / "raw-exact"
    folder.mkdir()
    first_path = folder / "frame-1.png"
    raw_path = folder / "frame-2.raw"
    assert cv2.imwrite(str(first_path), np.ones((2, 4), dtype=np.uint8))
    raw_path.write_bytes(np.arange(8, dtype="<u2").tobytes() + b"extra")
    application = ApplicationSettings(require_exact_raw_file_size=True)
    window = MainWindow(application, application.performance_settings())
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first = ImageDocument.from_array(
        np.ones((2, 4), dtype=np.uint8),
        first_path.name,
        source_path=first_path,
    )
    target = ImageDocument.pending_document(raw_path)
    window.add_document(first, select=False)
    window.add_document(target, select=False)
    window._raw_profiles[target.document_id] = _raw_profile()

    window._select_document_ids([first.document_id])
    qtbot.waitUntil(lambda: not window._preload_workers, timeout=3000)  # type: ignore[attr-defined]

    assert window.documents[target.document_id] is target
    assert target.source is None
    assert target.loading_state == "pending"
    assert target.error_state is None
    assert window.preload_controller.diagnostics.failure_count == 1


def test_removed_preload_target_is_not_recreated_by_late_result(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "removed"
    _write_images(folder, 2)
    started = Event()
    release = Event()

    class BlockingWorker(TaskWorker):
        def __init__(self, path: Path, *_args: object, **_kwargs: object) -> None:
            source_path = Path(path)

            def decode() -> ImageDocument:
                if source_path.name == "frame-2.png":
                    started.set()
                    release.wait(3)
                return ImageDocument.from_array(
                    np.ones((2, 2), dtype=np.uint8),
                    source_path.name,
                    source_path=source_path,
                )

            super().__init__(decode)

        def cancel(self) -> None:
            """Model a decoder that completes after an advisory cancellation."""

            return

    monkeypatch.setattr(main_window_module, "ImageLoadWorker", BlockingWorker)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    ids = _register_folder(window, folder)
    qtbot.waitUntil(started.is_set, timeout=3000)  # type: ignore[attr-defined]

    window._remove_document_ids([ids[1]])
    release.set()
    qtbot.waitUntil(lambda: not window._preload_workers, timeout=4000)  # type: ignore[attr-defined]

    assert ids[1] not in window.documents
    assert window.document_list.document_item(ids[1]) is None
    assert window.preload_controller.diagnostics.stale_drop_count >= 1


def test_raw_profile_and_generation_change_rejects_old_preload_result(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "raw-generation"
    folder.mkdir()
    first_path = folder / "frame-1.png"
    raw_path = folder / "frame-2.raw"
    assert cv2.imwrite(str(first_path), np.ones((2, 4), dtype=np.uint8))
    raw_path.write_bytes(np.arange(8, dtype="<u2").tobytes())
    old_started = Event()
    old_release = Event()
    calls = 0

    class ProfileRaceWorker(TaskWorker):
        def __init__(
            self,
            path: Path,
            raw_profile: RawProfile | None = None,
            **_kwargs: object,
        ) -> None:
            nonlocal calls
            source_path = Path(path)
            call_index = calls
            calls += 1

            def decode() -> ImageDocument:
                value = 10
                if source_path.suffix.casefold() == ".raw" and call_index == 0:
                    old_started.set()
                    old_release.wait(3)
                    value = 111
                elif source_path.suffix.casefold() == ".raw":
                    value = 222
                return ImageDocument.from_array(
                    np.full((2, 4), value, dtype=np.uint16),
                    source_path.name,
                    source_path=source_path,
                    channel_layout=raw_profile.channel_layout if raw_profile else "GRAY",
                    bit_depth=raw_profile.bit_depth if raw_profile else 16,
                    raw_profile=raw_profile,
                )

            super().__init__(decode)

        def cancel(self) -> None:
            return

    monkeypatch.setattr(main_window_module, "ImageLoadWorker", ProfileRaceWorker)
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
    old_profile = _raw_profile()
    window._raw_profiles[target.document_id] = old_profile
    window._select_document_ids([first.document_id])
    qtbot.waitUntil(old_started.is_set, timeout=3000)  # type: ignore[attr-defined]

    new_profile = old_profile.copy(update={"name": "new-profile", "white_level": 2047})
    window._raw_profiles[target.document_id] = new_profile
    window._mark_raw_for_reload(target.document_id, new_profile)
    changed_generation = target.generation
    window.next_folder_position()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[target.document_id].source is not None
        and int(window.documents[target.document_id].source[0, 0]) == 222,
        timeout=3000,
    )
    old_release.set()
    qtbot.waitUntil(lambda: not window._preload_workers, timeout=4000)  # type: ignore[attr-defined]

    loaded = window.documents[target.document_id]
    assert loaded.source is not None
    assert int(loaded.source[0, 0]) == 222
    assert loaded.generation == changed_generation
    assert loaded.raw_profile == new_profile
    assert window.preload_controller.diagnostics.stale_drop_count >= 1
