from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QAbstractItemView, QApplication, QDialog, QMessageBox

from pixelscope.app.application import create_application
from pixelscope.app.main_window import MainWindow
from pixelscope.core.bayer import render_bayer_preview
from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.io.path_discovery import ImageInput, discover_image_inputs
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.comparison_analysis_panel import automatic_histogram_spec
from pixelscope.ui.image_viewer import ImageViewer
from pixelscope.ui.pixel_inspector import PixelInspector
from pixelscope.ui.raw_open_dialog import RawOpenDialog


def test_application_and_selection_driven_main_window(qtbot: object) -> None:
    assert isinstance(create_application([]), QApplication)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    document = ImageDocument.from_array(np.arange(16, dtype=np.uint16).reshape(4, 4), "a")
    window.add_document(document)

    assert window.current_document is document
    assert window.viewer.document is document
    assert window.main_splitter.widget(0).minimumWidth() == 320
    assert window.document_list.selectionMode() == (
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    assert window.files_label.text() == "Files"
    assert window.analysis_tabs.count() == 2
    assert window.analysis_tabs.tabText(0) == "Statistics"
    assert window.analysis_tabs.tabText(1) == "Histogram"
    assert window.analysis_tabs.widget(1) is window.comparison_analysis_panel.histogram_grid
    assert window.viewer_splitter.widget(1) is window.line_profile_panel
    assert [action.text() for action in window.menuBar().actions()] == [
        "&File",
        "&Edit",
        "&Selection",
        "&View",
    ]
    assert "Select A" not in window.action_map
    assert "Compare A/B" not in window.action_map
    assert "Compare Two Folders..." not in window.action_map
    shortcut_keys = {shortcut.key() for shortcut in window._selection_shortcuts}
    assert QKeySequence(Qt.Key.Key_PageUp) in shortcut_keys
    assert QKeySequence(Qt.Key.Key_PageDown) in shortcut_keys
    assert window.action_map["100% Zoom"].shortcut() == QKeySequence("Ctrl+0")
    assert not window.action_map["Show Signed Difference"].isEnabled()
    window.close()


def test_viewer_pixel_and_ctrl_drag_roi(qtbot: object) -> None:
    viewer = ImageViewer()
    inspector = PixelInspector()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    qtbot.addWidget(inspector)  # type: ignore[attr-defined]
    document = ImageDocument.from_array(np.arange(100, dtype=np.uint8).reshape(10, 10), "pixel")
    viewer.set_document(document)
    inspector.update_document(document, 0, 0)
    assert inspector.value_text() == "0"

    with qtbot.waitSignal(viewer.roi_changed):  # type: ignore[attr-defined]
        viewer._on_roi_dragged((QPointF(2.2, 3.1), QPointF(7.8, 8.0)), True)
    assert viewer.current_roi_bounds() == RoiBounds(2, 3, 6, 5)
    viewer.clear_roi()
    assert viewer.current_roi_bounds() is None

    with qtbot.waitSignal(viewer.line_changed):  # type: ignore[attr-defined]
        viewer._on_line_dragged((QPointF(1.2, 6.7), QPointF(8.8, 2.0)), True)
    assert viewer.line_selection == LineSelection(1, 6, 8)
    viewer.clear_line()
    assert viewer.line_selection is None


def test_multi_selection_compare_toggle_stats_and_difference(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    a = ImageDocument.from_array(np.zeros((8, 8, 3), dtype=np.uint8), "a.png")
    b = ImageDocument.from_array(np.full((8, 8, 3), 20, dtype=np.uint8), "b.png")
    window.add_document(a)
    window.add_document(b, select=False)
    window._select_document_ids([a.document_id, b.document_id])

    assert window.selected_documents == [a, b]
    assert window.action_map["Show Signed Difference"].isEnabled()
    assert window.action_map["Show Absolute Difference"].isEnabled()
    window.compare_selection()
    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert window.multi_compare_view.viewers[0].document is a
    assert window.multi_compare_view.viewers[1].document is b
    assert window.multi_compare_view.viewers[0].header.text() == "[1/2] a.png"
    assert window.multi_compare_view.viewers[1].header.text() == "[2/2] b.png"

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 2,
        timeout=3000,
    )
    table = window.comparison_analysis_panel.table
    assert table.rowCount() == 9
    assert table.columnCount() == 2
    assert table.item(1, 1).text() == "8-bit"
    assert table.item(2, 1).text() == "R: 20\nG: 20\nB: 20"
    assert table.item(3, 1).text() == "R: 20\nG: 20\nB: 20"
    assert table.item(4, 1).text() == "R: 20\nG: 20\nB: 20"
    assert window.comparison_analysis_panel.status.text() == ""
    assert window.comparison_analysis_panel.roi_label.text() == "Full image"
    assert table.horizontalHeaderItem(0).text().startswith("1\n")
    assert table.horizontalHeaderItem(1).text().startswith("2\n")
    assert window.comparison_analysis_panel.layout().stretch(1) == 1
    histogram_plots = window.comparison_analysis_panel.plots[:2]
    assert all(
        plot.isVisibleTo(window.comparison_analysis_panel.histogram_grid)
        for plot in histogram_plots
    )
    assert window.comparison_analysis_panel.histogram_layout.getItemPosition(
        window.comparison_analysis_panel.histogram_layout.indexOf(histogram_plots[0])
    )[:2] == (0, 0)
    assert window.comparison_analysis_panel.histogram_layout.getItemPosition(
        window.comparison_analysis_panel.histogram_layout.indexOf(histogram_plots[1])
    )[:2] == (1, 0)
    for plot in histogram_plots:
        histogram_bars = plot.listDataItems()
        assert len(histogram_bars) == 3
        assert [bar.opts["pen"].color().name() for bar in histogram_bars] == [
            "#ff3b30",
            "#24b34b",
            "#2684ff",
        ]
        assert all(bar.opts["stepMode"] == "center" for bar in histogram_bars)
        assert all(bar.opts["fillLevel"] == 0.0 for bar in histogram_bars)
        assert all(bar.opts["fillBrush"] is not None for bar in histogram_bars)
    window.comparison_analysis_panel.channel_buttons["B"].setChecked(False)
    assert all(len(plot.listDataItems()) == 2 for plot in histogram_plots)

    window._shared_line_changed(LineSelection(1, 4, 6))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.line_profile_panel.last_results) == 2,
        timeout=3000,
    )
    profile_curves = [
        item
        for item in window.line_profile_panel.plot.listDataItems()
        if isinstance(item, pg.PlotDataItem)
    ]
    assert len(profile_curves) == 6
    assert all(line.opts["pen"].style() == Qt.PenStyle.SolidLine for line in profile_curves)
    marker_symbols = {
        item.opts["symbol"]
        for item in window.line_profile_panel.plot.items()
        if isinstance(item, pg.ScatterPlotItem)
    }
    assert {"o", "s"}.issubset(marker_symbols)
    y_max = window.line_profile_panel.plot.getViewBox().viewRange()[1][1]
    scene_position = window.line_profile_panel.plot.getViewBox().mapViewToScene(QPointF(2, y_max))
    window.line_profile_panel._on_plot_mouse_moved(scene_position)
    assert window.line_profile_panel._hover_text is not None
    assert window.line_profile_panel._hover_text.isVisible()
    assert "R:" in window.line_profile_panel._hover_text.toPlainText()
    assert window.line_profile_panel._hover_text.anchor.y() == 0
    window.line_profile_panel.channel_buttons["R"].setChecked(False)
    assert (
        len(
            [
                item
                for item in window.line_profile_panel.plot.listDataItems()
                if isinstance(item, pg.PlotDataItem)
            ]
        )
        == 4
    )

    window._inspect_multi_pixel(a, 1, 2, (0, 0, 0))
    assert window.pixel_status.text().startswith("Position (   1,    2)")
    assert "  |  1 (R   0, G   0, B   0)" in window.pixel_status.text()
    assert "  |  2 (R  20, G  20, B  20)" in window.pixel_status.text()
    assert "Img" not in window.pixel_status.text()
    assert "TYPE" not in window.pixel_status.text()

    window.set_view_capacity(1)
    assert window.viewer.document is a
    window.show()
    window.activateWindow()
    window.viewer.setFocus()
    qtbot.wait(10)  # type: ignore[attr-defined]
    window.viewer.view_box.setRange(xRange=(1.0, 6.0), yRange=(1.0, 6.0), padding=0)
    original_range = window.viewer.view_box.viewRange()
    qtbot.keyClick(window.viewer, Qt.Key.Key_2)  # type: ignore[attr-defined]
    assert window.viewer.document is b
    assert window.viewer.header.text() == "[2/2] b.png"
    assert np.allclose(window.viewer.view_box.viewRange(), original_range)
    assert window.pixel_status.text() == "Position (   -,    -)"

    window._inspect_pixel(1, 2, (20, 20, 20))
    assert window.pixel_status.text() == ("Position (   1,    2)  |  1 (R  20, G  20, B  20)")
    assert "TYPE" not in window.pixel_status.text()
    assert "b.png" not in window.pixel_status.text()

    qtbot.keyClick(window.viewer, Qt.Key.Key_1)  # type: ignore[attr-defined]
    assert window.viewer.document is a
    qtbot.keyClick(window.viewer, Qt.Key.Key_D)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer.document is not None
        and window.viewer.document.display_name.startswith("Signed:"),
        timeout=3000,
    )
    assert window.viewer.document is not None
    assert np.all(window.viewer.document.source == -20)
    qtbot.keyClick(window.viewer, Qt.Key.Key_2)  # type: ignore[attr-defined]
    assert window.viewer.document is b
    window.close()


