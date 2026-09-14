from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.issue77_ui_design_followup import RoiEditorDialog

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _document(name: str, shape: tuple[int, int] = (6, 8)) -> ImageDocument:
    return ImageDocument.from_array(
        np.arange(shape[0] * shape[1], dtype=np.uint16).reshape(shape),
        name,
    )


def _composed_window(qtbot: object) -> MainWindow:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    return window


def test_roi_edit_button_opens_from_compact_region_contract(qtbot: object) -> None:
    window = _composed_window(qtbot)
    followup = window.issue77_ui_design_followup

    assert not followup.roi_edit_button.isEnabled()
    document = _document("reference.png")
    window.add_document(document)

    assert followup.roi_edit_button.isEnabled()
    dialog = followup.create_roi_dialog()
    assert isinstance(dialog, RoiEditorDialog)
    assert dialog.bounds() == RoiBounds(0, 0, 8, 6)
    window.close()


def test_roi_dialog_applies_only_on_confirmation_and_stays_open_on_invalid_input(
    qtbot: object,
) -> None:
    window = _composed_window(qtbot)
    large = _document("large.png", (6, 8))
    small = _document("small.png", (5, 6))
    for document in (large, small):
        window.add_document(document, select=False)
    window._select_document_ids([large.document_id, small.document_id])
    followup = window.issue77_ui_design_followup

    dialog = followup.create_roi_dialog()
    assert isinstance(dialog, RoiEditorDialog)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    dialog.x_input.setValue(1)
    dialog.y_input.setValue(1)
    dialog.width_input.setValue(3)
    dialog.height_input.setValue(3)
    assert window._shared_roi is None

    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    assert window._shared_roi == RoiBounds(1, 1, 3, 3)
    assert dialog.result() == int(QDialog.Accepted) if False else dialog.result() == 1

    invalid_dialog = followup.create_roi_dialog()
    assert isinstance(invalid_dialog, RoiEditorDialog)
    qtbot.addWidget(invalid_dialog)  # type: ignore[attr-defined]
    invalid_dialog.show()
    invalid_dialog.x_input.setValue(4)
    invalid_dialog.y_input.setValue(2)
    invalid_dialog.width_input.setValue(4)
    invalid_dialog.height_input.setValue(3)
    qtbot.mouseClick(invalid_dialog.apply_button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]

    assert window._shared_roi == RoiBounds(1, 1, 3, 3)
    assert invalid_dialog.isVisible()
    assert invalid_dialog.validation.isVisible()
    window.close()


def test_three_view_arrangement_button_lives_beside_layout_and_toggles_geometry(
    qtbot: object,
) -> None:
    window = _composed_window(qtbot)
    followup = window.issue77_ui_design_followup
    controller = window.quick_compare_controller
    button = followup.three_view_button

    assert button.parentWidget() is window.layout_selector.parentWidget()
    assert button.isVisibleTo(window.presentation_controls)
    assert not button.isEnabled()

    documents = [_document(f"{index}.png") for index in range(3)]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert button.isEnabled()
    assert controller._effective_three_view_variant() == "Equal"
    equal_geometry = window.multi_compare_view._fixed_geometry(3)
    assert "Equal" in button.toolTip()

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    assert controller._effective_three_view_variant() == "Focus"
    assert window.multi_compare_view._fixed_geometry(3) != equal_geometry
    assert "Focus" in button.toolTip()

    fourth = _document("fourth.png")
    window.add_document(fourth, select=False)
    window._select_document_ids([*(document.document_id for document in documents), fourth.document_id])
    assert not button.isEnabled()
    window.close()
