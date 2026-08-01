from __future__ import annotations

from pathlib import Path
from threading import Event

import cv2
import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QPointF, QSettings, Qt
from PySide6.QtGui import QKeySequence, QPalette
from PySide6.QtWidgets import QAbstractItemView, QApplication, QDialog, QMessageBox

import pixelscope.ui.comparison_analysis_panel as comparison_module
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
from pixelscope.ui.image_viewer import ImageViewer, RoiViewBox
from pixelscope.ui.pixel_inspector import PixelInspector
from pixelscope.ui.raw_open_dialog import RawOpenDialog


@pytest.fixture(autouse=True)
def isolated_ui_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    QSettings().clear()


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
    assert window.analysis_tabs.tabText(1) == "Difference"
    assert window.bottom_tabs.count() == 2
    assert window.bottom_tabs.tabText(0) == "Histogram"
    assert window.bottom_tabs.tabText(1) == "Line Profile"
    toolbar_text = {action.text() for action in window.main_toolbar.actions()}
    assert not {"Open Image", "Open Folder", "Open RAW"}.intersection(toolbar_text)
    assert {
        "Fit Image",
        "100% Zoom",
        "Zoom In",
        "Zoom Out",
        "Diff",
        "Plots",
        "Export",
    }.issubset(toolbar_text)
    assert not {"Cursor", "ROI", "Set A", "Set B", "Swap A/B"}.intersection(toolbar_text)
    assert window.bottom_dock.isHidden()
    assert window.main_toolbar.objectName() == "mainToolbar"
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
    view_action = next(action for action in window.menuBar().actions() if action.text() == "&View")
    view_menu = view_action.menu()
    assert view_menu is not None
    assert not any("Difference" in action.text() for action in view_menu.actions())
    assert window.action_map["Previous Image"].shortcut().isEmpty()
    assert window.action_map["Next Image"].shortcut().isEmpty()
    assert QKeySequence(Qt.Key.Key_Left) in shortcut_keys
    assert QKeySequence(Qt.Key.Key_Right) in shortcut_keys
    window.close()


def test_layout_tool_and_file_state_models(qtbot: object, tmp_path: Path) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((4, 5, 3), index, dtype=np.uint8),
            f"state-{index + 1}.png",
            source_path=tmp_path / f"state-{index + 1}.png",
        )
        for index in range(3)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([documents[0].document_id])

    layout_model = window.layout_selector.model()
    enabled = {
        window.layout_selector.itemText(index): layout_model.item(index).isEnabled()
        for index in range(window.layout_selector.count())
    }
    assert enabled == {
        "Auto": True,
        "Single View": True,
        "Multi View": True,
    }
    window._select_document_ids([document.document_id for document in documents[:2]])
    assert window._effective_layout(2) == ("Side by Side", 2)
    window._select_document_ids([document.document_id for document in documents])
    assert window._effective_layout(3) == ("Focus + 2", 4)
    window.set_layout_mode("Single View")
    assert window._effective_layout(3) == ("Single", 1)
    window.set_layout_mode("Multi View")
    assert window._effective_layout(3) == ("Focus + 2", 4)

    plots_action = next(
        action for action in window.main_toolbar.actions() if action.text() == "Plots"
    )
    plots_action.trigger()
    assert not window.bottom_dock.isHidden()
    assert window.bottom_tabs.currentIndex() == 0
    window._show_plot_tab(1)
    assert window.bottom_tabs.currentIndex() == 1
    plots_action.trigger()
    assert window.bottom_dock.isHidden()

    group = window.document_list.topLevelItem(0)
    child = group.child(0)
    assert group.font(0).bold()
    assert not group.icon(0).isNull()
    assert not child.icon(0).isNull()
    assert child.text(1) == ""
    assert group.child(1).foreground(0).color().name() == "#e7e9ec"
    assert window.palette().color(QPalette.ColorRole.HighlightedText).name() == "#101316"
    window._select_document_ids([document.document_id for document in documents[:2]])
    window.compare_selection()
    assert [group.child(index).text(1) for index in range(3)] == ["", "", ""]
    assert group.child(0).font(0).bold()
    window.close()


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
        transform = DisplayTransform(black_level=0, white_level=1023)
        return ImageDocument.from_array(
            source,
            name,
            channel_layout="BAYER",
            bit_depth=10,
            raw_profile=profile,
            display_transform=transform,
            prepared_preview=render_bayer_preview(source, transform),
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
    window._compare_pair = None
    window._select_document_ids([rgb_a.document_id, bayer.document_id])
    assert not window.difference_panel.calculate.isEnabled()
    assert "RGB and Bayer" in window.difference_panel.status.text()

    different_size = ImageDocument.from_array(
        np.ones((7, 8, 3), dtype=np.uint8),
        "different.png",
    )
    window.add_document(different_size, select=False)
    window._select_document_ids([rgb_a.document_id, different_size.document_id])
    assert "dimensions" in window.difference_panel.status.text()
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
        window._difference_document,
        first,
        second,
    ]
    assert [
        viewer.header.badge.text() for viewer in window.multi_compare_view.occupied_viewers
    ] == ["Diff", "1", "2"]
    assert window.multi_compare_view.viewers[0].document is window._difference_document
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
    window.show_selected_image(2)
    assert window.viewer.document is window._difference_document
    window.close()