def test_drop_appends_to_multiview_preserves_range_and_deduplicates(
    qtbot: object, tmp_path: Path
) -> None:
    paths = [tmp_path / f"drop{index}.png" for index in range(3)]
    for index, path in enumerate(paths):
        assert cv2.imwrite(str(path), np.full((30, 40), index * 10, dtype=np.uint8))
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first_inputs = discover_image_inputs(paths[:2])
    window._register_inputs(first_inputs, select_all=True)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.source is not None for document in window.selected_documents),
        timeout=3000,
    )
    window.set_view_capacity(2)
    window.multi_compare_view.viewers[0].view_box.setRange(
        xRange=(5.0, 20.0), yRange=(4.0, 19.0), padding=0
    )
    original_range = window.multi_compare_view.viewers[0].view_box.viewRange()

    window._handle_dropped_paths([paths[2]])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.selected_documents) == 3
        and all(document.source is not None for document in window.selected_documents),
        timeout=3000,
    )
    assert window._view_capacity == 4
    assert [viewer.document for viewer in window.multi_compare_view.viewers[:3]] == (
        window.selected_documents
    )
    assert np.allclose(
        window.multi_compare_view.viewers[0].view_box.viewRange(),
        original_range,
    )
    same_folder_selection = [document.document_id for document in window.selected_documents]
    window.show()
    window.activateWindow()
    window.document_list.setFocus()
    qtbot.keyClick(window.document_list, Qt.Key.Key_PageDown)  # type: ignore[attr-defined]
    assert [document.document_id for document in window.selected_documents] == same_folder_selection
    assert "different folder" in window.statusBar().currentMessage()
    window.show()
    qtbot.wait(10)  # type: ignore[attr-defined]
    before_resize = window.multi_compare_view.viewers[0].view_box.viewRange()
    before_center = [(axis_range[0] + axis_range[1]) / 2 for axis_range in before_resize]
    window.resize(1650, 920)
    qtbot.wait(20)  # type: ignore[attr-defined]
    after_resize = window.multi_compare_view.viewers[0].view_box.viewRange()
    after_center = [(axis_range[0] + axis_range[1]) / 2 for axis_range in after_resize]
    assert np.allclose(after_center, before_center)
    for viewer in window.multi_compare_view.viewers[:3]:
        viewer_range = viewer.view_box.viewRange()
        viewer_center = [(axis_range[0] + axis_range[1]) / 2 for axis_range in viewer_range]
        assert np.allclose(viewer_center, after_center)
        assert np.allclose(
            viewer.view_box.viewPixelSize(),
            window.multi_compare_view.viewers[0].view_box.viewPixelSize(),
            rtol=0.02,
        )

    window._register_inputs(discover_image_inputs((tmp_path,)), select_all=False)
    assert len(window.documents) == 3
    assert window.document_list.document_count == 3
    assert window.document_list.topLevelItemCount() == 1
    assert window.document_list.topLevelItem(0).childCount() == 3
    assert window.document_list.topLevelItem(0).child(0).text(0).startswith("[1/3] ")
    window.close()


