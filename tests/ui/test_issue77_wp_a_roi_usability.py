from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.core.spatial_sampling import SpatialSampling
from pixelscope.core.yuv import NativeYuvFrame
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.comparison_analysis_panel import ComparisonAnalysisPanel
from pixelscope.ui.image_viewer import ImageViewer

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _document(
    name: str,
    shape: tuple[int, int] = (6, 8),
    *,
    channels: int | None = None,
    channel_layout: str | None = None,
    raw_profile: RawProfile | None = None,
    source_path: Path | None = None,
) -> ImageDocument:
    source_shape = shape if channels is None else (*shape, channels)
    return ImageDocument.from_array(
        np.arange(np.prod(source_shape), dtype=np.uint16).reshape(source_shape),
        name,
        channel_layout=channel_layout,
        bit_depth=10 if raw_profile is not None else 16,
        raw_profile=raw_profile,
        source_path=source_path,
    )


def _bayer_document() -> ImageDocument:
    profile = RawProfile(
        name="issue-77-bayer",
        width=8,
        height=6,
        dtype="uint16",
        stride_bytes=16,
        bit_depth=10,
        packing="unpacked_u16",
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=0,
        white_level=1023,
    )
    return _document(
        "mosaic.raw",
        channel_layout="BAYER",
        raw_profile=profile,
    )


def _yuv_document() -> ImageDocument:
    y = np.arange(48, dtype=np.uint8).reshape(6, 8)
    u = np.arange(12, dtype=np.uint8).reshape(3, 4)
    v = (u + 40).astype(np.uint8)
    return ImageDocument.from_yuv(NativeYuvFrame(y, u, v, "YUV420"), "native.yuv")


def _set_editor_bounds(panel: ComparisonAnalysisPanel, bounds: RoiBounds) -> None:
    panel.roi_x_input.setValue(bounds.x)
    panel.roi_y_input.setValue(bounds.y)
    panel.roi_width_input.setValue(bounds.width)
    panel.roi_height_input.setValue(bounds.height)


def _editor_bounds(panel: ComparisonAnalysisPanel) -> RoiBounds:
    return RoiBounds(
        panel.roi_x_input.value(),
        panel.roi_y_input.value(),
        panel.roi_width_input.value(),
        panel.roi_height_input.value(),
    )


def test_production_statistics_sidebar_uses_compact_roi_edit_affordance(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    window.add_document(_document("reference.png"))
    window.resize(1400, 850)
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]
    panel = window.comparison_analysis_panel
    followup = window.issue77_ui_design_followup

    assert not panel.roi_editor.isVisible()
    assert followup.roi_bounds_label.text() == "Bounds"
    assert followup.roi_bounds_label.isVisible()
    assert followup.roi_edit_button.isVisible()
    assert followup.roi_edit_button.isEnabled()
    assert panel.roi_label.isVisible()

    window.main_splitter.setSizes([320, 1080])
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert panel.width() <= 320
    assert followup.roi_edit_button.geometry().right() <= panel.width()
    window.close()


