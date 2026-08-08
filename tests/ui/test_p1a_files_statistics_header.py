from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView

from pixelscope.app.main_window import MainWindow
from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.comparison_analysis_panel import ComparisonAnalysisPanel
from pixelscope.ui.document_list import DocumentListWidget
from pixelscope.ui.multi_compare_view import MultiCompareView
from pixelscope.ui.tile_header import TileHeader


def _rgb_document(name: str, value: int = 0, source_path: Path | None = None) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((8, 10, 3), value, dtype=np.uint8),
        name,
        source_path=source_path,
    )


def test_files_tree_uses_icons_and_row_state_without_visible_compare_roles(
    qtbot: object,
    tmp_path: Path,
) -> None:
    tree = DocumentListWidget()
    qtbot.addWidget(tree)  # type: ignore[attr-defined]
    image_item = tree.add_document_item(
        "image",
        "image.png",
        tmp_path / "image.png",
    )
    raw_item = tree.add_document_item(
        "raw",
        "frame.raw",
        tmp_path / "frame.raw",
    )

    assert tree.columnCount() == 2
    assert [tree.headerItem().text(index) for index in range(2)] == ["File", "Type"]
    assert tree.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectRows
    assert not hasattr(tree, "compare_role_requested")
    assert image_item.text(1) == "PNG"
    assert raw_item.text(1) == "RAW"
    assert not image_item.icon(0).isNull()
    assert not raw_item.icon(0).isNull()
    assert image_item.icon(0).cacheKey() != raw_item.icon(0).cacheKey()

    ready_icon = image_item.icon(0).cacheKey()
    tree.set_document_state("image", loading_state="loading")
    loading_icon = image_item.icon(0).cacheKey()
    tree.set_document_state("image", loading_state="error")
    error_icon = image_item.icon(0).cacheKey()
    assert loading_icon != ready_icon
    assert error_icon != loading_icon

    tree.set_document_state("image", visible=True, active=True, role="A", slot=1)
    assert image_item.font(0).bold()
    assert bool(image_item.data(0, tree.ACTIVE_ROLE))
    assert image_item.text(0) == "image.png"
    assert image_item.text(1) == "PNG"
    assert "A" not in image_item.text(0)
    assert "A" not in image_item.text(1)


def test_difference_selectors_are_authoritative_and_tiles_have_no_a_b_badges(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [_rgb_document(f"image-{index + 1}.png", index) for index in range(3)]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")

    panel = window.difference_panel
    panel.a_selector.setCurrentIndex(2)
    panel.b_selector.setCurrentIndex(1)
    selected_ids = (panel.a_selector.currentData(), panel.b_selector.currentData())
    window._render_selection(preserve_view=True)

    assert not hasattr(window, "_compare_pair")
    assert (panel.a_selector.currentData(), panel.b_selector.currentData()) == selected_ids
    visible_viewers = window.multi_compare_view.viewers[:3]
    assert [viewer.document for viewer in visible_viewers] == documents
    assert [viewer.header.badge.text() for viewer in visible_viewers] == ["1", "2", "3"]


def test_statistics_sections_align_region_bounds_and_image_metadata(
    qtbot: object,
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    documents = [
        _rgb_document(
            "chart_03_frequency_patterns.jpg",
            10,
            Path("base") / "chart_03_frequency_patterns.jpg",
        ),
        _rgb_document("b.png", 20),
    ]
    panel.show()

    active_roi_index = panel.region_scope.findText("Active ROI")
    active_roi_model_index = panel.region_scope.model().index(active_roi_index, 0)
    assert not (
        panel.region_scope.model().flags(active_roi_model_index) & Qt.ItemFlag.ItemIsEnabled
    )
    assert not panel.image_summary.wordWrap()
    assert panel.image_summary.textElideMode() == Qt.TextElideMode.ElideMiddle
    assert panel.image_summary.verticalHeader().sectionResizeMode(0) == QHeaderView.ResizeMode.Fixed
    assert panel.region_group.title() == "1. Region"
    assert panel.image_summary_group.title() == "2. Images"
    assert panel.statistics_group.title() == "3. Channel statistics"
    assert panel.region_layout.indexOf(panel.region_scope) >= 0
    assert panel.region_layout.indexOf(panel.roi_label) >= 0
    assert panel.scope_label.width() == panel.bounds_label.width()
    root_layout = panel.layout()
    assert root_layout is not None
    assert root_layout.indexOf(panel.region_group) == 0
    assert root_layout.indexOf(panel.image_summary_group) == 1
    assert root_layout.indexOf(panel.statistics_group) == 2
    assert root_layout.indexOf(panel.activity) == 3

    panel.set_documents(documents, None, "Full image")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(panel.last_results) == 2,
        timeout=3000,
    )
    assert panel.image_summary.horizontalHeaderItem(2).text() == "Bit depth"
    assert panel.image_summary.horizontalHeaderItem(3).text() == "Pixels"
    assert panel.roi_label.text() == "x=0, y=0, width=10, height=8"
    assert panel.image_summary.item(0, 1).text() == "base / chart_03_frequency_patterns.jpg"
    assert panel.image_summary.item(0, 2).text() == "8-bit"
    assert panel.image_summary.item(0, 3).text() == "80"
    assert panel.image_summary.rowHeight(0) == panel.image_summary.rowHeight(1)
    assert panel.statistics_delegate.separator_rows == frozenset({3})
    assert panel.activity.isHidden()

    panel.set_documents(documents, RoiBounds(1, 2, 3, 4), "Active ROI")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(panel.last_results) == 2 and panel.image_summary.item(0, 3).text() == "12",
        timeout=3000,
    )
    assert panel.roi_label.text() == "x=1, y=2, width=3, height=4"
    assert panel.region_scope.model().flags(active_roi_model_index) & Qt.ItemFlag.ItemIsEnabled
    panel.set_roi_available(False)
    assert panel.region_scope.currentText() == "Full image"
    assert not (
        panel.region_scope.model().flags(active_roi_model_index) & Qt.ItemFlag.ItemIsEnabled
    )
    assert panel.activity.isHidden()


