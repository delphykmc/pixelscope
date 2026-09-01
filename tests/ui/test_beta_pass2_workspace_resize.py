from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QLabel,
    QSizePolicy,
    QWidget,
)

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.presentation_controls import polish_presentation_controls

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _production_window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    window.show()
    return window


def _register_rgb8_pair(window: MainWindow, tmp_path: Path) -> tuple[ImageDocument, ...]:
    documents = tuple(
        ImageDocument.from_array(
            np.full((12, 16, 3), index * 32, dtype=np.uint8),
            f"pair_{index}.png",
            source_path=tmp_path / f"{index}_{'very_long_beta_pair_name_' * 4}.png",
        )
        for index in range(2)
    )
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    return documents


def _assert_resize_accepted(window: MainWindow, qtbot: object, width: int, height: int) -> None:
    window.resize(width, height)
    qtbot.waitUntil(lambda: window.width() <= width)  # type: ignore[attr-defined]
    assert window.width() <= width
    assert window.height() <= height


def _assert_command_row_geometry(window: MainWindow) -> None:
    host = window.presentation_controls
    review = window.review_selection_controller
    ordered = (
        window.layout_selector.parentWidget(),
        window.presentation_control_separator,
        window.comparison_page_group,
        window.findChild(QWidget, "DisplayGainControl"),
        review.count_label,
        review.clear_button,
        review.keep_button,
    )
    visible_rects = []
    for widget in ordered:
        assert widget is not None
        if widget.isVisible():
            top_left = widget.mapTo(host, QPoint(0, 0))
            rect = widget.rect().translated(top_left)
            assert host.rect().contains(rect)
            visible_rects.append(rect)
    assert all(
        visible_rects[index].right() < visible_rects[index + 1].left()
        for index in range(len(visible_rects) - 1)
    ), visible_rects

    page_group = window.comparison_page_group
    if page_group.isVisible():
        for child in (
            page_group.findChild(QLabel, "comparisonPageCaption"),
            window.previous_comparison_page_button,
            window.comparison_page_label,
            window.next_comparison_page_button,
            window.comparison_page_range_label,
        ):
            assert child is not None
            assert page_group.rect().contains(child.geometry())


def _assert_actionable_content_floors(window: MainWindow) -> None:
    review = window.review_selection_controller
    layout_combo = window.layout_selector
    gain_combo = window.findChild(QComboBox, "DisplayGainCombo")
    gain_group = window.findChild(QWidget, "DisplayGainControl")
    layout_group = layout_combo.parentWidget()
    assert gain_combo is not None
    assert gain_group is not None
    assert layout_group is not None
    assert (
        window.comparison_page_group.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    )
    assert review.count_label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored

    for button in (review.clear_button, review.keep_button):
        assert isinstance(button, QAbstractButton)
        assert button.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Minimum
        assert button.minimumWidth() >= button.sizeHint().width()
        assert button.width() >= button.minimumWidth()

    for combo in (layout_combo, gain_combo):
        assert combo.sizeAdjustPolicy() == QComboBox.SizeAdjustPolicy.AdjustToContents
        assert combo.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.MinimumExpanding
        assert combo.minimumWidth() >= combo.sizeHint().width()
        assert combo.width() >= combo.minimumWidth()

    for group in (layout_group, gain_group):
        group_layout = group.layout()
        assert group_layout is not None
        assert group.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.MinimumExpanding
        assert group.minimumWidth() >= group_layout.minimumSize().width()
        assert group.width() >= group.minimumWidth()


