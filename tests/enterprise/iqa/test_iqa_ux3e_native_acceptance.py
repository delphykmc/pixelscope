"""UX-3E E1: native Qt acceptance in an isolated Windows pytest process.

No private model/server data; no runtime screenshot pixel assertions; no
PUBLIC MAIN modification. Keep native Qt tests outside routine hosted CI.
"""

from __future__ import annotations

import gc
from concurrent.futures import Future
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from pixelscope_enterprise.iqa.analysis_window import AnalysisWindowManager
from pixelscope_enterprise.iqa.demo import make_synthetic_result


def _settings_factory(path: Path) -> QSettings:
    return QSettings(str(path), QSettings.Format.IniFormat)


@pytest.mark.parametrize("cycle_count", [3])
def test_repeated_analysis_show_hide_close_and_normal_gc(
    qtbot: object, tmp_path: Path, cycle_count: int
) -> None:
    """Closing a child window does not shut down its manager; explicit shutdown does."""

    path = tmp_path / "normal-gc-analysis.ini"

    def factory() -> QSettings:
        return _settings_factory(path)

    result = make_synthetic_result("ux3e-native-lifecycle")
    for _ in range(cycle_count):
        manager = AnalysisWindowManager(settings_factory=factory)
        window = manager.show(result)
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        qtbot.waitUntil(window.isVisible, timeout=5000)  # type: ignore[attr-defined]
        assert window.active_result_id == result.result_id
        assert manager.show() is window

        window.hide()
        assert manager.show() is window
        assert window.isVisible()
        window.close()
        assert not window.isVisible()
        assert manager.show() is window  # Reopening is not a new top-level owner.
        assert window.active_result_id == result.result_id

        manager.shutdown()
        manager.shutdown()  # Idempotent even when deleteLater has been queued.
        assert manager.window is None
        with pytest.raises(RuntimeError, match="shut down"):
            manager.show()
        qtbot.wait(20)  # type: ignore[attr-defined]
        gc.collect()


def test_pending_spatial_future_quiesces_on_manager_shutdown(
    qtbot: object, tmp_path: Path
) -> None:
    """Do not dispatch a stale spatial completion into an already closing window."""

    path = tmp_path / "busy-close.ini"

    def factory() -> QSettings:
        return _settings_factory(path)

    manager = AnalysisWindowManager(settings_factory=factory)
    window = manager.show()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    pending: Future[tuple[()]] = Future()
    # Deliberately incomplete future: this exercises shutdown without running
    # a nondeterministic heavy spatial scan or assuming proprietary metrics.
    window._spatial_future = pending  # type: ignore[assignment]
    window._spatial_pending = ("synthetic", "synthetic_attr", 128)
    window._spatial_timer.start()
    assert window._spatial_timer.isActive()

    manager.shutdown()
    assert manager.window is None
    assert pending.cancelled()
    assert window._spatial_future is None
    assert window._spatial_pending is None
    assert not window._spatial_timer.isActive()
    qtbot.wait(80)  # type: ignore[attr-defined]
    gc.collect()


def test_offscreen_saved_geometry_falls_back_into_available_screen(
    qtbot: object, tmp_path: Path
) -> None:
    """A disconnected secondary-monitor geometry must not strand the IQA window."""

    screens = QApplication.screens()
    if not screens:
        pytest.skip("Qt platform exposes no screens")
    path = tmp_path / "removed-monitor.ini"

    def factory() -> QSettings:
        return _settings_factory(path)

    manager = AnalysisWindowManager(settings_factory=factory)
    window = manager.show()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.move(-50000, -50000)
    window.close()
    factory().sync()
    manager.shutdown()
    qtbot.wait(20)  # type: ignore[attr-defined]

    reopened = AnalysisWindowManager(settings_factory=factory)
    restored = reopened.show()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    qtbot.waitUntil(restored.isVisible, timeout=5000)  # type: ignore[attr-defined]
    geometry = restored.frameGeometry()
    assert any(
        geometry.intersected(screen.availableGeometry()).width() >= 100
        and geometry.intersected(screen.availableGeometry()).height() >= 100
        for screen in QApplication.screens()
    )
    reopened.shutdown()
    qtbot.wait(20)  # type: ignore[attr-defined]
    gc.collect()