def test_single_header_navigation_avoids_full_workspace_render(
    qtbot: object, monkeypatch: object
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first = ImageDocument.from_array(np.zeros((8, 8, 3), dtype=np.uint8), "fast-a.png")
    second = ImageDocument.from_array(np.ones((8, 8, 3), dtype=np.uint8), "fast-b.png")
    window.add_document(first, select=False)
    window.add_document(second, select=False)
    window._select_document_ids([first.document_id, second.document_id])
    window.set_layout_mode("Single View")

    def fail_render(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("single-header navigation rebuilt the workspace")

    monkeypatch.setattr(window, "_render_selection", fail_render)  # type: ignore[attr-defined]
    window._navigate_single_view(second.document_id)
    assert window.viewer.document is second
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


def test_single_view_plots_cover_all_selected_images_with_legends_and_tooltips(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((12, 16, 3), 20 + index, dtype=np.uint8),
            "same-name.png",
            source_path=tmp_path / f"folder-{index + 1}" / "same-name.png",
        )
        for index in range(2)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Single View")
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 2,
        timeout=3000,
    )

    histogram = window.comparison_analysis_panel
    assert not histogram.plots[0].isHidden()
    assert not histogram.plots[1].isHidden()
    assert len(histogram.legends[0].items) == 3
    assert len(histogram.legends[1].items) == 3
    point = histogram.plots[1].getViewBox().mapViewToScene(QPointF(21, 10))
    histogram._on_histogram_mouse_moved(1, point)
    hint = histogram._histogram_hover_texts[1]
    assert hint is not None and hint.isVisible()
    assert "same-name.png" in hint.toPlainText()
    histogram_range = histogram.plots[1].getViewBox().viewRange()
    assert histogram_range[0][0] <= hint.pos().x() <= histogram_range[0][1]
    assert histogram_range[1][0] <= hint.pos().y() <= histogram_range[1][1]

    assert window.difference_panel.a_selector.itemText(0).startswith("folder-1 / ")
    assert window.difference_panel.b_selector.itemText(1).startswith("folder-2 / ")
    assert window.difference_panel.a_selector.count() == 2
    assert not hasattr(window.difference_panel, "manual_low")
    assert not hasattr(window.difference_panel, "manual_high")
    assert (
        window.comparison_analysis_panel.image_summary.item(0, 1).text().startswith("folder-1 / ")
    )

    window._shared_line_changed(LineSelection(1, 4, 14))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.line_profile_panel.last_results) == 2,
        timeout=3000,
    )
    profile = window.line_profile_panel
    profile.view_mode.setCurrentText("Separate by image")
    assert "folder-2 / same-name.png" in profile.plots[1].plotItem.titleLabel.text
    assert len(profile.legends[1].items) == 3
    profile_point = profile.plots[1].getViewBox().mapViewToScene(QPointF(2, 21))
    profile._on_plot_mouse_moved(profile_point, 1)
    profile_hint = profile._hover_texts[1]
    assert profile_hint is not None and profile_hint.isVisible()
    assert "same-name.png" in profile_hint.toPlainText()
    profile_range = profile.plots[1].getViewBox().viewRange()
    assert profile_range[0][0] <= profile_hint.pos().x() <= profile_range[0][1]
    assert profile_range[1][0] <= profile_hint.pos().y() <= profile_range[1][1]
    window.close()