@pytest.mark.parametrize("populated", [False, True])
def test_production_workspace_accepts_fhd_and_compact_width_with_iqa_hidden_or_visible(
    qtbot: object,
    tmp_path: Path,
    populated: bool,
) -> None:
    window = _production_window(qtbot)
    if populated:
        _register_rgb8_pair(window, tmp_path)

    window.iqa_dock.hide()
    qtbot.waitUntil(window.iqa_dock.isHidden)  # type: ignore[attr-defined]
    _assert_resize_accepted(window, qtbot, 1920, 1080)
    _assert_command_row_geometry(window)
    _assert_resize_accepted(window, qtbot, 960, 540)
    _assert_command_row_geometry(window)
    _assert_actionable_content_floors(window)
    assert window.minimumSizeHint().width() <= 960

    window.iqa_dock.show()
    qtbot.waitUntil(window.iqa_dock.isVisible)  # type: ignore[attr-defined]
    _assert_resize_accepted(window, qtbot, 1920, 1080)
    _assert_command_row_geometry(window)
    _assert_resize_accepted(window, qtbot, 1280, 720)
    _assert_command_row_geometry(window)
    _assert_actionable_content_floors(window)
    assert window.minimumSizeHint().width() <= 1280

    shell = window.remote_iqa_workspace
    assert shell.minimumWidth() == 0
    assert shell.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    assert shell.tabs.minimumWidth() == 0
    assert shell.tabs.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    for index in range(shell.tabs.count()):
        page = shell.tabs.widget(index)
        assert page.minimumWidth() == 0
        assert page.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored

    window.close()


def test_command_row_refreshes_content_floors_after_composition_font_change(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    _register_rgb8_pair(window, tmp_path)
    window.iqa_dock.hide()
    _assert_resize_accepted(window, qtbot, 1280, 720)

    review = window.review_selection_controller
    gain_combo = window.findChild(QComboBox, "DisplayGainCombo")
    gain_group = window.findChild(QWidget, "DisplayGainControl")
    layout_group = window.layout_selector.parentWidget()
    assert gain_combo is not None
    assert gain_group is not None
    assert layout_group is not None
    metric_owner = window._command_row_metric_refresh
    polish_presentation_controls(window)
    assert window._command_row_metric_refresh is metric_owner
    before = tuple(
        widget.minimumWidth()
        for widget in (
            review.clear_button,
            review.keep_button,
            window.layout_selector,
            gain_combo,
            layout_group,
            gain_group,
        )
    )

    font = window.font()
    point_size = font.pointSizeF()
    font.setPointSizeF(max(11.0, point_size * 1.2 if point_size > 0 else 11.0))
    for widget in (
        review.clear_button,
        review.keep_button,
        window.layout_selector,
        gain_combo,
    ):
        widget.setFont(font)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            widget.minimumWidth() > previous
            for widget, previous in zip(
                (
                    review.clear_button,
                    review.keep_button,
                    window.layout_selector,
                    gain_combo,
                    layout_group,
                    gain_group,
                ),
                before,
                strict=True,
            )
        )
    )
    _assert_resize_accepted(window, qtbot, 1280, 720)
    _assert_actionable_content_floors(window)
    _assert_command_row_geometry(window)
    assert window.minimumSizeHint().width() <= 1280

    window.close()


def test_command_row_refreshes_combo_floors_after_composition_style_change(
    qtbot: object,
) -> None:
    window = _production_window(qtbot)
    window.iqa_dock.hide()
    _assert_resize_accepted(window, qtbot, 1280, 720)
    gain_combo = window.findChild(QComboBox, "DisplayGainCombo")
    layout_group = window.layout_selector.parentWidget()
    gain_group = gain_combo.parentWidget() if gain_combo is not None else None
    assert gain_combo is not None
    assert layout_group is not None
    assert gain_group is not None
    combos = (window.layout_selector, gain_combo)
    groups = (layout_group, gain_group)
    before_combos = tuple(combo.minimumWidth() for combo in combos)
    before_groups = tuple(group.minimumWidth() for group in groups)

    for combo in combos:
        combo.setStyleSheet("QComboBox { padding-left: 20px; padding-right: 20px; }")

    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: all(
            combo.minimumWidth() > previous
            for combo, previous in zip(combos, before_combos, strict=True)
        )
        and all(
            group.minimumWidth() > previous
            for group, previous in zip(groups, before_groups, strict=True)
        )
    )
    _assert_resize_accepted(window, qtbot, 1280, 720)
    _assert_actionable_content_floors(window)
    _assert_command_row_geometry(window)
    assert window.minimumSizeHint().width() <= 1280

    window.close()


