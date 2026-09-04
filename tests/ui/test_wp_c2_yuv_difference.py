from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from pixelscope.core.diff_engine import DifferenceMetrics
from pixelscope.core.difference_cache import CachedDifferenceMap
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.core.yuv_difference import difference_compatibility
from pixelscope.ui.difference_panel import DifferencePanel


def _chroma_shape(layout: str, height: int, width: int) -> tuple[int, int]:
    scale_x = 1 if layout == "YUV444" else 2
    scale_y = 2 if layout == "YUV420" else 1
    return height // scale_y, width // scale_x


def _yuv_pair(
    layout: str,
    *,
    height: int = 4,
    width: int = 4,
    channel: str = "Y",
    delta: int = 10,
) -> tuple[ImageDocument, ImageDocument]:
    chroma_shape = _chroma_shape(layout, height, width)
    y_a = np.full((height, width), 40, dtype=np.uint8)
    u_a = np.full(chroma_shape, 90, dtype=np.uint8)
    v_a = np.full(chroma_shape, 160, dtype=np.uint8)
    y_b = y_a.copy()
    u_b = u_a.copy()
    v_b = v_a.copy()
    selected = {"Y": y_b, "U": u_b, "V": v_b}[channel]
    selected.flat[0] = np.uint8(int(selected.flat[0]) + delta)
    first = ImageDocument.from_yuv(
        NativeYuvFrame(y=y_a, u=u_a, v=v_a, layout=layout),
        "a.yuv",
    )
    second = ImageDocument.from_yuv(
        NativeYuvFrame(y=y_b, u=u_b, v=v_b, layout=layout),
        "b.yuv",
    )
    # Make presentation deliberately useless as numerical evidence. A preview-based
    # implementation would now produce an all-zero Difference.
    assert first.preview is not None and second.preview is not None
    first.preview.fill(17)
    second.preview.fill(17)
    return first, second


def _wait_for_result(panel: DifferencePanel, qtbot: object) -> CachedDifferenceMap:
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None and panel.cached_result_for_current() is not None,
        timeout=3000,
    )
    result = panel.cached_result_for_current()
    assert result is not None
    return result


@pytest.mark.parametrize(
    ("layout", "channel", "expected_shape"),
    (
        ("YUV444", "Y", (4, 4)),
        ("YUV444", "U", (4, 4)),
        ("YUV444", "V", (4, 4)),
        ("YUV422", "Y", (4, 4)),
        ("YUV422", "U", (4, 2)),
        ("YUV422", "V", (4, 2)),
        ("YUV420", "Y", (4, 4)),
        ("YUV420", "U", (2, 2)),
        ("YUV420", "V", (2, 2)),
    ),
)
def test_native_yuv_difference_uses_selected_plane_and_native_sample_count(
    qtbot: object,
    layout: str,
    channel: str,
    expected_shape: tuple[int, int],
) -> None:
    first, second = _yuv_pair(layout, channel=channel)
    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents([first, second], (first.document_id, second.document_id))

    assert [panel.channel.itemText(index) for index in range(panel.channel.count())] == [
        "Y",
        "U",
        "V",
    ]
    assert panel.channel.currentText() == "Y"
    panel.channel.setCurrentText(channel)

    cached = _wait_for_result(panel, qtbot)

    assert cached.channel_layout == layout
    assert cached.domain == "native"
    assert cached.data_range == 255.0
    assert cached.absolute.dtype == np.dtype(np.uint8)
    assert cached.absolute.shape == expected_shape
    assert int(np.count_nonzero(cached.absolute)) == 1
    assert int(np.max(cached.absolute)) == 10
    assert panel.last_result is not None
    assert panel.last_result.mae == pytest.approx(10.0 / np.prod(expected_shape))
    assert panel.last_result.mse == pytest.approx(100.0 / np.prod(expected_shape))
    assert panel.last_result.maximum_absolute == 10.0
    assert panel.last_result.nonzero_ratio == pytest.approx(1.0 / np.prod(expected_shape))


