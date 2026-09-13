from __future__ import annotations

import gc
from collections.abc import Callable
from pathlib import Path
from threading import Event, get_ident
from types import SimpleNamespace
from weakref import ref

import numpy as np
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QThreadPool
from PySide6.QtWidgets import QApplication

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.roi import RoiBounds, analyze_roi
from pixelscope.ui.comparison_analysis_panel import ComparisonAnalysisPanel


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


def test_comparison_analysis_shutdown_releases_pyqtgraph_resources(
    qtbot: object,
) -> None:
    del qtbot
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    panel = ComparisonAnalysisPanel()
    panel_ref = ref(panel)
    scenes = tuple(plot.scene() for plot in panel.plots)
    view_boxes = tuple(plot.getViewBox() for plot in panel.plots)

    # Runtime context-menu behavior remains available until final shutdown.
    assert len(scenes) == 6
    assert len(view_boxes) == 6
    assert all(getattr(view_box, "menu", None) is not None for view_box in view_boxes)

    panel.shutdown()
    panel.shutdown()

    assert panel._histogram_resources_disposed
    assert panel._histogram_mouse_callbacks == []
    assert panel.plots == []
    assert panel.legends == []
    assert panel.plot is None
    assert panel.legend is None
    assert all(getattr(view_box, "menu", None) is None for view_box in view_boxes)

    panel.close()
    panel.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    del panel

    # Keep the scenes alive deliberately: if PixelScope's mouse callbacks were
    # still connected, their bound partials would retain the panel wrapper.
    assert panel_ref() is None

    del scenes
    del view_boxes
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def test_comparison_analysis_shutdown_rejects_late_worker_result(
    qtbot: object,
) -> None:
    del qtbot
    panel = ComparisonAnalysisPanel()
    signature = ("late-result",)
    document = SimpleNamespace(statistics_cache={})
    result = analyze_roi(
        np.zeros((2, 2), dtype=np.uint8),
        RoiBounds(0, 0, 2, 2),
        bins=2,
        histogram_range=(0.0, 2.0),
    )
    rendered: list[object] = []

    panel._documents = [document]  # type: ignore[list-item]
    panel._request_signature = signature
    panel._render = lambda *args: rendered.append(args)  # type: ignore[method-assign]

    panel.shutdown()

    # Cancellation is advisory: a worker that was already running may still
    # queue succeeded after final UI disposal. Late results must become inert.
    panel._on_result(
        signature,
        [("late-result",)],
        [(2, (0.0, 2.0))],
        (result,),
    )

    assert rendered == []
    assert document.statistics_cache == {}
    assert panel.last_results == ()

    panel.close()
    panel.deleteLater()
