from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.difference_cache import DifferenceMapCache
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar


def _window(qtbot: object) -> tuple[MainWindow, object]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window, window.review_selection_controller


def test_shortcuts_page_reservations_and_initial_placeholders(qtbot: object) -> None:
    window, _review = _window(qtbot)

    assert window.split_channels_action.shortcut().toString() == "S"
    assert window.iqa_workspace_action.shortcut().toString() == "Ctrl+Shift+I"
    assert not window.comparison_page_group.isHidden()
    assert window.comparison_page_label.text() == "— / —"
    assert window.comparison_page_range_label.text() == "—"
    assert not window.previous_comparison_page_button.isEnabled()
    assert not window.next_comparison_page_button.isEnabled()

    page_width = window.comparison_page_label.width()
    range_width = window.comparison_page_range_label.width()
    assert window.comparison_page_label.minimumWidth() == 0
    assert window.comparison_page_range_label.minimumWidth() == 0
    assert page_width <= window.comparison_page_label.maximumWidth() <= 54
    assert range_width <= window.comparison_page_range_label.maximumWidth() <= 90

    window._comparison_page_range = lambda: (9996, 10000, 10000)  # type: ignore[method-assign]
    window._comparison_page_controls_state = None
    window._update_comparison_page_controls()
    assert window.comparison_page_label.text() == "1667 / 1667"
    assert window.comparison_page_range_label.text() == "9997–10000 of 10000"
    assert window.comparison_page_label.width() <= 54
    assert window.comparison_page_range_label.width() <= 90
    assert window.comparison_page_label.toolTip() == "1667 / 1667"
    assert window.comparison_page_range_label.toolTip() == "9997–10000 of 10000"
    assert "1667 / 1667" in window.comparison_page_label.accessibleName()
    assert "9997–10000 of 10000" in window.comparison_page_range_label.accessibleName()


def test_shortcuts_dispatch_in_active_production_window(qtbot: object) -> None:
    window, _review = _window(qtbot)
    document = ImageDocument.from_array(
        np.zeros((2, 2, 3), dtype=np.uint8),
        "rgb.png",
    )
    window.add_document(document)
    window.show()
    QApplication.setActiveWindow(window)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: QApplication.activeWindow() is window,
        timeout=3000,
    )
    window.viewer.setFocus()

    qtbot.keyClick(window.viewer, Qt.Key.Key_S)  # type: ignore[attr-defined]
    qtbot.waitUntil(  # type: ignore[attr-defined]
        window.split_channels_action.isChecked,
        timeout=3000,
    )

    assert window.iqa_dock.isHidden()
    qtbot.keyClick(  # type: ignore[attr-defined]
        window.viewer,
        Qt.Key.Key_I,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window.iqa_dock.isHidden(),
        timeout=3000,
    )
    window.close()


def test_iqa_workspace_uses_plots_dock_chrome_before_first_show(qtbot: object) -> None:
    window, _review = _window(qtbot)

    title_bar = window.iqa_dock.titleBarWidget()
    assert isinstance(title_bar, PlotsDockTitleBar)
    assert window.iqa_workspace._dock_title is title_bar
    assert title_bar.title.text() == "IQA Results"

    layout = title_bar.layout()
    assert layout is not None
    assert layout.itemAt(1).widget() is title_bar.float_button
    assert layout.itemAt(2).widget() is title_bar.maximize_button
    assert layout.itemAt(3).widget() is title_bar.close_button
    assert not title_bar.float_button.icon().isNull()
    assert not title_bar.maximize_button.icon().isNull()
    assert not title_bar.close_button.icon().isNull()
    assert title_bar.float_button.toolTip() == "Float IQA Results"
    assert title_bar.maximize_button.toolTip() == "Maximize IQA Results"
    assert title_bar.close_button.toolTip() == "Hide IQA Results"


def test_single_view_navigation_and_difference_reference_are_visually_separated(
    qtbot: object,
) -> None:
    window, _review = _window(qtbot)
    header = window.viewer.header

    window.viewer.set_navigation_items(
        [
            ("a", "1", "a.png"),
            ("b", "2", "b.png"),
            ("difference", "Diff", "Difference"),
        ],
        "difference",
    )
    assert not header.workflow_navigation_separator.isHidden()

    header.set_difference_reference(
        visible=True,
        prefix="Absolute [All]:",
        a_slot=1,
        a_name="a.png",
        b_slot=2,
        b_name="b.png",
        detailed=True,
    )
    assert header.difference_prefix.text() == "Absolute · All:"
    assert header.difference_a_badge.text() == "A 1"
    assert header.difference_b_badge.text() == "B 2"
    assert header.difference_vs.text() == "↔"


