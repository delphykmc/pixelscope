from __future__ import annotations

import numpy as np

from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.ui.line_profile_panel import LineProfilePanel


def _document(name: str, value: int) -> ImageDocument:
    return ImageDocument.from_array(
        np.full((3, 5, 3), value, dtype=np.uint8),
        name,
    )


def _wait_for_results(qtbot: object, panel: LineProfilePanel, count: int) -> None:
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: len(panel.last_results) == count,
        timeout=3000,
    )


def test_reference_control_uses_priority_before_first_difference_mode(
    qtbot: object,
) -> None:
    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = _document("first.png", 10)
    active = _document("active.png", 20)
    focus = _document("focus.png", 30)

    panel.set_documents(
        [first, active, focus],
        LineSelection(0, 1, 4),
        reference_priority_ids=(focus.document_id, active.document_id, first.document_id),
    )
    _wait_for_results(qtbot, panel, 3)

    assert panel.reference_label.isHidden()
    assert panel.reference_selector.isHidden()
    assert panel.reference_selector.currentData() == focus.document_id

    panel.set_reference_priority_ids((active.document_id, first.document_id))
    assert panel.reference_selector.currentData() == active.document_id

    panel.y_mode.setCurrentText("Difference from reference")
    assert not panel.reference_label.isHidden()
    assert not panel.reference_selector.isHidden()
    assert panel.reference_selector.currentData() == active.document_id


def test_reference_selection_stays_stable_until_document_disappears(
    qtbot: object,
) -> None:
    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = _document("first.png", 10)
    second = _document("second.png", 20)
    third = _document("third.png", 30)
    selection = LineSelection(0, 1, 4)

    panel.set_documents(
        [first, second, third],
        selection,
        reference_priority_ids=(second.document_id, first.document_id),
    )
    _wait_for_results(qtbot, panel, 3)
    panel.y_mode.setCurrentText("Difference from reference")
    assert panel.reference_selector.currentData() == second.document_id

    third_index = panel.reference_selector.findData(third.document_id)
    panel.reference_selector.setCurrentIndex(third_index)
    assert panel.reference_selector.currentData() == third.document_id

    panel.set_reference_priority_ids((first.document_id, second.document_id))
    assert panel.reference_selector.currentData() == third.document_id

    panel.set_documents(
        [first, second],
        selection,
        reference_priority_ids=(first.document_id, second.document_id),
    )
    assert panel.reference_selector.currentData() == first.document_id


def test_difference_transform_uses_selected_reference_and_zeroes_it(
    qtbot: object,
) -> None:
    panel = LineProfilePanel()
    qtbot.addWidget(panel)  # type: ignore[attr-defined]
    first = _document("first.png", 10)
    second = _document("second.png", 20)
    third = _document("third.png", 35)

    panel.set_documents(
        [first, second, third],
        LineSelection(0, 1, 4),
        reference_priority_ids=(second.document_id,),
    )
    _wait_for_results(qtbot, panel, 3)
    panel.y_mode.setCurrentText("Difference from reference")
    results = panel.last_results

    first_x, first_y = panel._transformed_profile(
        0,
        "R",
        results[0].positions[0],
        results[0].values[0],
        results,
    )
    second_x, second_y = panel._transformed_profile(
        1,
        "R",
        results[1].positions[0],
        results[1].values[0],
        results,
    )
    third_x, third_y = panel._transformed_profile(
        2,
        "R",
        results[2].positions[0],
        results[2].values[0],
        results,
    )

    np.testing.assert_array_equal(first_x, second_x)
    np.testing.assert_array_equal(second_x, third_x)
    np.testing.assert_array_equal(first_y, np.full(5, -10.0))
    np.testing.assert_array_equal(second_y, np.zeros(5))
    np.testing.assert_array_equal(third_y, np.full(5, 15.0))


def test_main_window_orders_focus_active_and_first_displayed_reference(
    qtbot: object,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    first = _document("first.png", 10)
    focus = _document("focus.png", 20)
    active = _document("active.png", 30)
    for document in (first, focus, active):
        window.add_document(document, select=False)
    window._select_document_ids(
        [first.document_id, focus.document_id, active.document_id]
    )

    window._focus_document_id = focus.document_id
    assert window._line_reference_priority_ids([first, active], active) == (
        focus.document_id,
        active.document_id,
        first.document_id,
    )

    window._focus_document_id = None
    assert window._line_reference_priority_ids([first, active], active) == (
        active.document_id,
        first.document_id,
    )
