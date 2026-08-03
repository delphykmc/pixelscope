from __future__ import annotations

import numpy as np

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.performance_settings import DEFAULT_DIFFERENCE_CACHE_BYTES
from pixelscope.ui.difference_panel import DifferencePanel


def _documents() -> list[ImageDocument]:
    return [
        ImageDocument.from_array(
            np.full((2, 2, 3), value, dtype=np.uint8),
            f"cache-{index}.png",
        )
        for index, value in enumerate((0, 10, 30))
    ]


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
