from __future__ import annotations

import numpy as np
import pytest

from pixelscope.app.main_window import MainWindow
from pixelscope.core.bayer import render_bayer_preview
from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.io.raw_profile import RawProfile

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_difference_action_compatibility_states(qtbot: object) -> None:
    def bayer_document(name: str, shape: tuple[int, int] = (6, 8)) -> ImageDocument:
        profile = RawProfile(
            name=name,
            width=shape[1],
            height=shape[0],
            dtype="uint16",
            stride_bytes=shape[1] * 2,
            bit_depth=10,
            packing="unpacked_u16",
            channel_layout="BAYER",
            bayer_pattern="RGGB",
            black_level=0,
            white_level=1023,
        )
        source = np.zeros(shape, dtype=np.uint16)
        transform = DisplayTransform(display_low=0.0, display_high=1023.0)
        return ImageDocument.from_array(
            source,
            name,
            channel_layout="BAYER",
            bit_depth=10,
            raw_profile=profile,
            display_transform=transform,
            prepared_preview=render_bayer_preview(
                source,
                profile.bayer_pattern or "RGGB",
                profile.black_level,
                profile.bit_depth,
            ),
        )

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    rgb_a = ImageDocument.from_array(np.zeros((6, 8, 3), dtype=np.uint8), "a.png")
    rgb_b = ImageDocument.from_array(np.ones((6, 8, 3), dtype=np.uint8), "b.png")
    for document in (rgb_a, rgb_b):
        window.add_document(document, select=False)
    window._select_document_ids([rgb_a.document_id, rgb_b.document_id])
    assert window.difference_panel.calculate.isEnabled()

    bayer = bayer_document("mosaic.raw")
    window.add_document(bayer, select=False)
    window._select_document_ids([rgb_a.document_id, bayer.document_id])
    assert not window.difference_panel.calculate.isEnabled()
    assert window.difference_panel.status.text() == "Layout mismatch"
    assert "families do not match" in window.difference_panel.status.toolTip()

    different_size = ImageDocument.from_array(
        np.ones((7, 8, 3), dtype=np.uint8),
        "different.png",
    )
    window.add_document(different_size, select=False)
    window._select_document_ids([rgb_a.document_id, different_size.document_id])
    assert window.difference_panel.status.text() == "Size mismatch"
    assert "dimensions do not match" in window.difference_panel.status.toolTip()
    window.close()


def test_difference_display_updates_roi_metrics_and_session_cache(qtbot: object) -> None:
    first_pixels = np.zeros((4, 4, 3), dtype=np.uint8)
    second_pixels = np.zeros((4, 4, 3), dtype=np.uint8)
    second_pixels[0, 0, :] = 10
    second_pixels[2:4, 2:4, :] = 40
    first = ImageDocument.from_array(first_pixels, "cache-a.png")
    second = ImageDocument.from_array(second_pixels, "cache-b.png")
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.add_document(first, select=False)
    window.add_document(second, select=False)
    window._select_document_ids([first.document_id, second.document_id])
    panel = window.difference_panel

    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None and window._difference_document is not None,
        timeout=3000,
    )
    cached = panel.cached_result_for_current()
    assert cached is not None
    absolute_map = cached.absolute
    full_metric = panel.metrics.item(0, 1).text()

    with qtbot.waitSignal(panel.preview_updated):  # type: ignore[attr-defined]
        panel.gain.setValue(2)
    assert panel._worker is None
    assert panel.cached_result_for_current() is not None
    assert panel.cached_result_for_current().absolute is absolute_map
    assert panel.metrics.item(0, 1).text() == full_metric

    window._shared_roi_changed(RoiBounds(2, 2, 2, 2))
    assert panel.region.currentText() == "Active ROI"
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.metrics.item(0, 1).text() == "40",
        timeout=3000,
    )
    assert panel.cached_result_for_current() is not None
    assert panel.cached_result_for_current().absolute is absolute_map
    first_display = panel.cached_display_for_current()
    second_display = panel.cached_display_for_current()
    assert first_display is not None and second_display is not None
    assert first_display[1] is second_display[1]
    assert first_display[2] is second_display[2]

    panel.region.setCurrentText("Full image")
    assert panel.metrics.item(0, 1).text() == full_metric
    panel.a_selector.setCurrentIndex(1)
    panel.b_selector.setCurrentIndex(0)
    assert panel.cached_result_for_current() is not None
    assert panel.cached_result_for_current().absolute is absolute_map

    panel.channel.setCurrentText("R")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None,
        timeout=3000,
    )
    assert panel.cached_result_for_current() is not None
    assert panel.cached_result_for_current().absolute is absolute_map
    assert panel.cached_display_for_current()[1].ndim == 2
    panel.channel.setCurrentText("All")

    panel.mode.setCurrentText("Mask")
    assert panel.threshold.minimum() == 0
    assert panel.threshold.value() == 10
    updates: list[object] = []
    panel.preview_updated.connect(lambda *_args: updates.append(object()))  # type: ignore[attr-defined]
    panel.threshold.setValue(18)
    panel.threshold.setValue(19)
    panel.threshold.setValue(20)
    qtbot.wait(250)  # type: ignore[attr-defined]
    assert len(updates) == 1
    mask = panel.cached_display_for_current()
    assert mask is not None
    assert tuple(mask[2][2, 2]) == (255, 0, 0)
    assert tuple(mask[2][0, 0]) == (0, 0, 0)
    assert tuple(mask[2][1, 1]) == (0, 0, 0)

    window._select_document_ids([first.document_id])
    assert window._difference_document is None
    window._select_document_ids([first.document_id, second.document_id])
    assert window._difference_document is not None
    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert [viewer.document for viewer in window.multi_compare_view.occupied_viewers] == [
        first,
        window._difference_document,
        second,
    ]
    assert [
        viewer.header.badge.text() for viewer in window.multi_compare_view.occupied_viewers
    ] == ["1", "Diff", "2"]
    assert window.multi_compare_view.viewers[0].document is first
    window._set_focus_document(first)
    assert window.multi_compare_view.viewers[0].document is first
    assert [
        viewer.header.badge.text() for viewer in window.multi_compare_view.occupied_viewers
    ] == ["1", "Diff", "2"]
    window._set_focus_document(window._difference_document)
    assert window.multi_compare_view.viewers[0].document is window._difference_document
    window.set_layout_mode("Single View")
    navigation_labels = [
        window.viewer.header.navigation_layout.itemAt(index).widget().text()
        for index in range(window.viewer.header.navigation_layout.count())
    ]
    assert navigation_labels == ["1", "2", "Diff"]
    window._navigate_single_view("difference")
    assert window.viewer.document is window._difference_document
    window.close()