def test_pending_document_keeps_previous_pixels_until_replacement_is_ready(
    qtbot: object, tmp_path: Path
) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    previous = ImageDocument.from_array(np.full((8, 9), 17, dtype=np.uint8), "previous.png")
    pending = ImageDocument.pending_document(tmp_path / "next.png")
    replacement = ImageDocument.from_array(
        np.full((8, 9), 31, dtype=np.uint8),
        "next.png",
        source_path=pending.source_path,
    )
    viewer.set_document(previous)
    previous_pixels = np.asarray(viewer.image_item.image).copy()
    viewer.set_document(pending, fit=False)
    assert viewer.document is previous
    assert viewer._loading_item.isVisible()
    assert np.array_equal(viewer.image_item.image, previous_pixels)
    viewer.set_document(replacement, fit=False)
    assert viewer.document is replacement
    assert not viewer._loading_item.isVisible()
    assert np.all(viewer.image_item.image == 31)


def test_plot_dock_resize_preserves_image_scale_and_floating_controls(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    document = ImageDocument.from_array(np.zeros((300, 500, 3), dtype=np.uint8), "zoom.png")
    window.add_document(document)
    window.show()
    qtbot.wait(30)  # type: ignore[attr-defined]
    window.viewer.zoom_100_percent()
    initial_zoom = window.viewer.zoom_percent
    assert initial_zoom is not None
    window._show_bottom_results()
    window.resizeDocks([window.bottom_dock], [360], Qt.Orientation.Vertical)
    qtbot.wait(50)  # type: ignore[attr-defined]
    assert window.viewer.zoom_percent == pytest.approx(initial_zoom, rel=0.03)

    title = window.plots_dock_title
    assert title.close_button.toolTip() == "Hide Plots"
    assert title.maximize_button.toolTip() == "Maximize Plots"
    docked_float_icon = title.float_button.icon().cacheKey()
    maximize_icon = title.maximize_button.icon().cacheKey()
    assert docked_float_icon != maximize_icon
    title.maximize_button.click()
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert window.bottom_dock.isFloating()
    assert window.bottom_dock.isMaximized()
    assert title.float_button.icon().cacheKey() != docked_float_icon
    assert title.maximize_button.icon().cacheKey() != maximize_icon
    title.maximize_button.click()
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert not window.bottom_dock.isFloating()
    assert not window.bottom_dock.isMaximized()

    title.float_button.click()
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert window.bottom_dock.isFloating()
    title.maximize_button.click()
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert window.bottom_dock.isMaximized()
    title.maximize_button.click()
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert window.bottom_dock.isFloating()
    assert not window.bottom_dock.isMaximized()
    title.float_button.click()
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert not window.bottom_dock.isFloating()
    window.close()


def test_single_to_multi_after_three_folder_selection_displays_all_images(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    selected_ids: list[str] = []
    for folder_index in range(5):
        folder = tmp_path / f"folder-{folder_index}"
        folder.mkdir()
        path = folder / "frame.png"
        assert cv2.imwrite(str(path), np.full((12, 16, 3), 30 + folder_index, dtype=np.uint8))
        selected_ids.extend(
            window._register_inputs(discover_image_inputs((folder,)), select_all=False)[:1]
        )

    window.set_layout_mode("Single View")
    window._select_document_ids(selected_ids[:3])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.preview is not None for document in window.selected_documents),
        timeout=3000,
    )
    window.set_layout_mode("Multi View")
    window.resize(1200, 800)
    window.show()
    qtbot.wait(200)  # type: ignore[attr-defined]
    assert window.central_stack.currentWidget() is window.multi_compare_view
    occupied = window.multi_compare_view.occupied_viewers
    assert {viewer.document.document_id for viewer in occupied if viewer.document} == set(
        selected_ids[:3]
    )
    assert all(viewer.image_item.image is not None for viewer in occupied)

    for count in (4, 5):
        window._select_document_ids(selected_ids[:count])
        qtbot.wait(200)  # type: ignore[attr-defined]
        occupied = window.multi_compare_view.occupied_viewers
        assert len(occupied) == count
        for viewer in occupied:
            assert viewer.document is not None
            assert viewer.image_item.image is not None
            assert viewer.document.preview is not None
            height, width = viewer.document.preview.shape[:2]
            x_range, y_range = viewer.view_box.viewRange()
            assert x_range[0] <= width / 2.0 <= x_range[1]
            assert y_range[0] <= height / 2.0 <= y_range[1]
    window.close()


