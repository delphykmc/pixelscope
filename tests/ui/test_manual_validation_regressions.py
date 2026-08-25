from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.ui.display_gain import display_gain_state


def _window(qtbot: object) -> MainWindow:
    QSettings().clear()
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    window.show()
    return window


def _rgb(path: Path, value: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((32, 32, 3), value, dtype=np.uint8),
        path.name,
        source_path=path,
        channel_layout="RGB",
    )


def _gray(path: Path, value: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((8, 8), value, dtype=np.uint8),
        path.name,
        source_path=path,
        channel_layout="GRAY",
    )


def test_primary_swap_preserves_gained_viewer_buffers(qtbot: object, tmp_path: Path) -> None:
    state = display_gain_state()
    state.reset()
    window = _window(qtbot)
    first = _rgb(tmp_path / "a.png", 24)
    second = _rgb(tmp_path / "b.png", 48)
    for document in (first, second):
        window.add_document(document, select=False)
    window._select_document_ids([first.document_id, second.document_id])

    state.set_gain(2.0)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            viewer._displayed_gain == 2.0 and viewer._display_preview_worker is None
            for viewer in window.multi_compare_view.occupied_viewers
        ),
        timeout=5000,
    )
    source_viewers = {
        viewer.document.document_id: viewer
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    }
    request_serials = {
        document_id: viewer._display_preview_request_serial
        for document_id, viewer in source_viewers.items()
    }

    window._set_focus_document(second.document_id)

    presented = [viewer.document for viewer in window.multi_compare_view.occupied_viewers]
    assert presented[:2] == [second, first]
    for document in (first, second):
        viewer = next(
            candidate
            for candidate in window.multi_compare_view.occupied_viewers
            if candidate.document is document
        )
        assert viewer is source_viewers[document.document_id]
        assert viewer._display_preview_request_serial == request_serials[document.document_id]
        assert viewer._displayed_gain == 2.0
        assert viewer._display_preview_worker is None

    window.close()
    state.reset()


def test_folder_display_tags_disambiguate_same_folder_and_file_names(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    left_folder = tmp_path / "left" / "scene"
    right_folder = tmp_path / "right" / "scene"
    first = _gray(left_folder / "frame.png", 10)
    second = _gray(right_folder / "frame.png", 20)
    for document in (first, second):
        window.add_document(document, select=False)
    window._select_document_ids([first.document_id, second.document_id])

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.comparison_analysis_panel.last_results) == 2,
        timeout=5000,
    )
    window.line_profile_panel.view_mode.setCurrentText("Separate by image")
    window._shared_line = LineSelection(0, 0, 7, 0)
    window._render_selection(preserve_view=True)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.line_profile_panel.last_results) == 2,
        timeout=5000,
    )

    tags = window.folder_display_tag_controller
    first_folder_item = window.document_list.topLevelItem(0)
    folder_menu = window.workflow_files_context_menu.build_menu_for_item(first_folder_item)
    folder_actions = [action.text() for action in folder_menu.actions() if not action.isSeparator()]
    assert "Set Display Tag..." in folder_actions

    tags.set_tag(left_folder, "REF")
    tags.set_tag(right_folder, "TEST")

    assert first.display_name == "[REF] frame.png"
    assert second.display_name == "[TEST] frame.png"
    folder_labels = {
        window.document_list.topLevelItem(index).text(0)
        for index in range(window.document_list.topLevelItemCount())
    }
    assert "scene [REF]" in folder_labels
    assert "scene [TEST]" in folder_labels

    headers = {
        viewer.header.name.text()
        for viewer in window.multi_compare_view.occupied_viewers
        if viewer.document is not None
    }
    assert any("[REF] frame.png" in text for text in headers)
    assert any("[TEST] frame.png" in text for text in headers)

    selector_labels = {
        window.difference_panel.a_selector.itemText(index)
        for index in range(window.difference_panel.a_selector.count())
    }
    assert any("[REF] frame.png" in text for text in selector_labels)
    assert any("[TEST] frame.png" in text for text in selector_labels)

    analysis_labels = {
        window.comparison_analysis_panel.image_summary.item(row, 1).text()
        for row in range(window.comparison_analysis_panel.image_summary.rowCount())
    }
    assert any("[REF] frame.png" in text for text in analysis_labels)
    assert any("[TEST] frame.png" in text for text in analysis_labels)

    histogram_titles = {
        str(plot.getPlotItem().titleLabel.text)
        for plot in window.comparison_analysis_panel.plots[:2]
    }
    assert any("[REF] frame.png" in text for text in histogram_titles)
    assert any("[TEST] frame.png" in text for text in histogram_titles)

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(window.line_profile_panel.last_results) == 2,
        timeout=5000,
    )
    line_titles = {
        str(plot.getPlotItem().titleLabel.text) for plot in window.line_profile_panel.plots[:2]
    }
    assert any("[REF] frame.png" in text for text in line_titles)
    assert any("[TEST] frame.png" in text for text in line_titles)

    stored = str(window.settings.value(tags.SETTINGS_KEY, ""))
    assert "REF" in stored and "TEST" in stored
    window.close()


def test_cached_difference_can_be_explicitly_reactivated_from_toolbar(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _window(qtbot)
    first = _gray(tmp_path / "a.png", 10)
    second = _gray(tmp_path / "b.png", 30)
    for document in (first, second):
        window.add_document(document, select=False)
    ids = [first.document_id, second.document_id]
    window._select_document_ids(ids)

    window.difference_panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is not None,
        timeout=5000,
    )
    assert window.diff_action.isEnabled()
    assert window.diff_action.isChecked()
    assert window.difference_panel.has_cached_map()

    window.document_list.clearSelection()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window._difference_document is None,
        timeout=3000,
    )
    assert window.current_comparison_documents() == []
    assert window.difference_panel.has_cached_map()
    assert not window.diff_action.isEnabled()
    assert not window.diff_action.isChecked()

    window._select_document_ids(ids)
    assert window._difference_document is None
    assert window.difference_panel.has_cached_map()
    assert window.diff_action.isEnabled()
    assert not window.diff_action.isChecked()
    assert "cached" in window.diff_action.toolTip().casefold()

    calculations: list[str] = []

    def record_calculate(*_args: object, **_kwargs: object) -> None:
        calculations.append("calculate")

    window.difference_panel.calculate_difference = record_calculate  # type: ignore[method-assign]
    window.diff_action.setChecked(True)

    assert calculations == []
    assert window._difference_document is not None
    assert window._difference_source_ids == (first.document_id, second.document_id)
    assert window.diff_action.isEnabled()
    assert window.diff_action.isChecked()
    assert any(
        viewer.presented_document is window._difference_document
        for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()
