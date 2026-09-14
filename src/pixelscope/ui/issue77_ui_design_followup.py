from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core.roi import RoiBounds
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.quick_compare import QuickCompareController
from pixelscope.ui.toolbar_icons import toolbar_icon


class RoiEditorDialog(QDialog):
    """Compact modal editor for the application-owned shared ROI."""

    _FIELD_WIDTH = 92
    _BUTTON_WIDTH = 64

    def __init__(self, owner: Issue77UiDesignFollowup, bounds: RoiBounds) -> None:
        super().__init__(owner.window)
        self.owner = owner
        self.setWindowTitle("Set ROI")
        self.setWindowModality(Qt.WindowModality.WindowModal)

        root = QVBoxLayout(self)
        root.setContentsMargins(
            TOKENS.spacing_md,
            TOKENS.spacing_md,
            TOKENS.spacing_md,
            TOKENS.spacing_md,
        )
        root.setSpacing(TOKENS.spacing_sm)
        root.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        fields = QGridLayout()
        fields.setHorizontalSpacing(TOKENS.spacing_sm)
        fields.setVerticalSpacing(TOKENS.spacing_xs)
        root.addLayout(fields)

        self.x_input = self._spin_box(0, bounds.x, "ROI X")
        self.y_input = self._spin_box(0, bounds.y, "ROI Y")
        self.width_input = self._spin_box(1, bounds.width, "ROI Width")
        self.height_input = self._spin_box(1, bounds.height, "ROI Height")

        for row, left_name, left_control, right_name, right_control in (
            (0, "X", self.x_input, "Y", self.y_input),
            (1, "W", self.width_input, "H", self.height_input),
        ):
            fields.addWidget(QLabel(left_name, self), row, 0)
            fields.addWidget(left_control, row, 1)
            fields.addWidget(QLabel(right_name, self), row, 2)
            fields.addWidget(right_control, row, 3)

        self.validation = QLabel(self)
        self.validation.setObjectName("roiEditorValidation")
        self.validation.setText("ROI must fit all comparison frames.")
        self.validation.hide()
        root.addWidget(self.validation)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(TOKENS.spacing_xs)
        button_row.addStretch(1)
        self.cancel_button = QPushButton("Cancel", self)
        self.apply_button = QPushButton("Apply", self)
        for button in (self.cancel_button, self.apply_button):
            button.setFixedWidth(self._BUTTON_WIDTH)
            button.setFixedHeight(TOKENS.control_height)
            button_row.addWidget(button)
        self.apply_button.setDefault(True)
        self.cancel_button.clicked.connect(self.reject)  # type: ignore[attr-defined]
        self.apply_button.clicked.connect(self._apply)  # type: ignore[attr-defined]
        root.addLayout(button_row)

    @classmethod
    def _spin_box(cls, minimum: int, value: int, accessible_name: str) -> QSpinBox:
        control = QSpinBox()
        control.setRange(minimum, 2_147_483_647)
        control.setValue(value)
        control.setAccelerated(True)
        control.setKeyboardTracking(False)
        control.setAlignment(Qt.AlignmentFlag.AlignRight)
        control.setFixedWidth(cls._FIELD_WIDTH)
        control.setAccessibleName(accessible_name)
        return control

    def bounds(self) -> RoiBounds:
        return RoiBounds(
            self.x_input.value(),
            self.y_input.value(),
            self.width_input.value(),
            self.height_input.value(),
        )

    def _apply(self) -> None:
        if self.owner.window._numeric_roi_requested(self.bounds()):
            self.accept()
            return
        self.validation.show()