def test_numeric_editor_apply_enter_clear_and_drag_share_one_authority(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    gray = _document("gray.png")
    rgb = _document("rgb.png", channels=3)
    for document in (gray, rgb):
        window.add_document(document, select=False)
    window._select_document_ids([gray.document_id, rgb.document_id])
    panel = window.comparison_analysis_panel

    requested = RoiBounds(1, 2, 4, 3)
    _set_editor_bounds(panel, requested)
    qtbot.mouseClick(panel.roi_apply_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    assert window._shared_roi == requested
    assert _editor_bounds(panel) == requested
    assert all(
        viewer.current_roi_bounds() == requested
        for viewer in window.multi_compare_view.occupied_viewers
    )
    assert window.difference_panel._active_roi == requested
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(panel.last_results) == 2
        and all(result.bounds == requested for result in panel.last_results),
        timeout=3000,
    )

    enter_bounds = RoiBounds(2, 1, 3, 4)
    _set_editor_bounds(panel, enter_bounds)
    qtbot.keyClick(panel.roi_height_input, Qt.Key.Key_Return)  # type: ignore[attr-defined]
    assert window._shared_roi == enter_bounds

    dragged = RoiBounds(0, 0, 5, 5)
    window._shared_roi_changed(dragged)
    assert _editor_bounds(panel) == dragged

    qtbot.mouseClick(panel.roi_clear_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    assert window._shared_roi is None
    assert window.difference_panel._active_roi is None
    assert not panel.roi_clear_button.isEnabled()

    window._shared_roi_changed(requested)
    window.action_map["Clear ROI"].trigger()
    assert window._shared_roi is None
    assert all(
        viewer.current_roi_bounds() is None for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_selection_preserves_exact_roi_for_rgb_gray_bayer_and_yuv_or_clears_all(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    rgb = _document("rgb.png", channels=3)
    gray = _document("gray.png")
    bayer = _bayer_document()
    yuv = _yuv_document()
    too_small = _document("small.png", shape=(6, 7))
    for document in (rgb, gray, bayer, yuv, too_small):
        window.add_document(document, select=False)

    window._select_document_ids([rgb.document_id])
    exact = RoiBounds(4, 3, 4, 3)
    assert window._shared_roi_changed(exact)

    window._select_document_ids(
        [rgb.document_id, gray.document_id, bayer.document_id, yuv.document_id]
    )
    assert window._shared_roi == exact
    assert _editor_bounds(window.comparison_analysis_panel) == exact
    assert all(
        viewer.current_roi_bounds() == exact
        for viewer in window.multi_compare_view.occupied_viewers
    )

    window._select_document_ids([rgb.document_id, too_small.document_id])
    assert window._shared_roi is None
    assert window.comparison_analysis_panel.region_scope.currentText() == "Full image"
    assert all(
        viewer.current_roi_bounds() is None for viewer in window.multi_compare_view.occupied_viewers
    )
    assert "ROI cleared" in window.statusBar().currentMessage()
    window.close()


def test_invalid_numeric_or_drag_proposal_is_rejected_without_divergent_clipping(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    large = _document("large.png")
    small = _document("small.png", shape=(5, 6))
    for document in (large, small):
        window.add_document(document, select=False)
    window._select_document_ids([large.document_id, small.document_id])
    original = RoiBounds(1, 1, 3, 3)
    assert window._shared_roi_changed(original)

    invalid = RoiBounds(4, 2, 4, 3)
    _set_editor_bounds(window.comparison_analysis_panel, invalid)
    qtbot.mouseClick(  # type: ignore[attr-defined]
        window.comparison_analysis_panel.roi_apply_button,
        Qt.MouseButton.LeftButton,
    )

    assert window._shared_roi == original
    assert _editor_bounds(window.comparison_analysis_panel) == original
    assert all(
        viewer.current_roi_bounds() == original
        for viewer in window.multi_compare_view.occupied_viewers
    )
    assert "does not fit every comparison frame" in window.statusBar().currentMessage()
    window.close()


def test_mapped_difference_uses_reference_extent_for_editor_and_overlay(qtbot: object) -> None:
    sampling = SpatialSampling.cell_footprint(
        (6, 8),
        (3, 4),
        row_step=2,
        column_step=2,
    )
    difference = ImageDocument.from_array(
        np.arange(12, dtype=np.uint16).reshape(3, 4),
        "difference",
        channel_layout="DIFFERENCE",
        spatial_sampling=sampling,
    )
    panel = ComparisonAnalysisPanel()
    viewer = ImageViewer()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    panel.set_documents([difference], None)
    viewer.set_document(difference)

    assert difference.shape[:2] == (3, 4)
    assert difference.reference_shape == (6, 8)
    assert _editor_bounds(panel) == RoiBounds(0, 0, 8, 6)
    exact = RoiBounds(4, 2, 4, 4)
    panel.set_active_roi(exact)
    viewer.set_roi_bounds(exact)
    assert _editor_bounds(panel) == exact
    assert viewer.current_roi_bounds() == exact


def test_full_image_scope_keeps_active_roi_editor_authority(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    document = _document("gray.png")
    window.add_document(document)
    exact = RoiBounds(2, 1, 4, 3)
    assert window._shared_roi_changed(exact)

    window.comparison_analysis_panel.region_scope.setCurrentText("Full image")

    assert window._shared_roi == exact
    assert _editor_bounds(window.comparison_analysis_panel) == exact
    assert window.comparison_analysis_panel.region_scope.currentText() == "Full image"
    window.close()


def test_numeric_reference_roi_applies_during_yuv_split_without_enabling_split_drag(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    document = _yuv_document()
    window.add_document(document)
    window._set_split_channels(True)
    assert window._channel_split_active
    panel = window.comparison_analysis_panel
    exact = RoiBounds(4, 2, 4, 4)

    _set_editor_bounds(panel, exact)
    qtbot.mouseClick(panel.roi_apply_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    assert window._shared_roi == exact
    assert _editor_bounds(panel) == exact
    assert window.difference_panel._active_roi == exact
    window.multi_compare_view.occupied_viewers[0].set_roi_bounds(RoiBounds(0, 0, 2, 2))
    assert not window._shared_roi_changed(RoiBounds(0, 0, 2, 2))
    assert window._shared_roi == exact
    assert all(
        viewer.current_roi_bounds() is None for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_comparison_page_navigation_clears_roi_instead_of_clipping(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [_document(f"large-{index}.png") for index in range(6)]
    documents.append(_document("short-final-page.png", shape=(5, 7)))
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    exact = RoiBounds(4, 2, 4, 4)
    assert window._shared_roi_changed(exact)

    window.next_comparison_page()

    assert window._page_start == 6
    assert window._shared_roi is None
    assert window.viewer.current_roi_bounds() is None
    assert window.multi_compare_view.viewers[0].current_roi_bounds() is None
    window.previous_comparison_page()
    assert window._shared_roi is None
    window.close()


def test_folder_position_preserves_only_an_exact_all_target_roi(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first_folder = [
        _document("a1.png", source_path=tmp_path / "a" / "a1.png"),
        _document("a2.png", source_path=tmp_path / "a" / "a2.png"),
    ]
    second_folder = [
        _document("b1.png", source_path=tmp_path / "b" / "b1.png"),
        _document("b2.png", shape=(5, 7), source_path=tmp_path / "b" / "b2.png"),
    ]
    for document in (*first_folder, *second_folder):
        window.add_document(document, select=False)
    window._select_document_ids([first_folder[0].document_id, second_folder[0].document_id])
    exact = RoiBounds(4, 2, 4, 4)
    assert window._shared_roi_changed(exact)

    window.next_folder_position()

    assert [document.document_id for document in window.selected_documents] == [
        first_folder[1].document_id,
        second_folder[1].document_id,
    ]
    assert window._shared_roi is None
    window.close()