def test_grid_slots_and_shared_roi(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(np.full((12, 16), index, dtype=np.uint16), f"{index}.png")
        for index in range(3)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_view_capacity(4)
    qtbot.wait(10)  # type: ignore[attr-defined]

    assert [viewer.document for viewer in window.multi_compare_view.viewers[:4]] == [
        *documents,
        None,
    ]
    fitted_range = window.multi_compare_view.viewers[0].view_box.viewRange()
    assert fitted_range[0][0] <= 0 and fitted_range[0][1] >= 16
    assert fitted_range[1][0] <= 0 and fitted_range[1][1] >= 12
    window._shared_roi_changed(RoiBounds(2, 3, 7, 6))
    assert all(
        viewer.current_roi_bounds() == RoiBounds(2, 3, 7, 6)
        for viewer in window.multi_compare_view.viewers[:3]
    )
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 3
        and all(
            result.pixel_count == 42 for result in window.comparison_analysis_panel.last_results
        ),
        timeout=3000,
    )
    assert all(result.pixel_count == 42 for result in window.comparison_analysis_panel.last_results)
    third_plot = window.comparison_analysis_panel.plots[2]
    assert window.comparison_analysis_panel.histogram_layout.getItemPosition(
        window.comparison_analysis_panel.histogram_layout.indexOf(third_plot)
    )[:2] == (2, 0)
    assert not window.comparison_analysis_panel.plots[3].isVisibleTo(
        window.comparison_analysis_panel
    )
    window.clear_roi()
    assert all(
        viewer.current_roi_bounds() is None for viewer in window.multi_compare_view.viewers[:3]
    )
    window.close()