def test_yuv420_active_roi_reuses_native_chroma_footprint_mapping(qtbot: object) -> None:
    y = np.zeros((6, 6), dtype=np.uint8)
    u_a = np.zeros((3, 3), dtype=np.uint8)
    u_b = np.array([[1, 2, 30], [4, 5, 60], [70, 80, 90]], dtype=np.uint8)
    v = np.zeros((3, 3), dtype=np.uint8)
    first = ImageDocument.from_yuv(
        NativeYuvFrame(y=y.copy(), u=u_a, v=v.copy(), layout="YUV420"),
        "a.yuv",
    )
    second = ImageDocument.from_yuv(
        NativeYuvFrame(y=y.copy(), u=u_b, v=v.copy(), layout="YUV420"),
        "b.yuv",
    )
    roi = RoiBounds(1, 1, 3, 3)
    assert first.yuv_frame is not None
    assert first.yuv_frame.roi_plane_bounds(roi, "U") == RoiBounds(0, 0, 2, 2)

    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents([first, second], (first.document_id, second.document_id), roi)
    panel.channel.setCurrentText("U")

    cached = _wait_for_result(panel, qtbot)

    assert cached.absolute.shape == (3, 3)
    assert panel.region.currentText() == "Active ROI"
    assert panel.last_result is not None
    # The luma ROI [1:4, 1:4] references native U [0:2, 0:2] => 1,2,4,5.
    assert panel.last_result.mae == pytest.approx(3.0)
    assert panel.last_result.mse == pytest.approx((1 + 4 + 16 + 25) / 4)
    assert panel.last_result.maximum_absolute == 5.0
    assert panel.last_result.nonzero_ratio == 1.0


def test_yuv_difference_rejects_mixed_subsampling_and_non_yuv_family(qtbot: object) -> None:
    yuv420_a, _ = _yuv_pair("YUV420")
    yuv422_a, _ = _yuv_pair("YUV422")
    gray = ImageDocument.from_array(np.zeros((4, 4), dtype=np.uint8), "gray.png")

    mixed = difference_compatibility(yuv420_a, yuv422_a)
    assert not mixed.compatible
    assert mixed.reason_code == "layout-mismatch"
    assert "subsampling" in mixed.detail

    cross_family = difference_compatibility(yuv420_a, gray)
    assert not cross_family.compatible
    assert cross_family.reason_code == "layout-mismatch"
    assert "YUV vs non-YUV" in cross_family.detail

    panel = DifferencePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents(
        [yuv420_a, yuv422_a],
        (yuv420_a.document_id, yuv422_a.document_id),
    )
    assert [panel.channel.itemText(index) for index in range(panel.channel.count())] == [
        "Y",
        "U",
        "V",
    ]
    assert not panel.calculate.isEnabled()
    assert panel.status.text() == "Layout mismatch"
    assert "subsampling" in panel.status.toolTip()

    panel.set_documents([yuv420_a, gray], (yuv420_a.document_id, gray.document_id))
    assert not panel.calculate.isEnabled()
    assert "YUV vs non-YUV" in panel.status.toolTip()


def test_yuv_channel_switch_uses_channel_aware_lazy_cache(qtbot: object) -> None:
    first, second = _yuv_pair("YUV420", channel="Y")
    assert second.yuv_frame is not None
    second.yuv_frame.u.flat[0] = np.uint8(int(second.yuv_frame.u.flat[0]) + 7)
    second.yuv_frame.v.flat[0] = np.uint8(int(second.yuv_frame.v.flat[0]) + 9)
    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents([first, second], (first.document_id, second.document_id))

    y_map = _wait_for_result(panel, qtbot)
    y_metrics = panel.last_result
    y_key = panel._cache_key()
    assert y_key is not None
    assert len(y_key) == 3
    assert y_key[2] == ("YUV420", "Y")
    assert y_map.absolute.shape == (4, 4)
    assert panel.difference_cache.entry_count == 1
    assert panel.difference_cache.used_bytes == 16

    panel.channel.setCurrentText("U")
    u_map = _wait_for_result(panel, qtbot)
    u_key = panel._cache_key()
    assert u_key is not None and u_key != y_key
    assert len(u_key) == 3
    assert u_key[2] == ("YUV420", "U")
    assert u_map.absolute.shape == (2, 2)
    assert panel.difference_cache.entry_count == 2
    assert panel.difference_cache.used_bytes == 20

    # V has not been precomputed. Switching back selects the exact Y map/metrics.
    panel.channel.setCurrentText("Y")
    assert panel.cached_result_for_current() is y_map
    assert panel.last_result is y_metrics
    assert panel.difference_cache.entry_count == 2
    assert panel.difference_cache.used_bytes == 20