def test_reloaded_same_document_preview_is_uploaded_after_pending_clear(qtbot: object) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    document = ImageDocument.from_array(np.full((5, 7), 9, dtype=np.uint8), "reload.png")
    preview = document.preview
    assert preview is not None
    viewer.set_document(document)
    document.preview = None
    document.loading_state = "pending"
    viewer.set_document(document)
    assert viewer.image_item.image is None
    document.preview = preview
    document.loading_state = "ready"
    viewer.set_document(document, fit=False)
    assert viewer._displayed_preview is preview
    assert np.array_equal(viewer.image_item.image, preview)


def test_multi_view_focus_keeps_logical_badges_and_arrow_keys_cycle_reference(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((20, 30, 3), index, dtype=np.uint8),
            f"image-{index + 1}.png",
            source_path=tmp_path / "set" / f"image-{index + 1}.png",
        )
        for index in range(4)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    window._set_focus_document(documents[2])
    assert window.multi_compare_view.viewers[0].document is documents[2]
    assert window.multi_compare_view.viewers[0].header.badge.text() == "3"
    assert all(
        not viewer.header.focus.isHidden() for viewer in window.multi_compare_view.occupied_viewers
    )
    window.show()
    window.activateWindow()
    qtbot.wait(20)  # type: ignore[attr-defined]
    window.multi_compare_view.zoom_100_percent()
    zoom = window.multi_compare_view.viewers[0].zoom_percent
    window.multi_compare_view.viewers[0].setFocus()
    qtbot.keyClick(window.multi_compare_view.viewers[0], Qt.Key.Key_Right)  # type: ignore[attr-defined]
    assert window._focus_document_id == documents[3].document_id
    assert window.multi_compare_view.viewers[0].document is documents[3]
    assert window.multi_compare_view.viewers[0].header.badge.text() == "4"
    assert window.multi_compare_view.viewers[0].zoom_percent == pytest.approx(zoom, rel=0.01)

    window.set_layout_mode("Single View")
    assert window.viewer.document is documents[3]
    assert window.viewer.header.badge.isHidden()
    assert window.viewer.header.navigation_layout.count() == 4
    assert "set / image-4.png" in window.viewer.header.name.text()
    window.close()


def test_reselecting_multi_view_is_noop_and_reference_order_pushes(
    qtbot: object, monkeypatch: object
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((8, 10, 3), index, dtype=np.uint8), f"order-{index + 1}.png"
        )
        for index in range(4)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")
    window._set_focus_document(documents[2])
    window._set_focus_document(documents[3])
    assert [viewer.document for viewer in window.multi_compare_view.occupied_viewers] == [
        documents[3],
        documents[2],
        documents[0],
        documents[1],
    ]

    def fail_render(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("same layout selection rebuilt the workspace")

    monkeypatch.setattr(window, "_render_selection", fail_render)  # type: ignore[attr-defined]
    window.set_layout_mode("Multi View")
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
        *documents,
        window._difference_document,
    ]
    first_difference = window._difference_document
    window.set_layout_mode("Single View")
    navigation_labels = [
        window.viewer.header.navigation_layout.itemAt(index).widget().text()
        for index in range(window.viewer.header.navigation_layout.count())
    ]
    assert navigation_labels == ["1", "2", "3", "Diff"]
    window.show_selected_image(3)
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
    assert window._resident_document_limit == 7
    layout_model = window.layout_selector.model()
    multi_index = window.layout_selector.findText("Multi View")
    assert not layout_model.item(multi_index).isEnabled()
    window.close()


