from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument

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
    _assert_resize_accepted(window, qtbot, 1280, 720)
    assert window.minimumSizeHint().width() <= 1280

    window.iqa_dock.show()
    qtbot.waitUntil(window.iqa_dock.isVisible)  # type: ignore[attr-defined]
    _assert_resize_accepted(window, qtbot, 1920, 1080)
    _assert_resize_accepted(window, qtbot, 1280, 720)
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


def test_fhd_workspace_keeps_page_gain_and_curation_actions_observable(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window = _production_window(qtbot)
    documents = _register_rgb8_pair(window, tmp_path)
    window.iqa_dock.show()
    _assert_resize_accepted(window, qtbot, 1920, 1080)

    assert window.comparison_page_label.text() == "1 / 1"
    assert window.comparison_page_range_label.text() == "1–2 of 2"
    assert window.comparison_page_label.toolTip() == "1 / 1"
    assert window.comparison_page_range_label.toolTip() == "1–2 of 2"
    assert "1 / 1" in window.comparison_page_label.accessibleName()
    assert "1–2 of 2" in window.comparison_page_range_label.accessibleName()
    assert not window.previous_comparison_page_button.isHidden()
    assert not window.next_comparison_page_button.isHidden()

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