def test_single_view_number_shortcuts_and_six_histogram_grid(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((4, 4), index, dtype=np.uint8),
            f"selected-{index + 1}.png",
        )
        for index in range(6)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 6,
        timeout=3000,
    )
    assert not window.action_map["Show Signed Difference"].isEnabled()
    for index, plot in enumerate(window.comparison_analysis_panel.plots):
        position = window.comparison_analysis_panel.histogram_layout.getItemPosition(
            window.comparison_analysis_panel.histogram_layout.indexOf(plot)
        )
        assert position[:2] == (index, 0)

    window.show()
    window.activateWindow()
    window.viewer.setFocus()
    qtbot.wait(10)  # type: ignore[attr-defined]
    qtbot.keyClick(window.viewer, Qt.Key.Key_6)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[5]
    assert window.viewer.header.text() == "[6/6] selected-6.png"
    qtbot.keyClick(window.viewer, Qt.Key.Key_1)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[0]
    window.close()


def test_four_viewer_paging_with_seven_selected_images(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(np.full((3, 3), index, dtype=np.uint8), f"{index}.png")
        for index in range(7)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_view_capacity(4)

    window.next_image()
    assert [viewer.document for viewer in window.multi_compare_view.viewers[:4]] == [
        documents[4],
        documents[5],
        documents[6],
        None,
    ]
    window.next_image()
    assert window.multi_compare_view.viewers[0].document is documents[0]
    window.previous_image()
    assert window.multi_compare_view.viewers[0].document is documents[4]
    window.close()


def test_folder_pairs_are_naturally_sorted_and_loaded_lazily(qtbot: object, tmp_path: Path) -> None:
    folder_a = tmp_path / "a"
    folder_b = tmp_path / "b"
    folder_a.mkdir()
    folder_b.mkdir()
    for name, value in (("image10.png", 10), ("image2.png", 2)):
        assert cv2.imwrite(str(folder_a / name), np.full((4, 4), value, dtype=np.uint8))
        assert cv2.imwrite(str(folder_b / name), np.full((4, 4), value + 1, dtype=np.uint8))

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.register_folder_pair(folder_a, folder_b)
    assert window.document_list.topLevelItemCount() == 2
    assert sorted(
        window.document_list.topLevelItem(index).childCount()
        for index in range(window.document_list.topLevelItemCount())
    ) == [2, 2]
    assert [document.display_name for document in window.selected_documents] == [
        "image2.png",
        "image2.png",
    ]
    for group_index in range(2):
        group = window.document_list.topLevelItem(group_index)
        assert group.child(0).text(0).startswith("[1/2] ")
        assert group.child(0).text(0).endswith("image2.png")
        assert group.child(1).text(0).startswith("[2/2] ")
        assert group.child(1).text(0).endswith("image10.png")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.source is not None for document in window.selected_documents),
        timeout=3000,
    )
    pending_count = sum(
        document.loading_state == "pending" for document in window.documents.values()
    )
    assert pending_count == 2

    qtbot.keyClick(window.document_list, Qt.Key.Key_PageDown)  # type: ignore[attr-defined]
    assert [document.display_name for document in window.selected_documents] == [
        "image10.png",
        "image10.png",
    ]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.source is not None for document in window.selected_documents),
        timeout=3000,
    )
    selected_at_end = [document.document_id for document in window.selected_documents]
    window.show()
    window.activateWindow()
    window.viewer.setFocus()
    qtbot.wait(10)  # type: ignore[attr-defined]
    qtbot.keyClick(window.viewer, Qt.Key.Key_PageDown)  # type: ignore[attr-defined]
    assert [document.document_id for document in window.selected_documents] == selected_at_end
    assert "No next image" in window.statusBar().currentMessage()
    qtbot.keyClick(window.viewer, Qt.Key.Key_PageUp)  # type: ignore[attr-defined]
    assert [document.display_name for document in window.selected_documents] == [
        "image2.png",
        "image2.png",
    ]
    window.close()