def test_yuv_cache_variant_entries_are_dropped_on_generation_change(qtbot: object) -> None:
    first, second = _yuv_pair("YUV420", channel="Y")
    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents([first, second], (first.document_id, second.document_id))
    _wait_for_result(panel, qtbot)
    panel.channel.setCurrentText("U")
    _wait_for_result(panel, qtbot)
    assert panel.difference_cache.entry_count == 2

    first.generation += 1
    panel.set_documents([first, second], (first.document_id, second.document_id))

    assert panel.difference_cache.entry_count == 0
    assert panel.difference_cache.used_bytes == 0
    # WP-C2's generation contract is cache identity/invalidation. The standalone
    # fixture mutates the same ImageDocument instance in place, unlike the production
    # reload lifecycle that clears/rebinds source state before presentation. Ensure no
    # stale generation remains actionable in either map or metric caches.
    assert panel._metric_cache == {}


def test_late_yuv_channel_result_is_cached_but_not_published_for_new_channel(qtbot: object) -> None:
    first, second = _yuv_pair("YUV420", channel="Y")
    panel = DifferencePanel(difference_cache_budget_bytes=4096)
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents([first, second], (first.document_id, second.document_id))
    old_key = panel._cache_key()
    old_metric_key = panel._metric_key()
    assert old_key is not None and old_metric_key is not None

    panel.channel.setCurrentText("U")
    assert panel.last_result is None
    late_map = CachedDifferenceMap(
        absolute=np.ones((4, 4), dtype=np.uint8),
        domain="native",
        data_range=255.0,
        channel_layout="YUV420",
        bayer_pattern=None,
    )
    late_metrics = DifferenceMetrics(
        mae=1.0,
        mse=1.0,
        rmse=1.0,
        psnr=1.0,
        p95=1.0,
        p99=1.0,
        maximum_absolute=1.0,
        nonzero_ratio=1.0,
        minimum_signed=1.0,
        maximum_signed=1.0,
        minimum_absolute=1.0,
    )

    panel._on_result(old_key, old_metric_key, (late_map, late_metrics, False), True)

    assert old_key in panel.difference_cache
    assert panel.last_result is None
    assert panel.cached_result_for_current() is None


def test_legacy_gray_rgb_bayer_and_normalized_compatibility_is_preserved() -> None:
    gray_a = ImageDocument.from_array(np.zeros((4, 4), dtype=np.uint8), "a.png")
    gray_b = ImageDocument.from_array(np.ones((4, 4), dtype=np.uint8), "b.png")
    assert difference_compatibility(gray_a, gray_b).compatible

    normalized_gray = ImageDocument.from_array(
        np.ones((4, 4), dtype=np.uint16),
        "normalized.raw",
        bit_depth=12,
    )
    normalized = difference_compatibility(gray_a, normalized_gray)
    assert normalized.compatible
    assert normalized.domain == "normalized"
    assert normalized.data_range == 1.0

    rgb = ImageDocument.from_array(np.zeros((4, 4, 3), dtype=np.uint8), "rgb.png")
    assert not difference_compatibility(gray_a, rgb).compatible

    profile = SimpleNamespace(bayer_pattern="RGGB")
    bayer_a = ImageDocument.from_array(
        np.zeros((4, 4), dtype=np.uint16),
        "a.raw",
        channel_layout="BAYER",
        bit_depth=12,
        raw_profile=profile,
    )
    bayer_b = ImageDocument.from_array(
        np.ones((4, 4), dtype=np.uint16),
        "b.raw",
        channel_layout="BAYER",
        bit_depth=12,
        raw_profile=profile,
    )
    bayer = difference_compatibility(bayer_a, bayer_b)
    assert bayer.compatible
    assert bayer.domain == "native"