class Issue77UiDesignFollowup(QObject):
    """Presentation-only refinement for the merged Issue #77 work packages."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        controller = getattr(window, "quick_compare_controller", None)
        if not isinstance(controller, QuickCompareController):
            raise RuntimeError("Issue #77 UI follow-up requires Quick Compare composition")
        self.quick_compare = controller
        self._active_roi_dialog: RoiEditorDialog | None = None

        self._install_roi_affordance()
        self._install_three_view_affordance()
        self._compact_command_row()
        self._wrap_render_selection()
        self._sync_controls()

    def _install_roi_affordance(self) -> None:
        panel = self.window.comparison_analysis_panel
        panel.region_layout.removeWidget(panel.roi_label)
        panel.region_layout.removeWidget(panel.roi_editor)
        panel.roi_editor.hide()

        self.roi_bounds_label = QLabel("Bounds", panel)
        label_width = max(
            panel.scope_label.sizeHint().width(),
            self.roi_bounds_label.sizeHint().width(),
        )
        panel.scope_label.setFixedWidth(label_width)
        self.roi_bounds_label.setFixedWidth(label_width)
        self.roi_bounds_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        panel.roi_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self.roi_edit_button = QPushButton("Edit", panel)
        self.roi_edit_button.setObjectName("roiEditButton")
        self.roi_edit_button.setToolTip("Enter exact shared ROI coordinates")
        self.roi_edit_button.setAccessibleName("Edit ROI")
        self.roi_edit_button.setFixedWidth(52)
        self.roi_edit_button.setFixedHeight(TOKENS.control_height)
        self.roi_edit_button.clicked.connect(self._show_roi_editor)  # type: ignore[attr-defined]

        panel.region_layout.addWidget(self.roi_bounds_label, 1, 0)
        panel.region_layout.addWidget(
            panel.roi_label,
            1,
            1,
            alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        panel.region_layout.addWidget(
            self.roi_edit_button,
            1,
            2,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        panel.region_layout.setColumnStretch(1, 1)
        panel.region_layout.setColumnStretch(2, 0)

        original_update_region_label = panel._update_region_label

        def update_region_label() -> None:
            original_update_region_label()
            self._sync_roi_summary()

        panel._update_region_label = update_region_label
        self._sync_roi_summary()

    def _sync_roi_summary(self) -> None:
        panel = self.window.comparison_analysis_panel
        bounds = panel._bounds
        if bounds is None:
            if not panel._documents:
                panel.roi_label.clear()
                panel.roi_label.setToolTip("")
                panel.roi_label.setAccessibleName("ROI bounds")
                return
            height, width = panel._documents[0].reference_shape
            if height <= 0 or width <= 0:
                panel.roi_label.clear()
                return
            bounds = RoiBounds(0, 0, width, height)

        panel.roi_label.setText(
            f"({bounds.x}, {bounds.y}) · {bounds.width} × {bounds.height}"
        )
        panel.roi_label.setToolTip(
            f"X {bounds.x}, Y {bounds.y}, Width {bounds.width}, Height {bounds.height}"
        )
        panel.roi_label.setAccessibleName(
            "ROI bounds: "
            f"X {bounds.x}, Y {bounds.y}, Width {bounds.width}, Height {bounds.height}"
        )

    def _default_roi(self) -> RoiBounds | None:
        active = self.window._shared_roi
        if isinstance(active, RoiBounds):
            return active

        shapes = [
            document.reference_shape
            for document in self.window.current_comparison_documents()
            if document.reference_shape[0] > 0 and document.reference_shape[1] > 0
        ]
        if not shapes:
            return None
        height = min(shape[0] for shape in shapes)
        width = min(shape[1] for shape in shapes)
        return RoiBounds(0, 0, width, height)

    def create_roi_dialog(self) -> RoiEditorDialog | None:
        bounds = self._default_roi()
        if bounds is None:
            return None
        return RoiEditorDialog(self, bounds)

    def _show_roi_editor(self) -> RoiEditorDialog | None:
        existing = self._active_roi_dialog
        if existing is not None:
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return existing

        dialog = self.create_roi_dialog()
        if dialog is None:
            return None
        self._active_roi_dialog = dialog
        dialog.finished.connect(  # type: ignore[attr-defined]
            lambda _result, current=dialog: self._roi_dialog_finished(current)
        )
        dialog.open()
        return dialog

    def _roi_dialog_finished(self, dialog: RoiEditorDialog) -> None:
        if self._active_roi_dialog is dialog:
            self._active_roi_dialog = None
        dialog.deleteLater()

    def _install_three_view_affordance(self) -> None:
        controller = self.quick_compare
        controller.three_view_group.hide()
        controller.three_view_label.hide()
        controller.three_view_equal.hide()
        controller.three_view_focus.hide()

        layout_host = self.window.layout_selector.parentWidget()
        layout = layout_host.layout() if isinstance(layout_host, QWidget) else None
        if not isinstance(layout, QHBoxLayout):
            raise RuntimeError("Layout selector host is unavailable")

        self.three_view_button = QToolButton(layout_host)
        self.three_view_button.setObjectName("threeViewArrangementButton")
        self.three_view_button.setAutoRaise(True)
        self.three_view_button.setCheckable(False)
        self.three_view_button.setFixedSize(TOKENS.control_height, TOKENS.control_height)
        self.three_view_button.setAccessibleName("3-view arrangement")
        self.three_view_button.clicked.connect(self._toggle_three_view_variant)  # type: ignore[attr-defined]
        layout.addWidget(self.three_view_button)

        def update_three_view_controls() -> None:
            controller.three_view_group.hide()
            self._sync_three_view_button()

        controller._update_three_view_controls = update_three_view_controls
        metric_owner = getattr(self.window, "_command_row_metric_refresh", None)
        refresh = getattr(metric_owner, "refresh", None)
        if callable(refresh):
            refresh()

    def _compact_command_row(self) -> None:
        """Keep command groups at content width and give surplus width to one trailing spacer."""

        layout = self.window.presentation_controls_layout
        if not isinstance(layout, QHBoxLayout):
            return
        layout.setSpacing(TOKENS.spacing_sm)
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item is None:
                continue
            layout.setStretch(index, 1 if item.spacerItem() is not None else 0)
        layout.invalidate()
        layout.activate()

    def _three_view_enabled(self) -> bool:
        return (
            self.window.central_stack.currentWidget() is self.window.multi_compare_view
            and self.window.multi_compare_view._document_count == 3
        )

    def _toggle_three_view_variant(self) -> None:
        if not self._three_view_enabled():
            return
        current = self.quick_compare._effective_three_view_variant()
        target = "Focus" if current == "Equal" else "Equal"
        self.quick_compare.set_three_view_variant(target)
        self._sync_three_view_button()

    def _sync_three_view_button(self) -> None:
        enabled = self._three_view_enabled()
        variant = self.quick_compare._effective_three_view_variant()
        self.three_view_button.setEnabled(enabled)
        self.three_view_button.setIcon(
            toolbar_icon("three_focus" if variant == "Focus" else "three_equal")
        )
        target = "Focus" if variant == "Equal" else "Equal"
        self.three_view_button.setToolTip(
            f"3-view arrangement: {variant}. Click for {target}."
            if enabled
            else "3-view arrangement is available when exactly three views are shown."
        )

    def _wrap_render_selection(self) -> None:
        original_render = self.window._render_selection

        def render_selection(preserve_view: bool = False) -> None:
            original_render(preserve_view)
            self._sync_controls()

        self.window._render_selection = render_selection

    def _sync_controls(self) -> None:
        panel = self.window.comparison_analysis_panel
        self.roi_edit_button.setEnabled(bool(panel._documents))
        self._sync_roi_summary()
        self._sync_three_view_button()


def install_issue77_ui_design_followup(window: Any) -> Issue77UiDesignFollowup:
    existing = getattr(window, "issue77_ui_design_followup", None)
    if isinstance(existing, Issue77UiDesignFollowup):
        return existing
    controller = Issue77UiDesignFollowup(window)
    window.issue77_ui_design_followup = controller
    return controller