def test_new_files_update_an_active_multi_folder_pair(
    qtbot: object, tmp_path: Path, monkeypatch: object
) -> None:
    folders = [tmp_path / name for name in ("a", "b", "c")]
    for folder_index, folder in enumerate(folders):
        folder.mkdir()
        for image_index in (1, 2):
            assert cv2.imwrite(
                str(folder / f"image{image_index}.png"),
                np.full(
                    (4, 4),
                    folder_index * 20 + image_index,
                    dtype=np.uint8,
                ),
            )

    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.register_folder_pair(folders[0], folders[1])
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    window._handle_dropped_paths([folders[2] / "image2.png"])
    assert window.document_list.topLevelItemCount() == 3
    assert sorted(
        window.document_list.topLevelItem(index).childCount()
        for index in range(window.document_list.topLevelItemCount())
    ) == [2, 2, 2]
    assert [document.display_name for document in window.selected_documents] == [
        "image1.png",
        "image1.png",
        "image2.png",
    ]

    selection_at_shortest_end = [document.document_id for document in window.selected_documents]
    window.next_folder_pair()
    assert [
        document.document_id for document in window.selected_documents
    ] == selection_at_shortest_end
    assert "No next image" in window.statusBar().currentMessage()

    monkeypatch.setattr(  # type: ignore[attr-defined]
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )
    window._handle_dropped_paths([folders[0] / "image2.png"])
    assert window.selected_documents[0].display_name == "image1.png"

    monkeypatch.setattr(  # type: ignore[attr-defined]
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    window._handle_dropped_paths([folders[0] / "image2.png"])
    assert window.selected_documents[0].display_name == "image2.png"
    folder_key = window._folder_key(folders[0] / "image2.png")
    assert window._folder_indices[folder_key] == 1
    window.close()


def test_error_document_can_be_registered(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    error = ImageDocument.error_document("bad.png", "decode failed", Path("bad.png"))
    window.add_document(error)
    assert error.loading_state == "error"
    assert window.document_list.currentItem().text(0) == "[1/1] [error] bad.png"
    window.close()


def test_selection_refreshes_histogram_and_resets_pixel_status(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first = ImageDocument.from_array(np.zeros((5, 5, 3), dtype=np.uint8), "first.png")
    second = ImageDocument.from_array(np.full((5, 5, 3), 77, dtype=np.uint8), "second.png")
    window.add_document(first)
    window.add_document(second, select=False)

    window._inspect_pixel(3, 4, (0, 0, 0))
    window._select_document_ids([second.document_id])
    assert window.pixel_status.text() == "Position (   -,    -)"
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 1
        and window.comparison_analysis_panel.table.item(4, 0) is not None
        and window.comparison_analysis_panel.table.item(4, 0).text() == "R: 77\nG: 77\nB: 77",
        timeout=3000,
    )
    assert len(window.comparison_analysis_panel.plot.listDataItems()) == 3
    window.close()


def test_rgba_comparison_ignores_alpha_in_stats_and_plots(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first_pixels = np.zeros((5, 6, 4), dtype=np.uint8)
    second_pixels = np.full((5, 6, 4), 20, dtype=np.uint8)
    first_pixels[..., 3] = 255
    second_pixels[..., 3] = 3
    first = ImageDocument.from_array(first_pixels, "rgba-a.png")
    second = ImageDocument.from_array(second_pixels, "rgba-b.png")
    window.add_document(first)
    window.add_document(second, select=False)
    window._select_document_ids([first.document_id, second.document_id])

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 2,
        timeout=3000,
    )
    assert window.comparison_analysis_panel.table.item(4, 0).text() == ("R: 0\nG: 0\nB: 0")
    assert "A:" not in window.comparison_analysis_panel.table.item(4, 0).text()
    assert all(
        len(plot.listDataItems()) == 3 for plot in window.comparison_analysis_panel.plots[:2]
    )
    window._inspect_pixel(1, 2, (0, 0, 0, 255))
    assert "(   0,    0,    0,  255)" not in window.pixel_status.text()
    assert "1 (R   0, G   0, B   0)" in window.pixel_status.text()

    window._shared_line_changed(LineSelection(0, 2, 5))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.line_profile_panel.last_results) == 2,
        timeout=3000,
    )
    profile_curves = [
        item
        for item in window.line_profile_panel.plot.listDataItems()
        if isinstance(item, pg.PlotDataItem)
    ]
    assert len(profile_curves) == 6
    assert all(line.opts["pen"].style() == Qt.PenStyle.SolidLine for line in profile_curves)

    window.show_signed_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.viewer.document is not None
        and window.viewer.document.display_name.startswith("Signed:"),
        timeout=3000,
    )
    assert window.viewer.document is not None
    assert window.viewer.document.source is not None
    assert window.viewer.document.source.shape == (5, 6, 3)
    assert np.all(window.viewer.document.source == -20)
    window.close()