def test_statistics_shows_busy_indicator_during_background_analysis(
    qtbot: object, monkeypatch: object
) -> None:
    started = Event()
    release = Event()
    original = comparison_module.analyze_roi

    def delayed_analysis(*args: object, **kwargs: object) -> object:
        started.set()
        release.wait(2.0)
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(comparison_module, "analyze_roi", delayed_analysis)  # type: ignore[attr-defined]
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    document = ImageDocument.from_array(np.zeros((32, 32, 3), dtype=np.uint8), "wait.png")
    window.add_document(document)
    qtbot.waitUntil(started.is_set, timeout=1500)  # type: ignore[attr-defined]
    assert not window.comparison_analysis_panel.busy.isHidden()
    assert window.comparison_analysis_panel.status.text() == "Calculating..."
    release.set()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.comparison_analysis_panel.busy.isHidden(),
        timeout=3000,
    )
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


def test_rgb_channel_split_uses_three_automatic_views(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    document = ImageDocument.from_array(np.zeros((6, 8, 4), dtype=np.uint8), "rgba.png")
    window.add_document(document)
    split_action = window.action_map["Split Channels"]
    split_action.trigger()
    assert window._layout_mode == "Multi View"
    split_documents = [viewer.document for viewer in window.multi_compare_view.viewers[:4]]
    assert [item.channel_layout for item in split_documents if item is not None] == [
        "CHANNEL_R",
        "CHANNEL_G",
        "CHANNEL_B",
    ]
    assert split_documents[3] is None
    window.close()


def test_plain_drag_is_pan_only_and_crosshair_recovers(qtbot: object) -> None:
    viewer = ImageViewer()
    qtbot.addWidget(viewer)  # type: ignore[attr-defined]
    viewer.set_document(
        ImageDocument.from_array(np.arange(100, dtype=np.uint8).reshape(10, 10), "drag")
    )
    viewer.set_interaction_mode("line")
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.NoModifier) is None
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.AltModifier) == "line"
    assert RoiViewBox.gesture_for_modifiers(Qt.KeyboardModifier.ControlModifier) == "roi"

    inside = viewer.view_box.mapViewToScene(QPointF(3.2, 4.2))
    outside = viewer.view_box.mapViewToScene(QPointF(-2.0, -2.0))
    viewer._on_scene_mouse_moved(inside)
    assert viewer._vertical_cursor.isVisible()
    assert viewer._horizontal_cursor.isVisible()
    viewer._on_scene_mouse_moved(outside)
    assert not viewer._vertical_cursor.isVisible()
    viewer._on_scene_mouse_moved(inside)
    assert viewer._vertical_cursor.isVisible()
    assert viewer._horizontal_cursor.isVisible()


