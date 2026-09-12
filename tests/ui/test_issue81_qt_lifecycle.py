from __future__ import annotations

import gc
from collections.abc import Callable
from pathlib import Path
from threading import Event, get_ident
from weakref import ref

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QThreadPool
from PySide6.QtWidgets import QApplication

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow


def _blocked_loader(started: Event, release: Event) -> Callable[[Path | str], object]:
    def load(_path: Path | str) -> object:
        started.set()
        release.wait(timeout=3.0)
        return object()

    return load


def test_running_iqa_loader_can_finish_after_window_destruction_without_cross_thread_qobject_delete(
    qtbot: object,
    isolated_qsettings_subdirectory: None,
) -> None:
    del qtbot
    del isolated_qsettings_subdirectory
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    pool = QThreadPool(app)
    pool.setMaxThreadCount(2)
    gui_thread_id = get_ident()

    for _iteration in range(10):
        started = Event()
        release = Event()
        signal_destruction_threads: list[int] = []
        window = MainWindow(iqa_result_pool=pool)
        _compose_main_window_presentation(window)
        controller = window.iqa_controller
        controller._loader = _blocked_loader(started, release)
        controller.open_result(Path("diagnostic-result"))
        assert started.wait(timeout=1.0)
        worker = controller._worker
        assert worker is not None
        assert worker.autoDelete()
        assert worker.signals.parent() is app
        worker.signals.destroyed.connect(
            lambda *_args, threads=signal_destruction_threads: threads.append(get_ident()),
            Qt.ConnectionType.DirectConnection,
        )
        controller_ref = ref(controller)
        worker_ref = ref(worker)

        window.close()
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        del worker
        del controller
        del window
        # Deliberately force the exact Issue #81 race inside this stress test;
        # this is not general test-boundary cleanup or a passing precondition.
        gc.collect()

        assert controller_ref() is None
        assert worker_ref() is not None
        assert pool.activeThreadCount() == 1
        release.set()
        assert pool.waitForDone(3000)
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()

        assert signal_destruction_threads == [gui_thread_id]
        assert worker_ref() is None