def test_raw_dialog_prefills_all_bayer_profile_values(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    profile = RawProfile(
        name="camera",
        width=8,
        height=6,
        dtype="uint16",
        stride_bytes=20,
        offset_bytes=16,
        endianness="big",
        bit_depth=12,
        packing="unpacked_u16",
        channel_layout="BAYER",
        bayer_pattern="GBRG",
        black_level=(64, 65, 66, 67),
        white_level=4095,
    )
    dialog.set_profile(profile)
    assert dialog.name.text() == "camera"
    assert dialog.width_box.value() == 8
    assert dialog.height_box.value() == 6
    assert dialog.stride.value() == 20
    assert dialog.offset.value() == 16
    assert dialog.endian.currentText() == "big"
    assert dialog.bit_depth.value() == 12
    assert dialog.layout_kind.currentText() == "BAYER"
    assert dialog.bayer_pattern.currentText() == "GBRG"
    assert dialog.black.text() == "64, 65, 66, 67"
    assert dialog.profile() == profile


def test_raw_sidecar_confirmation_and_same_path_reload(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    raw_path = tmp_path / "sensor.raw"
    np.arange(16, dtype=np.uint16).tofile(raw_path)
    sidecar = tmp_path / "sensor.json"
    initial_profile = RawProfile(
        name="initial",
        width=4,
        height=4,
        dtype="uint16",
        stride_bytes=8,
        bit_depth=10,
        packing="unpacked_u16",
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=(0, 0, 0, 0),
        white_level=1023,
    )
    initial_profile.save_json(sidecar)

    class ConfirmRawDialog:
        override: RawProfile | None = None
        loaded_profiles: list[RawProfile] = []

        def __init__(self, _parent: object) -> None:
            self.loaded: RawProfile | None = None

        def set_profile(self, profile: RawProfile) -> None:
            self.loaded = profile
            self.loaded_profiles.append(profile)

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def profile(self) -> RawProfile:
            assert self.loaded is not None
            return self.override or self.loaded

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "pixelscope.app.main_window.RawOpenDialog",
        ConfirmRawDialog,
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    image_input = ImageInput(raw_path, sidecar)
    window._handle_dropped_paths([raw_path])
    document_ids = list(window.documents)
    assert len(document_ids) == 1
    document_id = document_ids[0]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document_id].source is not None,
        timeout=3000,
    )
    first_document = window.documents[document_id]
    assert ConfirmRawDialog.loaded_profiles[0] == initial_profile
    assert first_document.shape == (4, 4)
    assert first_document.preview is not None
    assert np.all(first_document.preview[..., 1] >= first_document.preview[..., 0])

    ConfirmRawDialog.override = initial_profile.copy(
        update={
            "name": "reloaded",
            "width": 2,
            "height": 8,
            "stride_bytes": 4,
            "bayer_pattern": "BGGR",
        }
    )
    generation = first_document.generation
    reloaded_ids = window._register_inputs((image_input,), select_all=True)
    assert reloaded_ids == [document_id]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.documents[document_id].source is not None
        and window.documents[document_id].shape == (8, 2),
        timeout=3000,
    )
    reloaded = window.documents[document_id]
    assert len(window.documents) == 1
    assert reloaded.generation > generation
    assert reloaded.raw_profile.bayer_pattern == "BGGR"
    window.close()


