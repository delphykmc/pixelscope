from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pixelscope.app.application as application_module
import pixelscope.workers.thread_pools as thread_pools_module


def test_fresh_pool_registration_preserves_shutdown_clear_wait_order(
    monkeypatch: Any,
) -> None:
    events: list[str] = []

    class FakeSignal:
        def __init__(self) -> None:
            self.slots: list[Any] = []

        def connect(self, slot: Any) -> None:
            self.slots.append(slot)

        def emit(self) -> None:
            for slot in self.slots:
                slot()

    class FakeApplication:
        current: FakeApplication

        def __init__(self) -> None:
            self.aboutToQuit = FakeSignal()

        @classmethod
        def instance(cls) -> FakeApplication:
            return cls.current

    class FakePool:
        labels = iter(("analysis",))

        def __init__(self, _parent: object) -> None:
            self.label = next(self.labels)

        def setMaxThreadCount(self, _count: int) -> None:
            pass

        def clear(self) -> None:
            events.append(f"{self.label}:clear")

        def waitForDone(self, timeout_ms: int) -> bool:
            events.append(f"{self.label}:wait:{timeout_ms}")
            return True

    app = FakeApplication()
    FakeApplication.current = app
    monkeypatch.setattr(thread_pools_module, "QApplication", FakeApplication)
    monkeypatch.setattr(thread_pools_module, "QThreadPool", FakePool)

    thread_pools_module.analysis_thread_pool()

    assert app.aboutToQuit.slots == [
        thread_pools_module.shutdown_background_thread_pools,
    ]
    app.aboutToQuit.emit()
    assert events == [
        "analysis:clear",
        "analysis:wait:3000",
    ]


def test_main_runs_core_only_after_local_pool_initialization(monkeypatch: Any) -> None:
    events: list[str] = []
    repository = object()
    application_settings = object()
    performance_settings = object()
    icon = object()
    window = SimpleNamespace(
        setWindowIcon=lambda value: events.append(f"icon:{value is icon}"),
        show=lambda: events.append("show"),
    )
    app = SimpleNamespace(windowIcon=lambda: icon, exec=lambda: 17)

    def build_window(
        application_settings_arg: object,
        performance_settings_arg: object,
        repository_arg: object,
        *,
        window_contributions: tuple[object, ...],
    ) -> object:
        assert application_settings_arg is application_settings
        assert performance_settings_arg is performance_settings
        assert repository_arg is repository
        assert window_contributions == ()
        events.append("window")
        return window

    def compose(window_arg: object) -> None:
        assert window_arg is window
        events.append("compose")

    monkeypatch.setattr(application_module, "create_application", lambda _args: app)
    monkeypatch.setattr(
        application_module,
        "load_startup_settings",
        lambda: (repository, application_settings, performance_settings),
    )
    monkeypatch.setattr(
        application_module,
        "analysis_thread_pool",
        lambda: events.append("analysis_pool"),
    )
    monkeypatch.setattr(application_module, "MainWindow", build_window)
    monkeypatch.setattr(application_module, "compose_main_window_presentation", compose)

    assert application_module.main([]) == 17
    assert events == [
        "analysis_pool",
        "window",
        "compose",
        "icon:True",
        "show",
    ]
