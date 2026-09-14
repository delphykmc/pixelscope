from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QApplication, QDialog, QLayout, QSizePolicy

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


def _drain_deferred_delete() -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def _direct_roi_dialogs(window: MainWindow) -> list[RoiEditorDialog]:
    return window.findChildren(
        RoiEditorDialog,
        "",
        Qt.FindChildOption.FindDirectChildrenOnly,
    )


def test_roi_region_uses_compact_geometry_summary_and_right_aligned_edit(qtbot: object) -> None:
    window = _composed_window(qtbot)
    followup = window.issue77_ui_design_followup
    panel = window.comparison_analysis_panel

    assert not followup.roi_edit_button.isEnabled()
    document = _document("reference.png")
    window.add_document(document)
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert followup.roi_edit_button.isEnabled()
    assert followup.roi_edit_button.text() == "Edit"
    assert followup.roi_edit_button.width() == 52
    assert panel.roi_label.text() == "(0, 0) · 8 × 6"
    assert "width" not in panel.roi_label.text().lower()
    assert "height" not in panel.roi_label.text().lower()
    assert panel.roi_label.alignment() & Qt.AlignmentFlag.AlignLeft
    assert followup.roi_bounds_label.alignment() & Qt.AlignmentFlag.AlignLeft
    assert followup.roi_bounds_label.geometry().left() < panel.roi_label.geometry().left()
    assert panel.roi_label.geometry().left() < followup.roi_edit_button.geometry().left()
    assert "Width 8" in panel.roi_label.toolTip()
    window.close()


def test_roi_dialog_is_dense_two_by_two_editor(qtbot: object) -> None:
    window = _composed_window(qtbot)
    window.add_document(_document("reference.png"))
    followup = window.issue77_ui_design_followup

    dialog = followup.create_roi_dialog()
    assert isinstance(dialog, RoiEditorDialog)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    root = dialog.layout()
    assert root is not None
    assert root.sizeConstraint() == QLayout.SizeConstraint.SetFixedSize
    assert dialog.x_input.width() == dialog.y_input.width() == 92
    assert dialog.width_input.width() == dialog.height_input.width() == 92
    assert dialog.cancel_button.width() == dialog.apply_button.width() == 64
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
    assert dialog.result() == int(QDialog.DialogCode.Accepted)

    invalid_dialog = followup.create_roi_dialog()
    assert isinstance(invalid_dialog, RoiEditorDialog)
    qtbot.addWidget(invalid_dialog)  # type: ignore[attr-defined]
    invalid_dialog.show()
    invalid_dialog.x_input.setValue(4)
    invalid_dialog.y_input.setValue(2)
    invalid_dialog.width_input.setValue(4)
    invalid_dialog.height_input.setValue(3)
    qtbot.mouseClick(  # type: ignore[attr-defined]
        invalid_dialog.apply_button,
        Qt.MouseButton.LeftButton,
    )

    assert window._shared_roi == RoiBounds(1, 1, 3, 3)
    assert invalid_dialog.isVisible()
    assert invalid_dialog.validation.isVisible()
    window.close()


def test_roi_editor_uses_one_nonblocking_instance_and_disposes_after_finish(qtbot: object) -> None:
    window = _composed_window(qtbot)
    window.add_document(_document("reference.png"))
    window.show()
    followup = window.issue77_ui_design_followup

    first = followup._show_roi_editor()
    assert isinstance(first, RoiEditorDialog)
    second = followup._show_roi_editor()
    assert second is first
    assert followup._active_roi_dialog is first
    assert _direct_roi_dialogs(window) == [first]

    first.reject()
    _drain_deferred_delete()
    assert followup._active_roi_dialog is None
    assert _direct_roi_dialogs(window) == []

    for accept in (True, False, True):
        dialog = followup._show_roi_editor()
        assert isinstance(dialog, RoiEditorDialog)
        assert len(_direct_roi_dialogs(window)) == 1
        if accept:
            dialog.x_input.setValue(1)
            dialog.y_input.setValue(1)
            dialog.width_input.setValue(3)
            dialog.height_input.setValue(3)
            dialog._apply()
        else:
            dialog.reject()
        _drain_deferred_delete()
        assert followup._active_roi_dialog is None
        assert _direct_roi_dialogs(window) == []

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
    assert not button.icon().isNull()
    assert not controller.three_view_group.isVisible()

    documents = [_document(f"{index}.png") for index in range(3)]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    window.show()
    qtbot.wait(20)  # type: ignore[attr-defined]

    assert button.isEnabled()
    assert controller._effective_three_view_variant() == "Equal"
    equal_geometry = window.multi_compare_view._fixed_geometry(3)
    equal_icon_key = button.icon().cacheKey()
    assert "Equal" in button.toolTip()

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)  # type: ignore[attr-defined]
    assert controller._effective_three_view_variant() == "Focus"
    assert window.multi_compare_view._fixed_geometry(3) != equal_geometry
    assert button.icon().cacheKey() != equal_icon_key
    assert "Focus" in button.toolTip()

    fourth = _document("fourth.png")
    window.add_document(fourth, select=False)
    window._select_document_ids(
        [*(document.document_id for document in documents), fourth.document_id]
    )
    assert button.isVisibleTo(window.presentation_controls)
    assert not button.isEnabled()
    window.close()


def test_three_view_button_reuses_priority_aware_command_row_sizing_owner(qtbot: object) -> None:
    window = _composed_window(qtbot)
    followup = window.issue77_ui_design_followup
    review = window.review_selection_controller
    layout_group = window.layout_selector.parentWidget()

    assert layout_group is not None
    assert followup.three_view_button.parentWidget() is layout_group
    assert followup.three_view_button.isVisibleTo(window.presentation_controls)
    assert window._command_row_metric_refresh.parent() is window

    group_layout = layout_group.layout()
    assert group_layout is not None
    assert layout_group.minimumWidth() >= group_layout.minimumSize().width()

    assert review.count_label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    assert review.count_label.minimumWidth() > 0
    assert (
        window.comparison_page_label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    )
    assert window.comparison_page_label.minimumWidth() > 0
    assert window.comparison_page_range_label.minimumWidth() == 0

    window.close()
