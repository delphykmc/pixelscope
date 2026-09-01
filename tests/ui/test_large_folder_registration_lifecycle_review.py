from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication

from pixelscope.app.main_window import MainWindow
from pixelscope.app.registration_controller import install_large_folder_registration
from pixelscope.io.path_discovery import ImageInput

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _flush_zero_timer_callbacks() -> None:
    for _index in range(4):
        QCoreApplication.processEvents()


def test_close_after_first_registration_chunk_rejects_later_callbacks(
    qtbot: object, tmp_path: Path
) -> None:
    folder = tmp_path / "close-during-register"
    folder.mkdir()
    for index in range(6):
        (folder / f"frame{index}.png").write_bytes(b"registered-only")

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(window, chunk_size=2)
    close_counts: list[int] = []

    def close_after_first_chunk(phase: str, completed: int, total: object) -> None:
        if phase == "registering" and completed == 2 and total == 6 and not close_counts:
            close_counts.append(len(window.documents))
            window.close()

    controller.progress_changed.connect(close_after_first_chunk)
    controller.enqueue((folder,))
    qtbot.waitUntil(lambda: bool(close_counts), timeout=3000)  # type: ignore[attr-defined]
    _flush_zero_timer_callbacks()

    assert close_counts == [2]
    assert len(window.documents) == 2
    assert window.document_list.document_count == 2
    assert controller.progress.phase == "idle"
    assert controller.pool.activeThreadCount() == 0


def test_cancel_during_registration_chunk_makes_scheduled_chunk_stale(
    qtbot: object, tmp_path: Path
) -> None:
    folder = tmp_path / "cancel-during-register"
    folder.mkdir()
    for index in range(7):
        (folder / f"frame{index}.png").write_bytes(b"registered-only")

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(window, chunk_size=2)
    cancel_counts: list[int] = []

    def cancel_after_first_chunk(phase: str, completed: int, total: object) -> None:
        if phase == "registering" and completed == 2 and total == 7 and not cancel_counts:
            cancel_counts.append(len(window.documents))
            controller.cancel_active()

    controller.progress_changed.connect(cancel_after_first_chunk)
    controller.enqueue((folder,))
    qtbot.waitUntil(lambda: controller.is_idle, timeout=3000)  # type: ignore[attr-defined]
    _flush_zero_timer_callbacks()

    assert cancel_counts == [2]
    assert len(window.documents) == 2
    assert window.document_list.document_count == 2
    assert controller.progress.phase == "idle"
    window.close()


def test_queued_request_waits_for_first_registration_and_owns_final_selection(
    qtbot: object, tmp_path: Path
) -> None:
    first_folder = tmp_path / "first"
    first_folder.mkdir()
    for index in (3, 1, 2):
        (first_folder / f"image{index}.png").write_bytes(b"registered-only")
    direct = tmp_path / "direct.png"
    assert cv2.imwrite(str(direct), np.full((8, 8), 31, dtype=np.uint8))

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    controller = install_large_folder_registration(window, chunk_size=1)
    registration_order: list[str] = []
    first_chunk_observations: list[bool] = []
    original_register_input = window._register_input

    def observed_register_input(
        image_input: ImageInput,
        *,
        resolve_raw_profile: bool = True,
    ) -> str | None:
        document_id = original_register_input(
            image_input,
            resolve_raw_profile=resolve_raw_profile,
        )
        if document_id is not None:
            registration_order.append(image_input.path.name)
        return document_id

    def observe_first_request(phase: str, completed: int, total: object) -> None:
        if phase == "registering" and completed == 1 and total == 3:
            direct_key = window._path_key(direct)
            first_chunk_observations.append(direct_key not in window._document_id_by_path)

    window._register_input = observed_register_input
    controller.progress_changed.connect(observe_first_request)
    controller.enqueue((first_folder,))
    controller.enqueue((direct,))
    qtbot.waitUntil(lambda: controller.is_idle, timeout=5000)  # type: ignore[attr-defined]

    assert first_chunk_observations == [True]
    assert registration_order == ["image1.png", "image2.png", "image3.png", "direct.png"]
    assert [document.source_path for document in window.selected_documents] == [direct.resolve()]
    qtbot.waitUntil(lambda: not window._workers, timeout=3000)  # type: ignore[attr-defined]
    window.close()
