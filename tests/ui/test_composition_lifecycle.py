from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from pixelscope.app.composition_lifecycle import (
    CompositionLifecycleController,
    install_composition_lifecycle,
    register_composed_teardown,
)


class _Owner:
    def __init__(self, name: str, events: list[str], *, fail: bool = False) -> None:
        self.name = name
        self.events = events
        self.fail = fail
        self.shutdown_calls = 0

    def shutdown(self) -> None:
        self.shutdown_calls += 1
        self.events.append(self.name)
        if self.fail:
            raise RuntimeError(f"{self.name} failed")


def test_composition_lifecycle_is_singleton_per_window(qtbot: Any) -> None:
    window = QWidget()
    qtbot.addWidget(window)

    first = install_composition_lifecycle(window)
    second = install_composition_lifecycle(window)

    assert isinstance(first, CompositionLifecycleController)
    assert second is first
    assert first.parent() is window


def test_composition_lifecycle_drains_in_lifo_order(qtbot: Any) -> None:
    window = QWidget()
    qtbot.addWidget(window)
    events: list[str] = []
    first = _Owner("first", events)
    second = _Owner("second", events)
    third = _Owner("third", events)

    register_composed_teardown(window, first)
    register_composed_teardown(window, second)
    register_composed_teardown(window, third)

    lifecycle = install_composition_lifecycle(window)
    assert lifecycle.pending_count == 3

    window.show()
    window.close()

    assert events == ["third", "second", "first"]
    assert lifecycle.pending_count == 0
    assert lifecycle.closed


def test_composition_lifecycle_shutdown_is_idempotent(qtbot: Any) -> None:
    window = QWidget()
    qtbot.addWidget(window)
    events: list[str] = []
    owner = _Owner("owner", events)

    register_composed_teardown(window, owner)
    lifecycle = install_composition_lifecycle(window)

    lifecycle.shutdown()
    lifecycle.shutdown()
    window.close()

    assert events == ["owner"]
    assert owner.shutdown_calls == 1


def test_composition_lifecycle_continues_after_owner_failure(
    qtbot: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    window = QWidget()
    qtbot.addWidget(window)
    events: list[str] = []
    first = _Owner("first", events)
    failing = _Owner("failing", events, fail=True)
    last = _Owner("last", events)

    register_composed_teardown(window, first)
    register_composed_teardown(window, failing)
    register_composed_teardown(window, last)

    install_composition_lifecycle(window).shutdown()

    assert events == ["last", "failing", "first"]
    assert "Composition teardown failed" in caplog.text


def test_composition_lifecycle_rejects_missing_callback(qtbot: Any) -> None:
    window = QWidget()
    qtbot.addWidget(window)
    owner = QObject()

    with pytest.raises(TypeError, match="has no callable"):
        register_composed_teardown(window, owner)


def test_composition_lifecycle_rejects_registration_after_shutdown(qtbot: Any) -> None:
    window = QWidget()
    qtbot.addWidget(window)
    events: list[str] = []
    owner = _Owner("owner", events)
    lifecycle = install_composition_lifecycle(window)
    lifecycle.shutdown()

    with pytest.raises(RuntimeError, match="already closed"):
        lifecycle.register(owner)
