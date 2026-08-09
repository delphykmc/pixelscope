from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtWidgets import QSizePolicy

from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.difference_panel import DifferencePanel


def _gray(value: int, name: str, bit_depth: int = 8) -> ImageDocument:
    dtype = np.uint8 if bit_depth <= 8 else np.uint16
    return ImageDocument.from_array(
        np.full((3, 4), value, dtype=dtype),
        name,
        bit_depth=bit_depth,
    )


def _rgb(value: int, name: str, *, alpha: int | None = None) -> ImageDocument:
    channels = 4 if alpha is not None else 3
    source = np.full((3, 4, channels), value, dtype=np.uint8)
    if alpha is not None:
        source[..., 3] = alpha
    return ImageDocument.from_array(source, name)


def test_difference_panel_compact_fields_do_not_force_sidebar_width(qtbot: object) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]

    assert panel.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    assert panel.threshold.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    assert panel.metric_scope.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    assert panel.domain_status.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored


def test_gray_pair_exposes_gray_and_native_domain(qtbot: object) -> None:
    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = _gray(10, "a.png")
    second = _gray(15, "b.png")

    panel.set_documents([first, second], (first.document_id, second.document_id))

    assert [panel.channel.itemText(i) for i in range(panel.channel.count())] == ["Gray"]
    assert panel.metric_scope.text() == "Scope Full image · Gray"
    assert panel.domain_status.text() == "Domain Native · 8-bit"
    assert panel.threshold.suffix() == " code"
    assert panel.calculate.isEnabled()

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None and panel.difference_cache.entry_count == 1,
        timeout=3000,
    )
    cached = panel.cached_result_for_current()
    assert cached is not None
    assert cached.domain == "native"
    assert cached.channel_layout == "GRAY"
    assert cached.absolute.dtype == np.dtype(np.uint8)
    assert np.all(cached.absolute == 5)


def test_rgb_rgba_pair_ignores_alpha_and_keeps_rgb_channels(qtbot: object) -> None:
    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    rgb = _rgb(25, "rgb.png")
    rgba = _rgb(25, "rgba.png", alpha=255)

    panel.set_documents([rgb, rgba], (rgb.document_id, rgba.document_id))

    assert [panel.channel.itemText(i) for i in range(panel.channel.count())] == [
        "All",
        "R",
        "G",
        "B",
    ]
    assert panel.metric_scope.text() == "Scope Full image · RGB combined"
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None,
        timeout=3000,
    )
    cached = panel.cached_result_for_current()
    assert cached is not None
    assert cached.channel_layout == "RGB"
    assert cached.absolute.shape == (3, 4, 3)
    assert np.count_nonzero(cached.absolute) == 0


def test_mixed_bit_gray_uses_normalized_domain_and_percent_full_scale(qtbot: object) -> None:
    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = _gray(255, "a.png", 8)
    second = _gray(0, "b.raw", 10)

    panel.set_documents([first, second], (first.document_id, second.document_id))

    assert panel.domain_status.text() == "Domain Normalized [0–1]"
    assert panel.threshold.suffix() == " %FS"
    assert panel.threshold.decimals() == 2
    assert panel.threshold.value() == pytest.approx(1.0)
    assert panel._threshold_value("normalized") == pytest.approx(0.01)

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None,
        timeout=3000,
    )
    cached = panel.cached_result_for_current()
    assert cached is not None
    assert cached.domain == "normalized"
    assert cached.data_range == 1.0
    assert cached.absolute.dtype == np.dtype(np.float32)
    assert np.all(cached.absolute == 1.0)

    panel.mode.setCurrentText("Mask")
    panel.threshold.setValue(100.0)
    preview = panel.cached_display_for_current()
    assert preview is not None
    assert np.count_nonzero(preview[2]) == 0
    panel.threshold.setValue(99.0)
    preview = panel.cached_display_for_current()
    assert preview is not None
    assert np.all(preview[2][..., 0] == 255)


def test_native_and_normalized_thresholds_are_session_local_per_domain(qtbot: object) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    gray8_a = _gray(0, "a.png", 8)
    gray8_b = _gray(1, "b.png", 8)
    gray10 = _gray(1, "c.raw", 10)
    panel.set_documents([gray8_a, gray8_b, gray10], (gray8_a.document_id, gray8_b.document_id))

    panel.threshold.setValue(23.0)
    panel.b_selector.setCurrentIndex(2)
    assert panel.threshold.suffix() == " %FS"
    assert panel.threshold.value() == pytest.approx(1.0)
    panel.threshold.setValue(2.5)

    panel.b_selector.setCurrentIndex(1)
    assert panel.threshold.suffix() == " code"
    assert panel.threshold.value() == 23.0
    panel.b_selector.setCurrentIndex(2)
    assert panel.threshold.value() == pytest.approx(2.5)


def test_validation_status_is_compact_and_detail_is_in_tooltip(qtbot: object) -> None:
    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    gray = _gray(0, "gray.png")
    rgb = _rgb(0, "rgb.png")

    panel.set_documents([gray, rgb], (gray.document_id, rgb.document_id))

    assert panel.status.text() == "Layout mismatch"
    assert "families do not match" in panel.status.toolTip()
    assert panel.calculate.toolTip() == panel.status.toolTip()
    assert not panel.calculate.isEnabled()


def test_reversed_normalized_pair_reuses_one_cached_map(qtbot: object) -> None:
    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = _gray(128, "a.png", 8)
    second = _gray(512, "b.raw", 10)
    panel.set_documents([first, second], (first.document_id, second.document_id))

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None and panel.difference_cache.entry_count == 1,
        timeout=3000,
    )
    key = panel._cache_key()
    cached = panel.cached_result_for_current()
    assert key is not None and cached is not None and cached.domain == "normalized"

    panel.a_selector.setCurrentIndex(1)
    panel.b_selector.setCurrentIndex(0)
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.status.text() in {"Cached map reused", "Cached metrics restored", "Ready"},
        timeout=3000,
    )

    assert panel._cache_key() == key
    assert panel.difference_cache.entry_count == 1
    restored = panel.cached_result_for_current()
    assert restored is not None
    assert restored.domain == "normalized"
    assert np.array_equal(restored.absolute, cached.absolute)
