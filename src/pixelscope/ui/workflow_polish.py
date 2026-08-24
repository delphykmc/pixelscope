from __future__ import annotations

from contextlib import suppress
from types import MethodType
from typing import Any, cast

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QLabel, QMenu, QVBoxLayout, QWidget

from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar


class FilesContextMenuController(QObject):
    """Provide Files-panel convenience commands without changing selection authority."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.tree = window.document_list
        with suppress(RuntimeError, TypeError):
            self.tree.customContextMenuRequested.disconnect(self.tree._show_context_menu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)

    def build_menu_for_item(self, item: Any | None) -> QMenu:
        menu = QMenu(self.tree)
        for name in ("Open Images...", "Open Folder..."):
            action = self.window.action_map.get(name)
            if isinstance(action, QAction):
                menu.addAction(action)

        if item is None:
            return menu

        document_id = item.data(0, Qt.ItemDataRole.UserRole)
        menu.addSeparator()
        if document_id is not None:
            document_key = str(document_id)
            primary = menu.addAction("Set as Primary")
            compare = menu.addAction("Show Selected in Multi View")
            menu.addSeparator()
            remove = menu.addAction("Remove Selected from Files")

            primary.triggered.connect(  # type: ignore[attr-defined]
                lambda _checked=False, value=document_key: self.tree.focus_requested.emit(value)
            )
            compare.triggered.connect(  # type: ignore[attr-defined]
                lambda _checked=False: self.tree.compare_requested.emit()
            )
            remove.triggered.connect(  # type: ignore[attr-defined]
                lambda _checked=False: self._remove_selected_images()
            )
            return menu

        child_ids = [
            str(item.child(index).data(0, Qt.ItemDataRole.UserRole))
            for index in range(item.childCount())
            if item.child(index).data(0, Qt.ItemDataRole.UserRole) is not None
        ]
        if child_ids:
            folder_ids = tuple(child_ids)
            remove_folder = menu.addAction("Remove Folder from Files")
            remove_folder.triggered.connect(  # type: ignore[attr-defined]
                lambda _checked=False, ids=folder_ids: self.tree._emit_remove_request(list(ids))
            )
        return menu

    def _remove_selected_images(self) -> None:
        self.tree._emit_remove_request(
            [
                str(item.data(0, Qt.ItemDataRole.UserRole))
                for item in self.tree.selected_document_items()
            ]
        )

    def _show_context_menu(self, position: QPoint) -> None:
        item = self.tree.itemAt(position)
        menu = self.build_menu_for_item(item)
        menu.exec(self.tree.viewport().mapToGlobal(position))


class PlotEmptyHintController(QObject):
    """Overlay a centered guide without participating in the plot layout geometry."""

    def __init__(self, host: QWidget, text: str, object_name: str) -> None:
        super().__init__(host)
        self.host = host
        self.label = QLabel(text, host)
        self.label.setObjectName(object_name)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            f"QLabel {{ color: {TOKENS.text_secondary}; padding: {TOKENS.spacing_lg}px; }}"
        )
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.host.installEventFilter(self)
        self.show(text)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.host and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            self._sync_geometry()
        return super().eventFilter(watched, event)

    def show(self, text: str | None = None) -> None:
        if text is not None:
            self.label.setText(text)
        self._sync_geometry()
        self.label.show()
        self.label.raise_()

    def hide(self) -> None:
        self.label.hide()

    def _sync_geometry(self) -> None:
        self.label.setGeometry(self.host.rect())


def _install_files_context_menu(window: Any) -> FilesContextMenuController:
    existing = getattr(window, "workflow_files_context_menu", None)
    if isinstance(existing, FilesContextMenuController):
        return existing
    controller = FilesContextMenuController(window)
    window.workflow_files_context_menu = controller
    return controller


def _install_shortcuts(window: Any) -> None:
    split_action = getattr(window, "split_channels_action", None)
    if isinstance(split_action, QAction):
        split_action.setShortcut("S")

    iqa_action = getattr(window, "iqa_workspace_action", None)
    if isinstance(iqa_action, QAction):
        iqa_action.setShortcut("Ctrl+Shift+I")
        iqa_action.setToolTip("Show or hide the IQA Workspace (Ctrl+Shift+I)")
        iqa_action.setStatusTip(iqa_action.toolTip())


def _install_iqa_dock_chrome(window: Any) -> None:
    workspace = getattr(window, "iqa_workspace", None)
    dock = getattr(window, "iqa_dock", None)
    if workspace is None or dock is None:
        return
    workspace._install_dock_title()
    title_bar = dock.titleBarWidget()
    if isinstance(title_bar, PlotsDockTitleBar):
        title_bar.sync(dock.isFloating())
        window.iqa_dock_title = title_bar


def _install_toolbar_spacing(window: Any) -> None:
    toolbar = window.main_toolbar
    if bool(toolbar.property("workflowPolished")):
        return
    toolbar.setProperty("workflowPolished", True)
    toolbar.setStyleSheet(
        toolbar.styleSheet()
        + f"QToolBar {{ spacing: {TOKENS.spacing_xs + 1}px; }}"
        + f"QToolBar QToolButton {{ padding-left: {TOKENS.spacing_sm + 1}px; "
        f"padding-right: {TOKENS.spacing_sm + 1}px; }}"
        + f"QToolBar::separator {{ margin-left: {TOKENS.spacing_sm}px; "
        f"margin-right: {TOKENS.spacing_sm}px; }}"
    )


def _install_page_polish(window: Any) -> None:
    page_label = window.comparison_page_label
    range_label = window.comparison_page_range_label
    page_label.setFixedWidth(
        page_label.fontMetrics().horizontalAdvance("999 / 999") + 2 * TOKENS.spacing_sm
    )
    range_label.setFixedWidth(
        range_label.fontMetrics().horizontalAdvance("9999–9999 of 9999")
        + 2 * TOKENS.spacing_sm
    )

    page_layout = window.comparison_page_group.layout()
    if page_layout is not None:
        page_layout.setSpacing(TOKENS.spacing_sm)

    if bool(window.comparison_page_group.property("workflowPolished")):
        return
    window.comparison_page_group.setProperty("workflowPolished", True)
    original_update = window._update_comparison_page_controls

    def update_controls(_window: Any) -> None:
        original_update()
        _start, _end, total = _window._comparison_page_range()
        if total > 0:
            return
        _window.comparison_page_group.setVisible(True)
        _window.comparison_page_label.setText("— / —")
        _window.comparison_page_range_label.setText("—")
        for button in (
            _window.previous_comparison_page_button,
            _window.next_comparison_page_button,
        ):
            button.setVisible(True)
            button.setEnabled(False)

    window._update_comparison_page_controls = MethodType(update_controls, window)
    window._comparison_page_controls_state = None
    window._update_comparison_page_controls()


def _install_header_polish(window: Any) -> None:
    header = window.viewer.header
    if bool(header.property("workflowPolished")):
        return
    header.setProperty("workflowPolished", True)
    layout = header.layout()
    if layout is None:
        return

    separator = QFrame(header)
    separator.setObjectName("singleNavigationSeparator")
    separator.setFrameShape(QFrame.Shape.VLine)
    separator.setFrameShadow(QFrame.Shadow.Plain)
    separator.setFixedHeight(TOKENS.control_height - 8)
    separator.setStyleSheet(f"QFrame {{ color: {TOKENS.border}; }}")
    separator.hide()
    navigation_index = layout.indexOf(header.navigation)
    layout.insertWidget(navigation_index + 1, separator)
    header.workflow_navigation_separator = separator

    original_navigation = header.set_navigation_items

    def set_navigation_items(
        _header: Any,
        items: list[tuple[str, str, str]],
        current_key: str,
        *,
        _original: Any = original_navigation,
        _separator: QFrame = separator,
    ) -> None:
        _original(items, current_key)
        _separator.setVisible(len(items) > 1)

    header.set_navigation_items = MethodType(set_navigation_items, header)

    reference_style = (
        f"QLabel {{ background: {TOKENS.workspace_background}; "
        f"color: {TOKENS.text_secondary}; border: 1px solid {TOKENS.border}; "
        f"border-radius: 2px; padding: 1px {TOKENS.spacing_sm}px; "
        "font-weight: 600; }"
    )
    for badge in (header.difference_a_badge, header.difference_b_badge):
        badge.setObjectName("differenceReferenceBadge")
        badge.setStyleSheet(reference_style)
    header.difference_vs.setText("↔")
    header.difference_vs.setStyleSheet(f"QLabel {{ color: {TOKENS.text_secondary}; }}")

    original_difference = header.set_difference_reference

    def set_difference_reference(
        _header: Any,
        *args: object,
        _original: Any = original_difference,
        **kwargs: object,
    ) -> None:
        prefix = str(kwargs.get("prefix", ""))
        if prefix:
            kwargs["prefix"] = prefix.replace(" [", " · ").replace("]", "")
        _original(*args, **kwargs)
        if not _header.difference_reference.isVisible():
            return
        a_slot = kwargs.get("a_slot")
        b_slot = kwargs.get("b_slot")
        if a_slot is not None:
            _header.difference_a_badge.setText(f"A {a_slot}")
        if b_slot is not None:
            _header.difference_b_badge.setText(f"B {b_slot}")

    header.set_difference_reference = MethodType(set_difference_reference, header)


def _primary_analysis_action_style() -> str:
    return (
        f"QPushButton#primaryAction {{ background: {TOKENS.raised_background}; "
        f"color: {TOKENS.text_primary}; border: 1px solid {TOKENS.accent}; "
        f"padding: {TOKENS.spacing_xs}px {TOKENS.spacing_md}px; font-weight: 600; }}"
        f"QPushButton#primaryAction:hover:enabled {{ background: {TOKENS.panel_background}; }}"
        f"QPushButton#primaryAction:pressed:enabled {{ "
        f"background: {TOKENS.workspace_background}; }}"
        f"QPushButton#primaryAction:disabled {{ background: {TOKENS.raised_background}; "
        f"border-color: {TOKENS.border}; color: {TOKENS.text_disabled}; }}"
    )


def _install_difference_polish(window: Any) -> None:
    panel = window.difference_panel
    unified_style = panel.calculate.styleSheet() + _primary_analysis_action_style()
    command_buttons = [panel.calculate]
    export_controller = getattr(window, "analysis_export_controller", None)
    for name in (
        "statistics_copy_button",
        "difference_metrics_export_button",
        "difference_metrics_copy_button",
    ):
        button = getattr(export_controller, name, None)
        if button is not None:
            command_buttons.append(button)
    for button in command_buttons:
        button.setStyleSheet(unified_style)
    panel.calculate.setMinimumWidth(92)

    layout = panel.layout()
    if not isinstance(layout, QVBoxLayout):
        return
    existing = getattr(panel, "workflow_metrics_hint", None)
    if isinstance(existing, QLabel):
        hint = existing
    else:
        hint = QLabel("Click Calculate to show Difference metrics.", panel)
        hint.setObjectName("differenceMetricsHint")
        hint.setStyleSheet(f"QLabel {{ color: {TOKENS.text_secondary}; }}")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        metrics_index = layout.indexOf(panel.metrics)
        layout.insertWidget(metrics_index, hint)
        panel.workflow_metrics_hint = hint

    if bool(panel.property("workflowPolished")):
        return
    panel.setProperty("workflowPolished", True)
    original_validate = panel._validate

    def validate(_panel: Any) -> str | None:
        reason = cast(str | None, original_validate())
        pending = reason is None and not _panel.has_cached_map()
        hint.setVisible(pending)
        if pending:
            _panel.status.setText("Not calculated")
        return reason

    panel._validate = MethodType(validate, panel)

    def calculated(*_args: object) -> None:
        hint.hide()
        if panel.last_result is not None and panel.status.text() == "Ready":
            panel.status.setText("Calculated")

    panel.result_ready.connect(calculated)
    panel.preview_updated.connect(calculated)
    panel._validate()


def _install_review_polish(review_controller: Any) -> None:
    if bool(review_controller.count_label.property("workflowPolished")):
        return
    review_controller.count_label.setProperty("workflowPolished", True)
    original_sync = review_controller._sync_controls

    def sync_controls(_controller: Any) -> None:
        original_sync()
        count = _controller.state.picked_count
        _controller.count_label.setText(f"● Picked {count}")
        color = TOKENS.selection if count > 0 else TOKENS.text_secondary
        _controller.count_label.setStyleSheet(
            f"QLabel {{ color: {color}; font-weight: 600; }}"
        )

    review_controller._sync_controls = MethodType(sync_controls, review_controller)
    review_controller._sync_controls()


def _install_histogram_polish(window: Any) -> None:
    panel = window.comparison_analysis_panel
    if bool(panel.histogram_panel.property("workflowPolished")):
        return
    panel.histogram_panel.setProperty("workflowPolished", True)

    hint = PlotEmptyHintController(
        panel.histogram_grid,
        "Select an image to view Histogram",
        "histogramEmptyHint",
    )
    panel.workflow_histogram_hint = hint.label
    panel.workflow_histogram_hint_controller = hint

    original_clear = panel.clear
    original_render = panel._render

    def clear(_panel: Any) -> None:
        original_clear()
        hint.show()

    def render(_panel: Any, results: object, histogram_specs: object) -> None:
        hint.hide()
        original_render(results, histogram_specs)

    panel.clear = MethodType(clear, panel)
    panel._render = MethodType(render, panel)
    if panel.last_results:
        hint.hide()
    else:
        hint.show()


def _install_line_profile_polish(window: Any) -> None:
    panel = window.line_profile_panel
    if bool(panel.property("workflowPolished")):
        return
    panel.setProperty("workflowPolished", True)

    hint = PlotEmptyHintController(
        panel.plot_grid,
        "Select an image to use Line Profile\n\nThen Shift + drag to draw a line",
        "lineProfileEmptyHint",
    )
    panel.workflow_empty_hint = hint.label
    panel.workflow_empty_hint_controller = hint

    def sync_hint() -> None:
        if panel._selection is not None:
            hint.hide()
            return
        if panel._documents:
            hint.show("Draw a line to view its profile\n\nShift + drag on an image")
            panel.status.setText("Shift+drag on an image to set a line profile")
        else:
            hint.show(
                "Select an image to use Line Profile\n\nThen Shift + drag to draw a line"
            )
            panel.status.setText("Select an image, then Shift+drag to set a line profile")

    original_clear = panel._clear_plot
    original_render = panel._render

    def clear_plot(_panel: Any) -> None:
        original_clear()
        sync_hint()

    def render(_panel: Any, results: object) -> None:
        hint.hide()
        original_render(results)

    panel._clear_plot = MethodType(clear_plot, panel)
    panel._render = MethodType(render, panel)
    sync_hint()


def install_workflow_polish(window: Any, review_controller: Any) -> FilesContextMenuController:
    """Apply small post-phase workflow/UI refinements without changing core authorities."""

    controller = _install_files_context_menu(window)
    _install_shortcuts(window)
    _install_iqa_dock_chrome(window)
    _install_toolbar_spacing(window)
    _install_page_polish(window)
    _install_header_polish(window)
    _install_difference_polish(window)
    _install_review_polish(review_controller)
    _install_histogram_polish(window)
    _install_line_profile_polish(window)
    return controller
