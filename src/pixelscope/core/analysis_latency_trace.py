"""Opt-in latency probes for 4K selection/Histogram responsiveness.

Set PIXELSCOPE_ANALYSIS_TRACE=1 before launching PixelScope. Probe timestamps
contain only stage names and numeric durations, never source paths or pixels.
"""

from __future__ import annotations

import logging
import os
from time import perf_counter, thread_time

_ENABLED = os.environ.get("PIXELSCOPE_ANALYSIS_TRACE", "").lower() in ("1", "true", "yes")
_LOGGER = logging.getLogger("pixelscope.performance.analysis")


class PhaseTimer:
    """Small no-op unless profiling was explicitly enabled before startup."""

    def __init__(self, phase: str, *, documents: int) -> None:
        self._phase = phase
        self._documents = documents
        self._start = perf_counter() if _ENABLED else None
        self._cpu_start = thread_time() if _ENABLED else None

    def finish(self) -> None:
        if self._start is None or self._cpu_start is None:
            return
        _LOGGER.warning(
            "[analysis-latency] %s documents=%d wall_ms=%.2f thread_cpu_ms=%.2f",
            self._phase,
            self._documents,
            1000.0 * (perf_counter() - self._start),
            1000.0 * (thread_time() - self._cpu_start),
        )
