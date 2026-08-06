from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QAbstractItemView

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


def test_statistics_region_detail_row_is_stable_and_summary_uses_pixels(
    qtbot: object,
) -> None:
    panel = ComparisonAnalysisPanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    documents = [_rgb_document("a.png", 10), _rgb_document("b.png", 20)]

    detail_height = panel.roi_label.height()
    panel.set_documents(documents, None, "Full image")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(panel.last_results) == 2,
        timeout=3000,
    )
    assert panel.image_summary.horizontalHeaderItem(2).text() == "Pixels"
    assert panel.roi_label.text() == ""
    assert panel.roi_label.height() == detail_height
    assert panel.image_summary.item(0, 2).text() == "80"

    panel.set_documents(documents, RoiBounds(1, 2, 3, 4), "Active ROI")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(panel.last_results) == 2 and panel.image_summary.item(0, 2).text() == "12",
        timeout=3000,
    )
    assert panel.roi_label.text() == "x=1, y=2, width=3, height=4"
    assert panel.roi_label.height() == detail_height


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

    assert panel.image_summary.item(0, 2).text() == "16"
    assert panel.table.rowCount() == 4
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
    documents = [_rgb_document(f"primary-{index}.png", index) for index in range(5)]

    view.set_capacity(4)
    view.set_documents(documents[:4], 0, 4, None, None)
    assert all(not viewer.header.focus.isHidden() for viewer in view.occupied_viewers)
    assert view.occupied_viewers[0].header.focus.isChecked()

    view.set_capacity(6)
    view.set_documents(documents, 0, 5, None, None)
    assert all(not viewer.header.focus.isHidden() for viewer in view.occupied_viewers)
    assert view.occupied_viewers[0].header.focus.isChecked()
