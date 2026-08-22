"""Thread-local cooperative cancellation checkpoints for bounded background work."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from threading import Event, local

_STATE = local()


class CooperativeCancellation(RuntimeError):
    """Background work observed its owning task's cancellation request."""


@contextmanager
def cancellation_scope(cancel_event: Event) -> Iterator[None]:
    """Expose one task cancellation event to lower-level synchronous helpers."""

    previous = getattr(_STATE, "cancel_event", None)
    _STATE.cancel_event = cancel_event
    try:
        yield
    finally:
        if previous is None:
            with suppress(AttributeError):
                del _STATE.cancel_event
        else:
            _STATE.cancel_event = previous


def cancellation_checkpoint() -> None:
    """Raise when the current TaskWorker has been asked to stop."""

    event = getattr(_STATE, "cancel_event", None)
    if isinstance(event, Event) and event.is_set():
        raise CooperativeCancellation("task cancelled")