@pytest.mark.parametrize("size", [(1280, 720), (1920, 1080)])
def test_workspace_keeps_page_gain_and_curation_actions_observable_without_overlap(
    qtbot: object,
    tmp_path: Path,
    size: tuple[int, int],
) -> None:
    window = _production_window(qtbot)
    pair = _register_rgb8_pair(window, tmp_path)
    additional = tuple(
        ImageDocument.from_array(
            np.full((12, 16, 3), index * 16, dtype=np.uint8),
            f"additional_{index}.png",
            source_path=tmp_path / f"additional_{index}.png",
        )
        for index in range(2, 8)
    )
    for document in additional:
        window.add_document(document, select=False)
    documents = (*pair, *additional)
    window._select_document_ids([document.document_id for document in documents])
    window.iqa_dock.show()
    _assert_resize_accepted(window, qtbot, *size)
    _assert_command_row_geometry(window)

    assert window.comparison_page_label.text() == "1 / 2"
    assert window.comparison_page_range_label.text() == "1–6 of 8"
    assert window.comparison_page_label.toolTip() == "1 / 2"
    assert window.comparison_page_range_label.toolTip() == "1–6 of 8"
    assert "1 / 2" in window.comparison_page_label.accessibleName()
    assert "1–6 of 8" in window.comparison_page_range_label.accessibleName()
    assert not window.previous_comparison_page_button.isHidden()
    assert not window.next_comparison_page_button.isHidden()
    qtbot.mouseClick(  # type: ignore[attr-defined]
        window.next_comparison_page_button,
        Qt.MouseButton.LeftButton,
    )
    assert window.comparison_page_label.text() == "2 / 2"
    assert window.comparison_page_range_label.text() == "7–8 of 8"
    assert window.comparison_page_label.toolTip() == "2 / 2"
    assert window.comparison_page_range_label.toolTip() == "7–8 of 8"
    _assert_command_row_geometry(window)
    qtbot.mouseClick(  # type: ignore[attr-defined]
        window.previous_comparison_page_button,
        Qt.MouseButton.LeftButton,
    )

    gain_label = window.findChild(QLabel, "DisplayGainLabel")
    gain = window.findChild(type(window.layout_selector), "DisplayGainCombo")
    assert gain_label is not None
    assert gain is not None
    assert gain_label.text() == "Gain"
    assert gain_label.toolTip() == "Display Gain"
    assert gain_label.accessibleName() == "Display Gain"
    gain.setCurrentIndex(1)
    assert gain.currentData(Qt.ItemDataRole.UserRole) == 2.0

    review = window.review_selection_controller
    for button, full_name in (
        (review.clear_button, "Clear Selection"),
        (review.keep_button, "Keep Selection"),
    ):
        assert not button.isHidden()
        assert button.accessibleName() == full_name
        assert full_name in button.toolTip()

    pick = window.multi_compare_view.occupied_viewers[0].header.pick
    assert not pick.isHidden()
    qtbot.mouseClick(pick, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    assert review.picked_ids == {documents[0].document_id}
    assert review.clear_button.isEnabled()
    assert review.keep_button.isEnabled()
    assert review.count_label.toolTip() == "● Picked 1"
    assert "● Picked 1" in review.count_label.accessibleName()

    qtbot.mouseClick(review.clear_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    assert not review.picked_ids
    assert review.count_label.toolTip() == "● Picked 0"

    window.close()


def test_populated_current_pair_keeps_long_names_out_of_iqa_minimum_hint(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    documents = _register_rgb8_pair(window, tmp_path)
    shell = window.remote_iqa_workspace
    shell.tabs.setCurrentWidget(shell.setup_page)
    shell.set_current_pair_state(
        "OK · RGB8 · 16×12",
        True,
        None,
        names=(documents[0].display_name, documents[1].display_name),
    )
    window.iqa_dock.show()
    _assert_resize_accepted(window, qtbot, 1280, 720)

    assert shell.current_pair_a.text() == documents[0].display_name
    assert shell.current_pair_b.text() == documents[1].display_name
    assert shell.current_pair_a.toolTip() == documents[0].display_name
    assert shell.current_pair_b.toolTip() == documents[1].display_name
    assert shell.current_pair_a.minimumWidth() == 0
    assert shell.current_pair_b.minimumWidth() == 0
    assert window.minimumSizeHint().width() <= 1280

    for label in shell.findChildren(QLabel):
        assert label.minimumWidth() == 0
        if label.text():
            assert label.toolTip() or label.accessibleName()

    window.close()
