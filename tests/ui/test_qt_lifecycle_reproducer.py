from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PySide6.QtCore import QObject, QThreadPool, Qt, Slot
from PySide6.QtWidgets import QApplication

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.workers.task_worker import TaskError, TaskWorker

_REPRO_ENABLED = os.environ.get("PIXELSCOPE_QT_LIFECYCLE_REPRO") == "1"
pytestmark = pytest.mark.skipif(
    not _REPRO_ENABLED,
    reason="diagnostic reproducer; set PIXELSCOPE_QT_LIFECYCLE_REPRO=1",
)


class _WorkerResultReceiver(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.done = False
        self.value: object | None = None
        self.error: TaskError | None = None

    @Slot(str, object, int, object)
    def succeeded(
        self,
        _task_id: str,
        _document_id: object,
        _generation: int,
        value: object,
    ) -> None:
        self.value = value
        self.done = True

    @Slot(str, object, int, object)
    def failed(
        self,
        _task_id: str,
        _document_id: object,
        _generation: int,
        error: object,
    ) -> None:
        if isinstance(error, TaskError):
            self.error = error
        self.done = True


def _build_zip_payload() -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index in range(48):
            payload = bytes(((index + offset) & 0xFF) for offset in range(32 * 1024))
            archive.writestr(f"payload/{index:03d}.bin", payload)
    return stream.getvalue()


def _allocation_heavy_worker(zip_path: Path) -> tuple[int, int]:
    # Keep this workload deterministic but allocation-heavy. Arrays are deliberately
    # local to the pool thread so their Python/NumPy references are also released there.
    checksum = 0
    for index in range(8):
        array = np.arange(1024 * 1024, dtype=np.uint32).reshape(1024, 1024)
        shifted = np.roll(array, index + 1, axis=index % 2)
        checksum ^= int(shifted[index * 17, index * 29])

    total_bytes = 0
    with zipfile.ZipFile(zip_path, "r") as archive:
        for name in archive.namelist():
            data = archive.read(name)
            total_bytes += len(data)
            checksum ^= data[(len(data) // 2) % len(data)]
    return checksum, total_bytes


def test_00_heavy_qt_widget_tree_teardown(qtbot: Any) -> None:
    """Phase A: build and tear down the production-scale Qt widget tree.

    Do not manually drain DeferredDelete or force GC here. The reproducer intentionally
    relies on normal pytest-qt test-boundary cleanup before phase B starts.
    """

    window = MainWindow()
    qtbot.addWidget(window)
    _compose_main_window_presentation(window)
    window.show()

    window._set_plots_visible(True)
    window.iqa_workspace_action.trigger()
    qtbot.waitUntil(window.bottom_dock.isVisible, timeout=3000)
    qtbot.waitUntil(window.iqa_dock.isVisible, timeout=3000)

    # Realize the heavier plot/IQA trees and their dock/title-bar relationships.
    window.bottom_dock.setFloating(True)
    window.iqa_dock.setFloating(True)
    qtbot.waitUntil(window.bottom_dock.isFloating, timeout=3000)
    qtbot.waitUntil(window.iqa_dock.isFloating, timeout=3000)

    window.close()
    assert not window.isVisible()


def test_01_background_worker_after_heavy_qt_teardown(qtbot: Any, tmp_path: Path) -> None:
    """Phase B: immediately start allocation-heavy pooled work and await queued delivery."""

    app = QApplication.instance()
    assert isinstance(app, QApplication)

    zip_path = tmp_path / "lifecycle-pressure.zip"
    zip_path.write_bytes(_build_zip_payload())

    pool = QThreadPool(app)
    pool.setMaxThreadCount(1)
    receiver = _WorkerResultReceiver()
    worker = TaskWorker(_allocation_heavy_worker, zip_path)
    worker.signals.succeeded.connect(
        receiver.succeeded,
        Qt.ConnectionType.QueuedConnection,
    )
    worker.signals.failed.connect(
        receiver.failed,
        Qt.ConnectionType.QueuedConnection,
    )

    pool.start(worker)
    qtbot.waitUntil(lambda: receiver.done, timeout=15_000)
    assert receiver.error is None
    assert isinstance(receiver.value, tuple)
    assert len(receiver.value) == 2
    assert pool.waitForDone(5000)
