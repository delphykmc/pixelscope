from __future__ import annotations

import logging
import weakref
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QEvent, QObject

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TeardownEntry:
    owner_ref: weakref.ReferenceType[object]
    method_name: str
    label: str


class CompositionLifecycleController(QObject):
    """Run composed feature teardown in strict reverse installation order."""

    def __init__(self, window: QObject) -> None:
        super().__init__(window)
        self._window_ref = weakref.ref(window)
        self._entries: list[_TeardownEntry] = []
        self._shutting_down = False
        self._closed = False
        window.installEventFilter(self)

    @property
    def pending_count(self) -> int:
        return len(self._entries)

    @property
    def closed(self) -> bool:
        return self._closed

    def register(
        self,
        owner: object,
        *,
        method_name: str = "shutdown",
        label: str | None = None,
    ) -> None:
        """Register one weakly-held teardown owner.

        The controller deliberately does not keep feature owners alive. Production
        composition already owns those objects; this stack only records their reverse
        teardown order. The callback is resolved at shutdown time so the stack itself
        does not create another bound-method reference cycle.
        """

        if self._closed:
            raise RuntimeError("composition lifecycle is already closed")
        callback = getattr(owner, method_name, None)
        if not callable(callback):
            raise TypeError(f"{owner!r} has no callable {method_name!r}")
        try:
            owner_ref = weakref.ref(owner)
        except TypeError as exc:
            raise TypeError("composition teardown owners must support weak references") from exc
        self._entries.append(
            _TeardownEntry(
                owner_ref,
                method_name,
                label or f"{type(owner).__name__}.{method_name}",
            )
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        window = self._window_ref()
        if watched is window and event.type() == QEvent.Type.Close:
            self.shutdown()
        return super().eventFilter(watched, event)

    def shutdown(self) -> None:
        """Drain registered feature teardown callbacks exactly once in LIFO order."""

        if self._closed or self._shutting_down:
            return
        self._shutting_down = True
        try:
            while self._entries:
                entry = self._entries.pop()
                owner = entry.owner_ref()
                if owner is None:
                    continue
                callback = getattr(owner, entry.method_name, None)
                if not callable(callback):
                    LOGGER.error("Composition teardown callback disappeared: %s", entry.label)
                    continue
                try:
                    callback()
                except Exception:  # noqa: BLE001 - continue deterministic teardown
                    LOGGER.exception("Composition teardown failed: %s", entry.label)
        finally:
            self._entries.clear()
            self._closed = True
            self._shutting_down = False


def install_composition_lifecycle(window: Any) -> CompositionLifecycleController:
    """Install the one teardown stack owned by a composed MainWindow."""

    existing = getattr(window, "_composition_lifecycle_controller", None)
    if isinstance(existing, CompositionLifecycleController):
        return existing
    if not isinstance(window, QObject):
        raise TypeError("composition lifecycle requires a QObject window")
    controller = CompositionLifecycleController(window)
    window._composition_lifecycle_controller = controller
    return controller


def register_composed_teardown(
    window: Any,
    owner: object,
    *,
    method_name: str = "shutdown",
    label: str | None = None,
) -> None:
    """Register one composed feature owner on the window's LIFO teardown stack."""

    lifecycle = install_composition_lifecycle(window)
    lifecycle.register(owner, method_name=method_name, label=label)
