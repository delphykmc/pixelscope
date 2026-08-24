from __future__ import annotations

from pathlib import Path
from threading import Event

import numpy as np
import pyqtgraph as pg
import pytest
from PySide6.QtCore import QPointF, Qt

import pixelscope.ui.comparison_analysis_panel as comparison_module
from pixelscope.app.main_window import MainWindow
from pixelscope.core.bayer import render_bayer_preview
from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineProfileResult, LineSelection, selected_line_profile
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.comparison_analysis_panel import automatic_histogram_spec
from pixelscope.ui.line_profile_panel import LineProfilePanel

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_single_view_plots_cover_all_selected_images_with_legends_and_tooltips(
    qtbot: object, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.show()
    window._show_plot_tab(0)
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
    point = histogram.plots[1].getViewBox().mapViewToScene(QPointF(20.5, 10))
    histogram._on_histogram_mouse_moved(1, point)
    hint = histogram._histogram_hover_texts[1]
    assert hint is not None and hint.isVisible()
    hover_text = hint.toPlainText()
    assert "Code 20.5" in hover_text
    assert "same-name.png" not in hover_text
    assert hover_text.splitlines() == [
        "Code 20.5",
        "2",
        "R",
        "0",
        "2",
        "G",
        "0",
        "2",
        "B",
        "0",
    ]
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
    profile_hover_text = profile_hint.toPlainText()
    assert "same-name.png" not in profile_hover_text
    assert profile_hover_text.splitlines() == [
        "Distance 2 px",
        "2",
        "R",
        "21",
        "2",
        "G",
        "21",
        "2",
        "B",
        "21",
    ]
    profile_range = profile.plots[1].getViewBox().viewRange()
    assert profile_range[0][0] <= profile_hint.pos().x() <= profile_range[0][1]
    assert profile_range[1][0] <= profile_hint.pos().y() <= profile_range[1][1]
    window.close()


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
    resize_zoom_samples: list[float] = []
    window.viewer.zoom_changed.connect(resize_zoom_samples.append)
    window._show_bottom_results()
    window.resizeDocks([window.bottom_dock], [360], Qt.Orientation.Vertical)
    qtbot.wait(50)  # type: ignore[attr-defined]
    assert window.viewer.zoom_percent == pytest.approx(initial_zoom, rel=0.03)
    assert all(zoom == pytest.approx(initial_zoom, rel=0.03) for zoom in resize_zoom_samples)

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


def test_line_profile_separate_modes_share_available_height_equally(qtbot: object) -> None:
    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    selection = LineSelection(0, 3, 31)
    documents = [
        ImageDocument.from_array(
            np.full((8, 32, 3), 20 + index, dtype=np.uint8),
            f"image-{index + 1}.png",
        )
        for index in range(3)
    ]
    results: tuple[LineProfileResult, ...] = tuple(
        selected_line_profile(document.source, selection)  # type: ignore[arg-type]
        for document in documents
    )
    panel._documents = documents
    panel._selection = selection
    panel.last_results = results
    panel.resize(900, 850)
    panel.show()
    panel._render(results)

    for mode in ("Separate by image", "Overlay", "Separate by channel"):
        panel.view_mode.setCurrentText(mode)
        qtbot.wait(20)  # type: ignore[attr-defined]
        if mode == "Overlay":
            continue
        visible = [plot for plot in panel.plots if not plot.isHidden()]
        assert len(visible) == 3
        heights = [plot.height() for plot in visible]
        assert max(heights) - min(heights) <= 2


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
    assert window._focus_document_id == documents[0].document_id
    first_position = grid.getItemPosition(grid.indexOf(window.multi_compare_view.viewers[0]))
    assert first_position == (0, 0, 2, 1)
    assert grid.rowStretch(0) == 1
    assert grid.rowStretch(1) == 1
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
    assert exported.startswith("Id,Image,Bit depth,Samples")
    assert "2,histogram-2.png,8-bit,64" in exported
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
    restored_sidebar_width = restored.main_splitter.sizes()[0]
    assert abs(restored_sidebar_width - saved_sidebar_width) <= restored.main_splitter.handleWidth()
    assert not restored.bottom_dock.isHidden()
    assert restored.bottom_tabs.currentIndex() == 1
    assert restored.dockWidgetArea(restored.bottom_dock) == Qt.DockWidgetArea.BottomDockWidgetArea
    restored.reset_workspace_layout()
    assert restored._layout_mode == "Auto"
    assert restored.bottom_dock.isHidden()
    restored.close()


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
    assert all(curve.opts["pen"].style() == Qt.PenStyle.SolidLine for curve in profile_curves)
    assert len(window.line_profile_panel.plot.listDataItems()) == 12

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
    transform = DisplayTransform(display_low=0.0, display_high=1023.0)
    document = ImageDocument.from_array(
        source,
        "bayer.raw",
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
    window.show()
    window._show_plot_tab(0)
    window.add_document(document)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 1,
        timeout=3000,
    )
    result = window.comparison_analysis_panel.last_results[0]
    assert result.channel_names == ("R", "Gr", "Gb", "B")
    table = window.comparison_analysis_panel.table
    assert table.item(0, 0).toolTip().find("10-bit") >= 0
    assert window.comparison_analysis_panel.image_summary.item(0, 2).text() == "10-bit"
    assert window.comparison_analysis_panel.image_summary.item(0, 3).text() == "16"
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
    window._show_plot_tab(1)
    hover_position = window.line_profile_panel.plot.getViewBox().mapViewToScene(QPointF(0, 25))
    window.line_profile_panel._on_plot_mouse_moved(hover_position)
    assert window.line_profile_panel._hover_text is not None
    assert "Gr@1" in window.line_profile_panel._hover_text.toPlainText()
    bayer_hover_text = window.line_profile_panel._hover_text.toPlainText()
    assert "Gr@1" in bayer_hover_text
    assert "Gb" in bayer_hover_text.splitlines()
    assert "Gb:" not in bayer_hover_text
    assert "B@1" in bayer_hover_text
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
