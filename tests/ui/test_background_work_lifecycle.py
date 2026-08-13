from __future__ import annotations

from threading import Event, Lock, get_ident

import numpy as np
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

import pixelscope.ui.difference_panel as difference_panel_module
import pixelscope.ui.image_viewer as image_viewer_module
import pixelscope.workers.thread_pools as thread_pools_module
from pixelscope.app.main_window import MainWindow
from pixelscope.core.difference_cache import CachedDifferenceMap
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.difference_panel import DifferencePanel


def _rgb(value: int, name: str) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((16, 20, 3), value, dtype=np.uint8),
        name,
    )


def _cache_current_difference(panel: DifferencePanel) -> CachedDifferenceMap:
    key = panel._cache_key()
    assert key is not None
    cached = CachedDifferenceMap(
        absolute=np.full((16, 20, 3), 5, dtype=np.uint8),
        domain="native",
        data_range=255.0,
        channel_layout="RGB",
        bayer_pattern=None,
    )
    assert panel.difference_cache.put(key, cached).stored
    return cached


def test_difference_panel_uses_app_owned_bounded_analysis_pool(qtbot: object) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    pool = thread_pools_module.analysis_thread_pool()

    assert panel._pool is pool
    assert pool is not QThreadPool.globalInstance()
    assert pool.parent() is app
    assert pool.maxThreadCount() == thread_pools_module.ANALYSIS_MAX_THREADS
    assert bool(
        getattr(
            app,
            thread_pools_module._BACKGROUND_POOL_SHUTDOWN_HOOK_ATTRIBUTE,
            False,
        )
    )


def test_difference_preview_runs_off_gui_thread_and_drops_stale_result(
    qtbot: object,
    monkeypatch: object,
) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = _rgb(10, "a.png")
    second = _rgb(15, "b.png")
    panel.set_documents([first, second], (first.document_id, second.document_id))
    _cache_current_difference(panel)

    first_started = Event()
    first_release = Event()
    calls: list[tuple[float, int]] = []
    calls_lock = Lock()
    main_thread_id = get_ident()

    def render(absolute: np.ndarray, gain: float) -> np.ndarray:
        with calls_lock:
            calls.append((gain, get_ident()))
        if gain == 2.0:
            first_started.set()
            first_release.wait(3)
        return np.full(absolute.shape, int(gain), dtype=np.uint8)

    monkeypatch.setattr(  # type: ignore[attr-defined]
        difference_panel_module,
        "render_absolute_difference",
        render,
    )
    emitted: list[np.ndarray] = []
    panel.preview_updated.connect(lambda _title, _numerical, preview: emitted.append(preview))

    panel.gain.setValue(2)
    panel._display_timer.stop()
    panel._apply_display_update()
    qtbot.waitUntil(first_started.is_set, timeout=3000)  # type: ignore[attr-defined]

    panel.gain.setValue(3)
    panel._display_timer.stop()
    panel._apply_display_update()
    first_release.set()

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: bool(emitted) and panel._preview_worker is None,
        timeout=4000,
    )

    assert len(emitted) == 1
    assert np.all(emitted[0] == 3)
    assert calls
    assert all(thread_id != main_thread_id for _gain, thread_id in calls)
    panel.shutdown()


def test_display_gain_pool_is_bounded_and_uses_app_shutdown_hook(qtbot: object) -> None:
    del qtbot
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    analysis_pool = thread_pools_module.analysis_thread_pool()
    display_pool = image_viewer_module._display_preview_thread_pool()

    assert analysis_pool.parent() is app
    assert display_pool.parent() is app
    assert display_pool.maxThreadCount() == image_viewer_module._DISPLAY_PREVIEW_MAX_THREADS
    assert bool(
        getattr(
            app,
            thread_pools_module._BACKGROUND_POOL_SHUTDOWN_HOOK_ATTRIBUTE,
            False,
        )
    )
    assert thread_pools_module.shutdown_background_thread_pools(100)


def test_preload_and_load_pools_remain_independent_from_analysis_pool(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    analysis_pool = thread_pools_module.analysis_thread_pool()

    assert window._load_pool.maxThreadCount() == 2
    assert window._preload_pool.maxThreadCount() == 1
    assert analysis_pool.maxThreadCount() == thread_pools_module.ANALYSIS_MAX_THREADS
    assert window.comparison_analysis_panel._pool is analysis_pool
    assert window.difference_panel._pool is analysis_pool
    assert analysis_pool is not window._load_pool
    assert analysis_pool is not window._preload_pool
    assert image_viewer_module._display_preview_thread_pool().maxThreadCount() == 2
    assert thread_pools_module.shutdown_background_thread_pools(100)
