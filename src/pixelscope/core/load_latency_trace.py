"""Opt-in coarse wall-clock trace for the first explicit image load.

Set PIXELSCOPE_LOAD_TRACE=1 before launching PixelScope. Traces contain
monotonic durations and short stage names only; source paths are never logged.
This is a diagnostic aid, not a substitute for first-paint benchmarks.
"""

from __future__ import annotations

import logging
import os
from time import perf_counter_ns, thread_time_ns

LOGGER = logging.getLogger(__name__)
_ENABLED = os.environ.get("PIXELSCOPE_LOAD_TRACE") == "1"
_start_ns: int | None = None
_target_document_id: str | None = None
_seen: set[str] = set()


def begin(stage: str) -> None:
    """Begin one single-file diagnostic trace (a later request supersedes it)."""

    global _start_ns, _target_document_id
    if not _ENABLED:
        return
    _start_ns = perf_counter_ns()
    _target_document_id = None
    _seen.clear()
    LOGGER.warning("[load-trace] +0.00ms %s", stage)


def target(document_id: str) -> None:
    """Associate GUI and viewport events with the newly registered document."""

    global _target_document_id
    if not _ENABLED or _start_ns is None:
        return
    _target_document_id = document_id
    mark("files_row_registered", document_id=document_id)


def mark(
    stage: str,
    *,
    document_id: str | None = None,
    once: bool = False,
) -> None:
    """Log an elapsed-time checkpoint if this request still owns the trace."""

    if not _ENABLED or _start_ns is None:
        return
    if document_id is not None and document_id != _target_document_id:
        return
    if once and stage in _seen:
        return
    if once:
        _seen.add(stage)
    elapsed_ms = (perf_counter_ns() - _start_ns) / 1_000_000
    LOGGER.warning("[load-trace] +%.2fms %s", elapsed_ms, stage)


def tracks(document_id: str) -> bool:
    """Whether this document still needs the first viewport-paint marker."""

    return (
        _ENABLED
        and _start_ns is not None
        and _target_document_id == document_id
        and "first_viewport_paint_event_processed" not in _seen
    )


class PhaseTimer:
    """Opt-in local GUI call-path timing; independent of concurrent worker events.

    Each checkpoint reports both elapsed time since this scope began and the
    incremental time since its previous checkpoint. Times are monotonic and
    scoped to the current invocation, so nested/reentrant rendering does not
    corrupt the accounting. This intentionally does not invoke processEvents().
    """

    def __init__(self, group: str, *, document_id: str | None = None) -> None:
        self._group = group
        self._active = (
            _ENABLED
            and _start_ns is not None
            and (document_id is None or document_id == _target_document_id)
        )
        self._started_ns = perf_counter_ns() if self._active else 0
        self._previous_ns = self._started_ns
        self._started_cpu_ns = thread_time_ns() if self._active else 0
        self._previous_cpu_ns = self._started_cpu_ns
        if self._active:
            mark(f"{group}.begin", document_id=document_id)

    def checkpoint(self, stage: str) -> None:
        if not self._active:
            return
        now = perf_counter_ns()
        cpu_now = thread_time_ns()
        elapsed_ms = (now - self._started_ns) / 1_000_000
        delta_ms = (now - self._previous_ns) / 1_000_000
        cpu_elapsed_ms = (cpu_now - self._started_cpu_ns) / 1_000_000
        cpu_delta_ms = (cpu_now - self._previous_cpu_ns) / 1_000_000
        self._previous_ns = now
        self._previous_cpu_ns = cpu_now
        LOGGER.warning(
            "[load-trace] %s.%s step=%.2fms scope=%.2fms cpu_step=%.2fms cpu_scope=%.2fms",
            self._group,
            stage,
            delta_ms,
            elapsed_ms,
            cpu_delta_ms,
            cpu_elapsed_ms,
        )
