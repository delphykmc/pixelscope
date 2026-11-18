from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from shiboken6 import isValid

from pixelscope.core.diff_engine import absolute_difference_metrics
from pixelscope.core.difference_cache import CachedDifferenceMap
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.performance_settings import DEFAULT_DIFFERENCE_CACHE_BYTES
from pixelscope.ui.difference_panel import DifferencePanel
from pixelscope.workers.task_worker import TaskError


def _documents() -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((2, 2, 3), value, dtype=np.uint8),
            f"cache-{index}.png",
        )
        for index, value in enumerate((0, 10, 30))
    ]


@pytest.mark.parametrize("publish_result", [False, True])
def test_shutdown_rejects_queued_difference_callbacks_after_child_destruction(
    qtbot: object, publish_result: bool
) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents(_documents()[:2], None)
    key, metric_key = panel._cache_key(), panel._metric_key()
    assert key is not None and metric_key is not None
    absolute = np.full((2, 2, 3), 10, dtype=np.uint8)
    difference_map = CachedDifferenceMap(
        absolute=absolute,
        domain="native",
        data_range=255.0,
        channel_layout="RGB",
        bayer_pattern=None,
    )
    metrics = absolute_difference_metrics(absolute, 255.0)
    settled: list[object] = []
    panel.presentation_settled.connect(settled.append)
    panel._presentation_map_pairs["late"] = ("a", "b")
    panel._presentation_preview_pairs["late-preview"] = ("a", "b")
    panel.shutdown()
    panel.shutdown()
    # Reproduce the observed close ordering: a queued Python callback may
    # outlive the selector's C++ object even though its panel wrapper exists.
    panel.a_selector.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not isValid(panel.a_selector)
    panel._on_result("late", key, metric_key, (difference_map, metrics, False), publish_result)
    panel._on_error("late", None, 0, TaskError("late", None, 0, "late error", "OSError", ""))
    panel._on_finished("late")
    panel._preview_finished("late-preview")
    panel.calculate_difference()
    assert panel.last_result is None
    assert panel.difference_cache.entry_count == 0
    assert panel._metric_cache == {}
    assert settled == []


def test_difference_panel_exposes_injected_cache_diagnostics(qtbot: object) -> None:
    panel = DifferencePanel(difference_cache_budget_bytes=1234)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]

    assert panel.difference_cache.budget_bytes == 1234
    assert panel.difference_cache.used_bytes == 0
    assert panel.difference_cache.entry_count == 0
    assert [panel.metrics.item(row, 0).text() for row in range(panel.metrics.rowCount())] == [
        "MAE",
        "MSE",
        "RMSE",
        "PSNR",
        "P95",
        "P99",
        "Max difference",
        "Non-zero ratio",
    ]

    default_panel = DifferencePanel()
    qtbot.addWidget(default_panel)  # type: ignore[attr-defined]
    assert default_panel.difference_cache.budget_bytes == DEFAULT_DIFFERENCE_CACHE_BYTES


def test_panel_lru_eviction_removes_dependent_metric_cache(qtbot: object) -> None:
    panel = DifferencePanel(difference_cache_budget_bytes=12)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    documents = _documents()
    panel.set_documents(documents, None)

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None and panel.difference_cache.entry_count == 1,
        timeout=3000,
    )
    first_key = panel._cache_key()
    assert first_key is not None
    assert panel.difference_cache.used_bytes == 12
    assert len(panel._metric_cache) == 1

    panel.b_selector.setCurrentIndex(2)
    second_key = panel._cache_key()
    assert second_key is not None and second_key != first_key
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None
        and panel.difference_cache.entry_count == 1
        and panel.difference_cache.peek(second_key) is not None,
        timeout=3000,
    )

    assert panel.difference_cache.peek(first_key) is None
    assert panel.difference_cache.used_bytes == 12
    assert all((metric_key[0], metric_key[1]) != first_key for metric_key in panel._metric_cache)
    assert len(panel._metric_cache) == 1


def test_expanded_metrics_render_exact_values(qtbot: object) -> None:
    panel = DifferencePanel(difference_cache_budget_bytes=1024)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = ImageDocument.from_array(np.zeros((2, 2, 3), dtype=np.uint8), "a.png")
    second_pixels = np.array(
        [
            [[0, 0, 0], [10, 10, 10]],
            [[20, 20, 20], [30, 30, 30]],
        ],
        dtype=np.uint8,
    )
    second = ImageDocument.from_array(second_pixels, "b.png")
    panel.set_documents([first, second], None)

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None,
        timeout=3000,
    )

    assert panel.metrics.item(0, 1).text() == "15"
    assert panel.metrics.item(1, 1).text() == "350"
    assert panel.metrics.item(2, 1).text().startswith("18.708")
    assert panel.metrics.item(4, 1).text() == "30"
    assert panel.metrics.item(5, 1).text() == "30"
    assert panel.metrics.item(6, 1).text() == "30"
    assert panel.metrics.item(7, 1).text() == "0.75"


def test_same_pair_rerender_does_not_relabel_fresh_metrics_as_restored(
    qtbot: object,
) -> None:
    panel = DifferencePanel(difference_cache_budget_bytes=1024)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    documents = _documents()[:2]
    panel.set_documents(documents, None)

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None and panel.status.text() == "Ready",
        timeout=3000,
    )
    result = panel.last_result

    panel.set_documents(documents, None)

    assert panel.last_result is result
    assert panel.status.text() == "Ready"


def test_same_document_id_new_generation_does_not_restore_stale_difference(
    qtbot: object,
) -> None:
    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = ImageDocument.from_array(np.zeros((4, 4), dtype=np.uint8), "first.png")
    second = ImageDocument.from_array(np.full((4, 4), 10, dtype=np.uint8), "second.png")
    pair = (first.document_id, second.document_id)
    panel.set_documents([first, second], pair)
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None and panel.difference_cache.entry_count == 1,
        timeout=3000,
    )
    stale_result = panel.last_result
    stale_key = panel._cache_key()
    assert stale_result is not None and stale_key is not None

    refreshed = ImageDocument.from_array(np.full((4, 4), 100, dtype=np.uint8), "first.png")
    refreshed.document_id = first.document_id
    refreshed.generation = first.generation + 1

    panel.set_documents([refreshed, second], pair)

    assert panel._cache_key() != stale_key
    assert panel.last_result is None
    assert panel.cached_result_for_current() is None

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None,
        timeout=3000,
    )
    assert panel.last_result is not stale_result
    assert panel.last_result.mae == 90.0
