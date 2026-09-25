"""Opt-in E8 timing marks for documentation tests; no validation behavior changes.

Enable only while profiling with PIXELSCOPE_E8_PROFILE=1. Each line is an
independent measurement; parent subprocess wall time includes child phases and
must not be added to them when attributing total time.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

_ENABLED = os.environ.get("PIXELSCOPE_E8_PROFILE") == "1"


@contextmanager
def measure_phase(phase: str, **fields: object) -> Iterator[None]:
    """Print machine-readable wall-time observations even on a failing phase."""
    started = time.perf_counter()
    try:
        yield
    finally:
        if _ENABLED:
            record = {
                "phase": phase,
                "seconds": round(time.perf_counter() - started, 6),
                "pid": os.getpid(),
                **fields,
            }
            print("PIXELSCOPE_E8_PHASE " + json.dumps(record, sort_keys=True), flush=True)
