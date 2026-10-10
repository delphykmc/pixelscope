"""UX-3E E1: native Qt acceptance in an isolated Windows pytest process.

No private model/server data; no runtime screenshot pixel assertions; no
PUBLIC MAIN modification. Keep native Qt tests outside routine hosted CI.
"""

from __future__ import annotations

import gc
from concurrent.futures import Future
from pathlib import Path
from threading import Thread

import pytest
from PySide6.QtCore import QByteArray, QSettings
from PySide6.QtWidgets import QApplication, QMainWindow

from pixelscope_enterprise.iqa.analysis_window import AnalysisWindowManager
from pixelscope_enterprise.iqa.composition import IqaJobSnapshot, IqaWindowContribution
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


def test_running_spatial_future_quiesces_on_manager_shutdown(
    qtbot: object, tmp_path: Path
) -> None:
    """A RUNNING Future can complete after close without refreshing disposed UI."""

    path = tmp_path / "busy-close.ini"

    def factory() -> QSettings:
        return _settings_factory(path)

    manager = AnalysisWindowManager(settings_factory=factory)
    window = manager.show()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    running: Future[tuple[()]] = Future()
    assert running.set_running_or_notify_cancel()
    assert running.running()
    assert not running.cancel()
    # The Future has already entered RUNNING, so shutdown cannot cancel it.
    # This exercises late completion without launching an unbounded CPU scan.
    window._spatial_future = running  # type: ignore[assignment]
    window._spatial_pending = ("synthetic", "synthetic_attr", 128)
    late_timer_events: list[str] = []
    window._spatial_timer.timeout.connect(  # type: ignore[attr-defined]
        lambda: late_timer_events.append("stale polling")
    )
    window._spatial_timer.start()
    assert window._spatial_timer.isActive()

    manager.shutdown()
    assert manager.window is None
    assert running.running() and not running.cancelled()
    assert window._spatial_future is None
    assert window._spatial_pending is None
    assert not window._spatial_timer.isActive()

    # Simulate the in-flight computation finishing only after the owner closed.
    running.set_result(())
    assert running.done() and not running.cancelled()
    qtbot.wait(100)  # type: ignore[attr-defined]
    # Qt may have already executed deleteLater; only examine Python-owned
    # observations after pumping the event loop, never disposed Qt wrappers.
    assert not late_timer_events
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

    def intersects_screen() -> bool:
        bounds = window.frameGeometry()
        return any(
            bounds.intersected(screen.availableGeometry()).width() >= 100
            and bounds.intersected(screen.availableGeometry()).height() >= 100
            for screen in QApplication.screens()
        )

    if intersects_screen():
        manager.shutdown()
        pytest.skip("Qt or the window manager clamps off-screen geometry on move")
    # Capture exactly the blob produced while the source window is off-screen.
    # The test must not PASS by reopening a window whose geometry was never invalid.
    offscreen_blob = QByteArray(window.saveGeometry())
    window.close()
    saved_settings = factory()
    saved_settings.sync()
    stored = saved_settings.value("analysis_window_geometry")
    assert isinstance(stored, QByteArray | bytes), "No saved native window geometry"
    assert bytes(stored) == bytes(offscreen_blob), "Off-screen geometry was not persisted"
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


def test_worker_queued_terminal_during_host_shutdown_cannot_mutate_ui(
    qtbot: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An actual worker queues completion, then the host shuts down before Qt delivery."""

    host = QMainWindow()
    qtbot.addWidget(host)  # type: ignore[attr-defined]
    contribution = IqaWindowContribution()
    contribution.prepare(host)
    contribution.install_dock(host)
    contribution.install_runtime(host)
    host.show()
    qtbot.waitUntil(host.isVisible, timeout=5000)  # type: ignore[attr-defined]

    # One known active job makes accidental late publication observable.
    contribution.publish_job(IqaJobSnapshot("shutdown-race", "Before close", "running"))
    assert contribution.jobs_list is not None
    assert contribution.jobs_list.count() == 1
    assert contribution.jobs_status_button is not None
    assert "running" in contribution.jobs_status_button.text()
    deliveries: list[str] = []
    original_publish = contribution.publish_job

    def record_delivery(snapshot: IqaJobSnapshot) -> None:
        deliveries.append(snapshot.status)
        original_publish(snapshot)

    monkeypatch.setattr(contribution, "publish_job", record_delivery)
    errors: list[Exception] = []

    def worker() -> None:
        try:
            contribution.post_job(
                IqaJobSnapshot(
                    "shutdown-race",
                    "Late verified result",
                    "completed",
                    make_synthetic_result("not-delivered"),
                )
            )
        except Exception as error:  # noqa: BLE001 - assert worker errors on owner thread
            errors.append(error)

    thread = Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert not errors
    # QueuedConnection has not delivered while the GUI thread was blocked.
    assert deliveries == []
    assert contribution._records["shutdown-race"].status == "running"

    contribution.shutdown()
    assert contribution._closed
    assert contribution.manager.window is None
    assert not contribution._records
    assert contribution.jobs_list.count() == 1
    assert "running" in contribution.jobs_list.item(0).text()
    assert contribution.jobs_status_button.isHidden()
    with pytest.raises(RuntimeError, match="not available"):
        contribution.post_job(IqaJobSnapshot("late-again", "No host", "queued"))

    # Pump pending Qt signal, deferred deletes and normal GC after shutdown.
    qtbot.wait(100)  # type: ignore[attr-defined]
    gc.collect()
    assert deliveries == []
    assert contribution.jobs_list.count() == 1
    assert "running" in contribution.jobs_list.item(0).text()
    assert contribution.jobs_status_button.isHidden()
    assert contribution.manager.window is None
    assert not contribution._records
    host.close()
