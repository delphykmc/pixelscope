from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core.roi import RoiBounds
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.quick_compare import QuickCompareController


class RoiEditorDialog(QDialog):
    """Compact modal editor for the application-owned shared ROI."""

    def __init__(self, owner: Issue77UiDesignFollowup, bounds: RoiBounds) -> None:
        super().__init__(owner.window)
        self.owner = owner
        self.setWindowTitle("Set ROI")
        self.setModal(True)

        root = QVBoxLayout(self)
        form = QFormLayout()
        form.setHorizontalSpacing(TOKENS.spacing_md)
        form.setVerticalSpacing(TOKENS.spacing_sm)
        root.addLayout(form)

        self.x_input = self._spin_box(0, bounds.x, "ROI X")
        self.y_input = self._spin_box(0, bounds.y, "ROI Y")
        self.width_input = self._spin_box(1, bounds.width, "ROI Width")
        self.height_input = self._spin_box(1, bounds.height, "ROI Height")
        form.addRow("X", self.x_input)
        form.addRow("Y", self.y_input)
        form.addRow("Width", self.width_input)
        form.addRow("Height", self.height_input)

        self.validation = QLabel(self)
        self.validation.setObjectName("roiEditorValidation")
        self.validation.setWordWrap(True)
        self.validation.hide()
        root.addWidget(self.validation)

        buttons = QDialogButtonBox(self)
        self.cancel_button = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.apply_button = buttons.addButton("Apply", QDialogButtonBox.ButtonRole.AcceptRole)
        self.apply_button.setDefault(True)
        self.cancel_button.clicked.connect(self.reject)  # type: ignore[attr-defined]
        self.apply_button.clicked.connect(self._apply)  # type: ignore[attr-defined]
        root.addWidget(buttons)

    @staticmethod
    def _spin_box(minimum: int, value: int, accessible_name: str) -> QSpinBox:
        control = QSpinBox()
        control.setRange(minimum, 2_147_483_647)
        control.setValue(value)
        control.setAccelerated(True)
        control.setKeyboardTracking(False)
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
        self.validation.setText("ROI must fit every frame on the current comparison page.")
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

        self._install_roi_affordance()
        self._install_three_view_affordance()
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

        self.roi_edit_button = QPushButton("Edit...", panel)
        self.roi_edit_button.setObjectName("roiEditButton")
        self.roi_edit_button.setToolTip("Enter exact shared ROI coordinates")
        self.roi_edit_button.setAccessibleName("Edit ROI")
        self.roi_edit_button.clicked.connect(self._show_roi_editor)  # type: ignore[attr-defined]

        panel.region_layout.addWidget(self.roi_bounds_label, 1, 0)
        panel.region_layout.addWidget(panel.roi_label, 1, 1)
        panel.region_layout.addWidget(
            self.roi_edit_button,
            1,
            2,
            alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        panel.region_layout.setColumnStretch(1, 1)
        panel.region_layout.setColumnStretch(2, 0)

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

    def _show_roi_editor(self) -> None:
        dialog = self.create_roi_dialog()
        if dialog is not None:
            dialog.exec()

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
        self.three_view_button.setIcon(self._three_view_icon(variant))
        target = "Focus" if variant == "Equal" else "Equal"
        self.three_view_button.setToolTip(
            f"3-view arrangement: {variant}. Click for {target}."
            if enabled
            else "3-view arrangement is available when exactly three views are shown."
        )

    def _three_view_icon(self, variant: str) -> QIcon:
        size = max(16, TOKENS.icon_size)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        color = self.three_view_button.palette().color(QPalette.ColorRole.ButtonText)
        pen = QPen(color)
        pen.setWidthF(1.2)
        painter.setPen(pen)
        margin = 2.0
        gap = 1.5
        width = float(size) - 2.0 * margin
        height = float(size) - 2.0 * margin
        if variant == "Focus":
            left_width = width * 0.62
            right_x = margin + left_width + gap
            right_width = width - left_width - gap
            half_height = (height - gap) / 2.0
            painter.drawRect(QRectF(margin, margin, left_width, height))
            painter.drawRect(QRectF(right_x, margin, right_width, half_height))
            painter.drawRect(
                QRectF(right_x, margin + half_height + gap, right_width, half_height)
            )
        else:
            cell_width = (width - 2.0 * gap) / 3.0
            for index in range(3):
                x = margin + index * (cell_width + gap)
                painter.drawRect(QRectF(x, margin, cell_width, height))
        painter.end()
        return QIcon(pixmap)

    def _wrap_render_selection(self) -> None:
        original_render = self.window._render_selection

        def render_selection(preserve_view: bool = False) -> None:
            original_render(preserve_view)
            self._sync_controls()

        self.window._render_selection = render_selection

    def _sync_controls(self) -> None:
        panel = self.window.comparison_analysis_panel
        self.roi_edit_button.setEnabled(bool(panel._documents))
        self._sync_three_view_button()


def install_issue77_ui_design_followup(window: Any) -> Issue77UiDesignFollowup:
    existing = getattr(window, "issue77_ui_design_followup", None)
    if isinstance(existing, Issue77UiDesignFollowup):
        return existing
    controller = Issue77UiDesignFollowup(window)
    window.issue77_ui_design_followup = controller
    return controller