def test_main_window_tracks_active_roi_availability(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    document = _rgb_document("roi-state.png", 10)
    replacement = _rgb_document("replacement.png", 20)
    window.add_document(document)
    window.add_document(replacement, select=False)
    panel = window.comparison_analysis_panel
    active_roi_index = panel.region_scope.findText("Active ROI")
    active_roi_model_index = panel.region_scope.model().index(active_roi_index, 0)
    assert not (
        panel.region_scope.model().flags(active_roi_model_index) & Qt.ItemFlag.ItemIsEnabled
    )

    window._shared_roi_changed(RoiBounds(1, 2, 3, 4))
    assert panel.region_scope.model().flags(active_roi_model_index) & Qt.ItemFlag.ItemIsEnabled
    assert panel.region_scope.currentText() == "Active ROI"

    window._select_document_ids([replacement.document_id])
    assert panel.region_scope.currentText() == "Full image"
    assert not (
        panel.region_scope.model().flags(active_roi_model_index) & Qt.ItemFlag.ItemIsEnabled
    )

    window._shared_roi_changed(RoiBounds(1, 2, 3, 4))
    assert panel.region_scope.currentText() == "Active ROI"
    window.clear_roi()
    assert panel.region_scope.currentText() == "Full image"
    assert not (
        panel.region_scope.model().flags(active_roi_model_index) & Qt.ItemFlag.ItemIsEnabled
    )
    window.close()


def test_statistics_pixels_preserve_bayer_sample_count(qtbot: object) -> None:
    profile = RawProfile(
        name="bayer",
        width=4,
        height=4,
        dtype="uint16",
        stride_bytes=8,
        bit_depth=10,
        packing="unpacked_u16",
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=0,
        white_level=1023,
    )
    source = np.arange(16, dtype=np.uint16).reshape(4, 4)
    document = ImageDocument.from_array(
        source,
        "mosaic.raw",
        channel_layout="BAYER",
        bit_depth=10,
        raw_profile=profile,
        display_transform=DisplayTransform(black_level=0, white_level=1023),
    )
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    panel.set_documents([document], None)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(panel.last_results) == 1,
        timeout=3000,
    )

    assert panel.image_summary.item(0, 2).text() == "10-bit"
    assert panel.image_summary.item(0, 3).text() == "16"
    assert panel.table.rowCount() == 4
    assert panel.statistics_delegate.separator_rows == frozenset()
    assert [panel.table.item(row, 1).text() for row in range(4)] == ["R", "Gr", "Gb", "B"]


def test_tile_header_switches_between_full_and_compact_metadata(
    qtbot: object,
    tmp_path: Path,
) -> None:
    long_name = f"{'very-long-image-name-' * 8}.png"
    source_path = tmp_path / "folder" / long_name
    document = _rgb_document(long_name, 1, source_path)
    header = TileHeader()
    qtbot.addWidget(header)  # type: ignore[attr-defined]
    header.set_focus_control_visible(True)
    header.show()

    header.resize(760, header.height())
    header.set_document(document, slot=2)
    qtbot.waitUntil(lambda: not header.compact)  # type: ignore[attr-defined]
    assert header.meta.isVisible()
    assert "10×8" in header.meta.text()
    assert header.name.toolTip() == str(source_path)

    header.resize(TileHeader.COMPACT_WIDTH - 40, header.height())
    qtbot.waitUntil(lambda: header.compact)  # type: ignore[attr-defined]
    assert not header.meta.isVisible()
    assert header.badge.isVisible()
    assert header.zoom.isVisible()
    assert header.focus.isVisible()
    assert "…" in header.name.text()
    assert header.name.toolTip() == str(source_path)


def test_primary_flag_is_available_in_four_and_five_tile_layouts(qtbot: object) -> None:
    view = MultiCompareView()
    qtbot.addWidget(view)  # type: ignore[attr-defined]
    view.show()
    documents = [_rgb_document(f"primary-{index}.png", index) for index in range(5)]

    view.set_capacity(4)
    view.set_documents(documents[:4], 0, 4, None, None)
    assert all(not viewer.header.focus.isHidden() for viewer in view.occupied_viewers)
    assert view.occupied_viewers[0].header.focus.isChecked()

    view.set_capacity(6)
    view.set_documents(documents, 0, 5, None, None)
    assert all(not viewer.header.focus.isHidden() for viewer in view.occupied_viewers)
    assert view.occupied_viewers[0].header.focus.isChecked()