def test_difference_defaults_to_first_two_distinct_selected_images(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(np.full((4, 5), index, dtype=np.uint8), f"pick-{index}.png")
        for index in range(3)
    ]
    window.difference_panel.set_documents([documents[0]], None)
    window.difference_panel.set_documents(documents, None)
    assert window.difference_panel.a_selector.currentData() == documents[0].document_id
    assert window.difference_panel.b_selector.currentData() == documents[1].document_id
    assert window.difference_panel.selected_documents() == (documents[0], documents[1])
    window.close()


def test_three_selected_images_add_and_replace_one_latest_difference(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((8, 10, 3), index * 10, dtype=np.uint8),
            f"diff-{index + 1}.png",
        )
        for index in range(3)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and len(window.multi_compare_view.occupied_viewers) == 4,
        timeout=3000,
    )
    assert [viewer.document for viewer in window.multi_compare_view.occupied_viewers] == [
        window._difference_document,
        *documents,
    ]
    first_difference = window._difference_document
    window.set_layout_mode("Single View")
    navigation_labels = [
        window.viewer.header.navigation_layout.itemAt(index).widget().text()
        for index in range(window.viewer.header.navigation_layout.count())
    ]
    assert navigation_labels == ["1", "2", "3", "Diff"]
    window._navigate_single_view("difference")
    assert window.viewer.document is first_difference

    window.difference_panel.a_selector.setCurrentIndex(1)
    window.difference_panel.b_selector.setCurrentIndex(2)
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_source_ids
        == (documents[1].document_id, documents[2].document_id),
        timeout=3000,
    )
    assert window._difference_document is not first_difference
    assert len(window.multi_compare_view.occupied_viewers) == 4
    window.close()


def test_difference_preview_refreshes_only_diff_tile(qtbot: object, monkeypatch: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((8, 10, 3), index * 20, dtype=np.uint8), f"preview-{index}.png"
        )
        for index in range(2)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window.central_stack.currentWidget() is window.multi_compare_view,
        timeout=3000,
    )
    difference = window._difference_document
    assert difference is not None
    numerical = np.full((8, 10, 3), 7, dtype=np.uint8)
    preview = np.full((8, 10, 3), 31, dtype=np.uint8)

    def fail_render(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("display-only Diff update rebuilt every image tile")

    monkeypatch.setattr(window, "_render_selection", fail_render)  # type: ignore[attr-defined]
    window._difference_preview_updated("Diff updated", numerical, preview)
    assert window._difference_document is difference
    assert difference.preview is preview
    assert any(
        viewer.document is difference for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_six_images_with_difference_force_single_view_and_lock_multi(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(np.full((8, 10, 3), index, dtype=np.uint8), f"six-{index}.png")
        for index in range(6)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window.central_stack.currentWidget() is window.viewer,
        timeout=3000,
    )
    assert window.viewer.document is window._difference_document
    assert window._layout_mode == "Single View"
    assert not window.action_map["Multi View"].isEnabled()
    assert not hasattr(window, "_resident_document_limit")
    layout_model = window.layout_selector.model()
    multi_index = window.layout_selector.findText("Multi View")
    assert not layout_model.item(multi_index).isEnabled()
    window.close()