def test_bayer_statistics_profiles_status_and_channel_split(qtbot: object) -> None:
    source = np.array(
        [
            [10, 20, 11, 21],
            [30, 40, 31, 41],
            [12, 22, 13, 23],
            [32, 42, 33, 43],
        ],
        dtype=np.uint16,
    )
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
    transform = DisplayTransform(black_level=0, white_level=1023)
    document = ImageDocument.from_array(
        source,
        "bayer.raw",
        channel_layout="BAYER",
        bit_depth=10,
        raw_profile=profile,
        display_transform=transform,
        prepared_preview=render_bayer_preview(source, transform),
    )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.add_document(document)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 1,
        timeout=3000,
    )
    result = window.comparison_analysis_panel.last_results[0]
    assert result.channel_names == ("R", "Gr", "Gb", "B")
    table = window.comparison_analysis_panel.table
    assert table.item(1, 0).text() == "10-bit"
    assert table.item(4, 0).text() == ("R: 11.5\nGr: 21.5\nGb: 31.5\nB: 41.5")
    histogram = window.comparison_analysis_panel.plots[0]
    assert [item.name() for item in histogram.listDataItems()] == [
        "R",
        "Gr",
        "Gb",
        "B",
    ]
    window.comparison_analysis_panel.channel_buttons["G"].setChecked(False)
    assert [item.name() for item in histogram.listDataItems()] == ["R", "B"]
    window.comparison_analysis_panel.channel_buttons["G"].setChecked(True)

    window._shared_line_changed(LineSelection(0, 0, 3))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.line_profile_panel.last_results) == 1,
        timeout=3000,
    )
    profile_result = window.line_profile_panel.last_results[0]
    assert profile_result.channel_names == ("R", "Gr", "Gb", "B")
    assert profile_result.positions[1].tolist() == [1.0, 3.0]
    hover_position = window.line_profile_panel.plot.getViewBox().mapViewToScene(QPointF(0, 25))
    window.line_profile_panel._on_plot_mouse_moved(hover_position)
    assert window.line_profile_panel._hover_text is not None
    assert "Gr@1" in window.line_profile_panel._hover_text.toPlainText()
    assert "Gb:" in window.line_profile_panel._hover_text.toPlainText()
    window.line_profile_panel.channel_buttons["G"].setChecked(False)
    profile_curves = [
        item
        for item in window.line_profile_panel.plot.listDataItems()
        if isinstance(item, pg.PlotDataItem)
    ]
    assert len(profile_curves) == 2

    window._inspect_pixel(1, 0, 20)
    assert "1 Gr   20" in window.pixel_status.text()
    window.set_view_capacity(4)
    split_action = window.action_map["Split Channels in 4 Views"]
    assert split_action.isEnabled()
    split_action.trigger()
    split_documents = [viewer.document for viewer in window.multi_compare_view.viewers[:4]]
    assert [item.channel_layout for item in split_documents if item is not None] == [
        "CHANNEL_R",
        "CHANNEL_Gr",
        "CHANNEL_Gb",
        "CHANNEL_B",
    ]
    assert all(item is not None and item.shape == (2, 2) for item in split_documents)
    window.close()


def test_histogram_bins_follow_effective_bit_depth() -> None:
    raw10 = ImageDocument.from_array(
        np.arange(16, dtype=np.uint16).reshape(4, 4),
        "raw10",
        bit_depth=10,
    )
    assert automatic_histogram_spec(raw10) == (1024, (0.0, 1024.0))