def test_smart_layout_focus_and_profile_dock(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((8, 12, 3), index * 10, dtype=np.uint8),
            f"smart-layout-{index + 1}.png",
        )
        for index in range(3)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])

    grid = window.multi_compare_view._layout
    first_position = grid.getItemPosition(grid.indexOf(window.multi_compare_view.viewers[0]))
    assert first_position == (0, 0, 2, 1)
    assert grid.rowStretch(2) == 0
    selection_before_focus = [document.document_id for document in window.selected_documents]
    window._set_focus_document(documents[2])
    assert window.multi_compare_view.viewers[0].document is documents[2]
    assert [
        document.document_id for document in window.selected_documents
    ] == selection_before_focus
    assert not window.multi_compare_view.viewers[0].header.focus.isHidden()

    assert not hasattr(window.multi_compare_view.viewers[0].header, "solo")

    assert window.bottom_dock.isHidden()
    window._shared_line_changed(LineSelection(1, 3, 10))
    assert not window.bottom_dock.isHidden()
    assert window.bottom_tabs.currentWidget() is window.line_profile_panel
    assert window.dockWidgetArea(window.bottom_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
    window.show()
    window.bottom_dock.setFloating(True)
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert window.bottom_dock.isFloating()
    assert window.redock_plots_action.isEnabled()
    floating_position = window.bottom_dock.pos()
    qtbot.mouseClick(  # type: ignore[attr-defined]
        window.multi_compare_view.viewers[0]._graphics.viewport(),
        Qt.MouseButton.LeftButton,
    )
    qtbot.wait(20)  # type: ignore[attr-defined]
    assert window.bottom_dock.pos() == floating_position
    window._redock_plots()
    assert not window.bottom_dock.isFloating()
    window.close()


def test_histogram_modes_csv_and_workspace_settings(qtbot: object, tmp_path: Path) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    documents = [
        ImageDocument.from_array(
            np.full((8, 8, 3), index * 40, dtype=np.uint8),
            f"histogram-{index + 1}.png",
        )
        for index in range(2)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 2,
        timeout=3000,
    )
    panel = window.comparison_analysis_panel
    panel.histogram_mode.setCurrentText("Overlay")
    panel.histogram_units.setCurrentText("Normalized")
    panel.histogram_range.setCurrentText("Normalized 0–1")
    assert not panel.plots[0].isHidden()
    assert panel.plots[1].isHidden()
    assert len(panel.plots[0].listDataItems()) == 6
    for curve in panel.plots[0].listDataItems():
        x_values, y_values = curve.getData()
        assert float(np.min(x_values)) >= 0
        assert float(np.max(x_values)) <= 1
        assert np.isclose(float(np.sum(y_values)), 1.0)

    export_path = tmp_path / "statistics.csv"
    panel.export_csv(export_path)
    exported = export_path.read_text(encoding="utf-8-sig")
    assert exported.startswith("Id,Image,Samples")
    assert "2,histogram-2.png,64" in exported
    assert "Id,Ch,Min,Max,Mean,Std,P1,P50,P99" in exported
    assert "2,B,40,40,40" in exported

    window.set_layout_mode("Multi View")
    window.main_splitter.setSizes([450, 950])
    window._show_plot_tab(1)
    saved_sidebar_width = window.main_splitter.sizes()[0]
    window._save_ui_state()
    window.close()
    restored = MainWindow()
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    assert restored._layout_mode == "Multi View"
    assert restored.layout_selector.currentText() == "Multi View"
    assert restored.main_splitter.sizes()[0] == saved_sidebar_width
    assert not restored.bottom_dock.isHidden()
    assert restored.bottom_tabs.currentIndex() == 1
    assert restored.dockWidgetArea(restored.bottom_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
    restored.reset_workspace_layout()
    assert restored._layout_mode == "Auto"
    assert restored.bottom_dock.isHidden()
    restored.close()


def test_multi_selection_compare_toggle_stats_and_difference(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    a = ImageDocument.from_array(np.zeros((8, 8, 3), dtype=np.uint8), "a.png")
    b = ImageDocument.from_array(np.full((8, 8, 3), 20, dtype=np.uint8), "b.png")
    window.add_document(a)
    window.add_document(b, select=False)
    window._select_document_ids([a.document_id, b.document_id])

    assert window.selected_documents == [a, b]
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
    assert table.rowCount() == 6
    assert table.columnCount() == 9
    assert table.horizontalHeaderItem(0).text() == "Id"
    assert table.horizontalHeaderItem(1).text() == "Ch"
    assert table.item(3, 0).text() == "2"
    assert table.item(3, 1).text() == "R"
    assert table.item(3, 4).text() == "20"
    assert table.item(3, 0).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    assert table.item(3, 1).textAlignment() & Qt.AlignmentFlag.AlignHCenter
    summary = window.comparison_analysis_panel.image_summary
    assert summary.rowCount() == 2
    assert summary.item(1, 0).text() == "2"
    assert summary.item(1, 1).text().endswith("b.png")
    assert summary.item(1, 2).text() == "64"
    assert window.comparison_analysis_panel.status.text() == ""
    assert window.comparison_analysis_panel.roi_label.text() == "Full image"
    histogram_plots = window.comparison_analysis_panel.plots[:2]
    assert all(not plot.isHidden() for plot in histogram_plots)
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
    assert profile_curves[0].opts["pen"].style() == Qt.PenStyle.SolidLine
    assert profile_curves[3].opts["pen"].style() == Qt.PenStyle.CustomDashLine
    assert all(curve.opts.get("symbol") is None for curve in profile_curves)
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
    assert "1 (R   0, G   0, B   0)" in window.structured_status.pixel_value.text()
    assert "2 (R  20, G  20, B  20)" in window.structured_status.pixel_value.text()
    assert "Img" not in window.structured_status.pixel_value.text()
    assert "TYPE" not in window.structured_status.pixel_value.text()

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
    assert window.pixel_status.text() == "Position (   1,    2)"
    assert window.structured_status.pixel_value.text() == "1 (R  20, G  20, B  20)"
    assert "TYPE" not in window.structured_status.pixel_value.text()

    qtbot.keyClick(window.viewer, Qt.Key.Key_1)  # type: ignore[attr-defined]
    assert window.viewer.document is a
    window.analysis_tabs.setCurrentWidget(window.difference_panel)
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.central_stack.currentWidget() is window.viewer
        and window.viewer.document is window._difference_document,
        timeout=3000,
    )
    assert window._difference_document is not None
    assert np.all(window._difference_document.source == 20)
    assert window.analysis_tabs.currentWidget() is window.difference_panel
    assert "all R, G, and B samples combined" in window.difference_panel.metric_scope.text()
    assert not hasattr(window.difference_panel, "plot")
    assert window._layout_mode == "Single View"
    assert not window.viewer.header.navigation.isHidden()
    window._navigate_single_view(a.document_id)
    assert window.viewer.document is a
    window._navigate_single_view("difference")
    assert window.viewer.document is window._difference_document
    difference_range = window.viewer.view_box.viewRange()
    window.difference_panel.gain.setValue(3)
    assert window.viewer.document is window._difference_document
    assert np.allclose(window.viewer.view_box.viewRange(), difference_range)
    qtbot.keyClick(window.viewer, Qt.Key.Key_2)  # type: ignore[attr-defined]
    assert window.viewer.document is b
    qtbot.keyClick(window.viewer, Qt.Key.Key_Right)  # type: ignore[attr-defined]
    assert window.viewer.document is window._difference_document
    qtbot.keyClick(window.viewer, Qt.Key.Key_Left)  # type: ignore[attr-defined]
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
    assert window._layout_mode == "Multi View"
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
    assert window.document_list.topLevelItem(0).child(0).text(0) == "drop0.png"
    assert window.document_list.topLevelItem(0).child(0).text(1) == ""
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
    for index, plot in enumerate(window.comparison_analysis_panel.plots):
        position = window.comparison_analysis_panel.histogram_layout.getItemPosition(
            window.comparison_analysis_panel.histogram_layout.indexOf(plot)
        )
        assert position[:2] == (index, 0)

    window.set_layout_mode("Single View")
    window.show()
    window.activateWindow()
    window.viewer.setFocus()
    qtbot.wait(10)  # type: ignore[attr-defined]
    qtbot.keyClick(window.viewer, Qt.Key.Key_Right)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[1]
    qtbot.keyClick(window.viewer, Qt.Key.Key_Left)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[0]
    qtbot.keyClick(window.viewer, Qt.Key.Key_6)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[5]
    assert window.viewer.header.text() == "[6/6] selected-6.png"
    qtbot.keyClick(window.viewer, Qt.Key.Key_1)  # type: ignore[attr-defined]
    assert window.viewer.document is documents[0]
    window.close()


def test_auto_grid_paging_with_seven_selected_images(qtbot: object) -> None:
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
    assert window._layout_mode == "Multi View"
    assert window._view_capacity == 6

    window.next_image()
    assert window.multi_compare_view.viewers[0].document is documents[6]
    assert all(viewer.document is None for viewer in window.multi_compare_view.viewers[1:6])
    window.next_image()
    assert window.multi_compare_view.viewers[0].document is documents[0]
    window.previous_image()
    assert window.multi_compare_view.viewers[0].document is documents[6]
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
        assert group.child(0).text(0) == "image2.png"
        assert group.child(1).text(0) == "image10.png"
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


def test_folder_pair_navigation_recalculates_enabled_difference_and_keeps_focus(
    qtbot: object, tmp_path: Path
) -> None:
    folders = [tmp_path / name for name in ("reference", "candidate")]
    for folder_index, folder in enumerate(folders):
        folder.mkdir()
        for image_index in range(2):
            assert cv2.imwrite(
                str(folder / f"frame-{image_index}.png"),
                np.full((20, 24, 3), folder_index * 10 + image_index, dtype=np.uint8),
            )
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.register_folder_pair(folders[0], folders[1])
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(document.source is not None for document in window.selected_documents),
        timeout=3000,
    )
    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None and window.diff_action.isChecked(),
        timeout=3000,
    )
    stale_difference = window._difference_document
    window._set_focus_document(window.selected_documents[1])
    window.next_folder_pair()
    assert window._view_capacity == 4
    assert window._difference_document is stale_difference
    assert len(window.multi_compare_view.occupied_viewers) == 3
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_source_ids
        == tuple(document.document_id for document in window.selected_documents)
        and len(window.multi_compare_view.occupied_viewers) == 3,
        timeout=5000,
    )
    assert [document.display_name for document in window.selected_documents] == [
        "frame-1.png",
        "frame-1.png",
    ]
    assert window._focus_document_id == window.selected_documents[1].document_id
    assert window.multi_compare_view.viewers[0].document is window.selected_documents[1]
    window.close()


