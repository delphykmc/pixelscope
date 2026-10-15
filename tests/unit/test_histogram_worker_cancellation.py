from __future__ import annotations

from threading import Event

import numpy as np
import pytest

from pixelscope.core import statistics
from pixelscope.core.cancellation import CooperativeCancellation, cancellation_scope
from pixelscope.core.roi import RoiBounds, analyze_roi


def test_obsolete_rgb_histogram_stops_before_next_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Exercise the retained uint16 NumPy fallback; uint8/256 now uses cv2.
    image = np.full((16, 24, 3), 127, dtype=np.uint16)
    cancel_event = Event()
    original_bincount = statistics.np.bincount
    calls: list[int] = []

    def cancel_after_first_channel(*args: object, **kwargs: object) -> np.ndarray:
        result = original_bincount(*args, **kwargs)
        calls.append(1)
        cancel_event.set()
        return result

    monkeypatch.setattr(statistics.np, "bincount", cancel_after_first_channel)
    with cancellation_scope(cancel_event), pytest.raises(CooperativeCancellation):
        analyze_roi(image, RoiBounds(0, 0, 24, 16), bins=65536)
    assert calls == [1]


def test_roi_analysis_without_worker_scope_still_returns_full_results() -> None:
    image = np.full((16, 24, 3), 127, dtype=np.uint8)
    result = analyze_roi(image, RoiBounds(0, 0, 24, 16), bins=256)
    assert result.pixel_count == 16 * 24
    assert result.channel_names == ("R", "G", "B")
    assert all(value.mean == 127.0 for value in result.channel_statistics)