def test_difference_and_plot_empty_states_are_consistent(qtbot: object) -> None:
    window, _review = _window(qtbot)
    first = ImageDocument.from_array(np.zeros((2, 2, 3), dtype=np.uint8), "a.png")
    second = ImageDocument.from_array(np.ones((2, 2, 3), dtype=np.uint8), "b.png")

    window.difference_panel.set_documents([first, second], None)
    assert window.difference_panel.status.text() == "Not calculated"
    assert not window.difference_panel.workflow_metrics_hint.isHidden()
    assert TOKENS.accent in window.difference_panel.calculate.styleSheet()

    histogram_panel = window.comparison_analysis_panel
    assert "Select an image" in histogram_panel.workflow_histogram_hint.text()
    assert "Histogram" in histogram_panel.workflow_histogram_hint.text()
    histogram_panel.set_documents([first], None)
    assert histogram_panel.workflow_histogram_hint.isHidden()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(histogram_panel.last_results) == 1,
        timeout=3000,
    )
    assert histogram_panel.workflow_histogram_hint.isHidden()
    histogram_panel.clear()
    assert not histogram_panel.workflow_histogram_hint.isHidden()

    line_panel = window.line_profile_panel
    assert "Select an image" in line_panel.workflow_empty_hint.text()
    line_panel.set_documents([first], None)
    assert "Draw a line" in line_panel.workflow_empty_hint.text()
    assert "Shift + drag" in line_panel.workflow_empty_hint.text()
    assert "Shift+drag" in line_panel.status.text()
    assert "Alt+drag" not in line_panel.status.text()
    line_panel.set_documents([first], LineSelection(0, 0, 1, 1))
    assert line_panel.workflow_empty_hint.isHidden()


def test_difference_hint_hides_in_flight_and_stays_hidden_for_uncached_result(
    qtbot: object,
    monkeypatch: object,
) -> None:
    window, _review = _window(qtbot)
    panel = window.difference_panel
    first = ImageDocument.from_array(np.zeros((2, 2, 3), dtype=np.uint8), "a.png")
    second = ImageDocument.from_array(np.ones((2, 2, 3), dtype=np.uint8), "b.png")
    panel.set_documents([first, second], None)

    start = panel._pool.start
    monkeypatch.setattr(panel._pool, "start", lambda _worker: None)  # type: ignore[attr-defined]
    qtbot.mouseClick(panel.calculate, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    assert panel.status.text() == "Calculating map…"
    assert panel.workflow_metrics_hint.isHidden()
    panel._cancel_worker()

    monkeypatch.setattr(panel._pool, "start", start)  # type: ignore[attr-defined]
    panel._map_cache = DifferenceMapCache(1)
    panel.calculate_difference()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: panel.last_result is not None and panel._worker is None,
        timeout=3000,
    )
    assert not panel.has_cached_map()
    panel._validate()
    assert panel.status.text() == "Calculated"
    assert panel.workflow_metrics_hint.isHidden()
    window.close()


def test_review_count_uses_pick_language_and_selection_accent(qtbot: object) -> None:
    _window_widget, review = _window(qtbot)
    review.state.enter(("a",))
    review.state.set_picked("a", True)
    review._sync_controls()

    assert review.count_label.text() == "● Picked 1"
    assert TOKENS.selection in review.count_label.styleSheet()


def test_files_context_menu_reuses_open_actions_and_batches_folder_removal(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, _review = _window(qtbot)
    tree = window.document_list
    controller = window.workflow_files_context_menu

    folder = tmp_path / "scene"
    first = ImageDocument.from_array(
        np.zeros((2, 2, 3), dtype=np.uint8),
        "a.png",
        source_path=folder / "a.png",
    )
    second = ImageDocument.from_array(
        np.ones((2, 2, 3), dtype=np.uint8),
        "b.png",
        source_path=folder / "b.png",
    )
    window.add_document(first, select=False)
    window.add_document(second, select=False)
    folder_item = tree.topLevelItem(0)
    image_item = folder_item.child(0)

    blank_menu = controller.build_menu_for_item(None)
    assert [action.text() for action in blank_menu.actions()] == [
        "Open Images...",
        "Open Folder...",
    ]

    image_menu = controller.build_menu_for_item(image_item)
    image_texts = [action.text() for action in image_menu.actions() if not action.isSeparator()]
    assert image_texts == [
        "Open Images...",
        "Open Folder...",
        "Set as Primary",
        "Show Selected in Multi View",
        "Remove Selected from Files",
    ]

    removed: list[object] = []
    tree.remove_requested.connect(removed.append)
    folder_menu = controller.build_menu_for_item(folder_item)
    folder_texts = [action.text() for action in folder_menu.actions() if not action.isSeparator()]
    assert folder_texts == [
        "Open Images...",
        "Open Folder...",
        "Remove Folder from Files",
        "Set Display Tag...",
    ]
    remove_folder = next(
        action for action in folder_menu.actions() if action.text() == "Remove Folder from Files"
    )
    remove_folder.trigger()

    expected_ids = [first.document_id, second.document_id]
    assert removed == [expected_ids]
    assert first.document_id not in window.documents
    assert second.document_id not in window.documents
    assert tree.document_count == 0
    assert tree.topLevelItemCount() == 0


def test_files_context_menu_disables_primary_outside_current_comparison_page(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, _review = _window(qtbot)
    documents = [
        ImageDocument.from_array(
            np.full((2, 2), index, dtype=np.uint8),
            f"{index}.png",
            source_path=tmp_path / f"{index}.png",
        )
        for index in range(7)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    controller = window.workflow_files_context_menu
    off_page_item = window.document_list.document_item(documents[-1].document_id)
    assert off_page_item is not None

    menu = controller.build_menu_for_item(off_page_item)
    primary = next(action for action in menu.actions() if action.text() == "Set as Primary")

    assert not primary.isEnabled()
    assert "current Comparison Page" in primary.toolTip()
    window.close()