def test_rapid_three_folder_navigation_coalesces_loads_and_bounds_resident_images(
    qtbot: object, tmp_path: Path
) -> None:
    folders = [tmp_path / name for name in ("camera-a", "camera-b", "camera-c")]
    first_ids: list[str] = []
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    for folder_index, folder in enumerate(folders):
        folder.mkdir()
        for image_index in range(8):
            image = np.full(
                (96, 160, 3),
                folder_index * 20 + image_index,
                dtype=np.uint8,
            )
            assert cv2.imwrite(str(folder / f"chart-{image_index:02d}.jpg"), image)
        ids = window._register_inputs(discover_image_inputs((folder,)), select_all=False)
        first_ids.append(ids[0])

    window._select_document_ids(first_ids)
    for _index in range(5):
        window.next_folder_pair()
    assert [document.display_name for document in window.selected_documents] == [
        "chart-05.jpg",
        "chart-05.jpg",
        "chart-05.jpg",
    ]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window._workers
        and all(document.source is not None for document in window.selected_documents),
        timeout=5000,
    )

    # Walk the remaining positions normally as well; decoded arrays behind the
    # current working set must be released instead of accumulating indefinitely.
    for _index in range(2):
        window.next_folder_pair()
        qtbot.waitUntil(  # type: ignore[attr-defined]
            lambda: not window._workers
            and all(document.source is not None for document in window.selected_documents),
            timeout=5000,
        )
    resident = [
        document
        for document in window.documents.values()
        if document.source_path is not None and document.source is not None
    ]
    assert len(resident) <= window._resident_document_limit
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 3,
        timeout=3000,
    )
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
    assert window.document_list.currentItem().text(0) == "bad.png"
    assert "!" in window.document_list.currentItem().text(1)
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
        and window.comparison_analysis_panel.table.item(0, 6) is not None
        and window.comparison_analysis_panel.table.item(0, 6).text() == "77",
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
    assert [window.comparison_analysis_panel.table.item(row, 6).text() for row in range(3)] == [
        "0",
        "0",
        "0",
    ]
    assert all(
        len(plot.listDataItems()) == 3 for plot in window.comparison_analysis_panel.plots[:2]
    )
    window._inspect_pixel(1, 2, (0, 0, 0, 255))
    assert "(   0,    0,    0,  255)" not in window.structured_status.pixel_value.text()
    assert "1 (R   0, G   0, B   0)" in window.structured_status.pixel_value.text()

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
    assert profile_curves[0].opts["pen"].style() == Qt.PenStyle.SolidLine
    assert profile_curves[3].opts["pen"].style() == Qt.PenStyle.CustomDashLine

    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None
        and window.central_stack.currentWidget() is window.multi_compare_view,
        timeout=3000,
    )
    assert window._difference_document is not None
    assert window._difference_document.source is not None
    assert window._difference_document.source.shape == (5, 6, 3)
    assert np.all(window._difference_document.source == 20)
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
    assert not hasattr(dialog, "name")
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
    assert table.item(0, 0).toolTip().find("10-bit") >= 0
    assert window.comparison_analysis_panel.image_summary.item(0, 2).text() == "16"
    assert [table.item(row, 4).text() for row in range(4)] == [
        "11.5",
        "21.5",
        "31.5",
        "41.5",
    ]
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
    window.line_profile_panel.channel_buttons["Gr"].setChecked(False)
    window.line_profile_panel.channel_buttons["Gb"].setChecked(False)
    profile_curves = [
        item
        for item in window.line_profile_panel.plot.listDataItems()
        if isinstance(item, pg.PlotDataItem)
    ]
    assert len(profile_curves) == 2

    window._inspect_pixel(1, 0, 20)
    assert "1 Gr   20" in window.structured_status.pixel_value.text()
    window.set_view_capacity(4)
    split_action = window.action_map["Split Channels"]
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
