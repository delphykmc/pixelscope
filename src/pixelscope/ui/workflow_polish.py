from __future__ import annotations

import weakref
from collections import Counter
from contextlib import suppress
from typing import Any, cast

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QLabel, QMenu, QVBoxLayout, QWidget

from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.lifecycle_hooks import OwnerCallback, WeakOwnerHook
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
            current_page_ids = {
                document.document_id for document in self.window.current_comparison_documents()
            }
            primary.setEnabled(document_key in current_page_ids)
            if not primary.isEnabled():
                primary.setToolTip("Primary is available only on the current Comparison Page")
            compare = menu.addAction("Show Selected in Multi View")
            same_position = QMenu("Compare same position with...", menu)
            menu.addMenu(same_position)
            targets = self.window.folder_comparison_targets(document_key)
            if targets:
                labels = {
                    target.target_folder_key: self._folder_display_label(target.target_folder_key)
                    for target in targets
                }
                label_counts = Counter(labels.values())
                for target in targets:
                    folder = self.window._folder_paths.get(target.target_folder_key)
                    label = labels[target.target_folder_key]
                    if label_counts[label] > 1 and folder is not None:
                        label = f"{label} — {folder.parent}"
                    target_action = same_position.addAction(label)
                    if folder is not None:
                        target_action.setToolTip(
                            f"Add position {target.ordinal_index + 1} from {folder}"
                        )
                    target_action.triggered.connect(  # type: ignore[attr-defined]
                        lambda _checked=False,
                        anchor=document_key,
                        folder_key=target.target_folder_key: (
                            self.window.add_same_position_from_folder(anchor, folder_key)
                        )
                    )
            else:
                same_position.setEnabled(False)
                same_position.setToolTip(
                    "Select 1–5 images from different folders with an available matching position"
                )
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

    def _folder_display_label(self, folder_key: str) -> str:
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            raw_path = str(item.data(0, self.tree.PATH_ROLE) or "")
            if raw_path.casefold() == folder_key:
                return str(item.text(0))
        folder = self.window._folder_paths.get(folder_key)
        return str(folder.name) if folder is not None else folder_key

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
    page_reservation = (
        page_label.fontMetrics().horizontalAdvance("999 / 999") + 2 * TOKENS.spacing_sm
    )
    range_reservation = (
        range_label.fontMetrics().horizontalAdvance("9999–9999 of 9999") + 2 * TOKENS.spacing_sm
    )
    page_label.setFixedWidth(page_reservation)
    range_label.setFixedWidth(range_reservation)

    page_layout = window.comparison_page_group.layout()
    if page_layout is not None:
        page_layout.setSpacing(TOKENS.spacing_sm)

    if bool(window.comparison_page_group.property("workflowPolished")):
        return
    window.comparison_page_group.setProperty("workflowPolished", True)
    original_update = OwnerCallback(window._update_comparison_page_controls)

    def update_controls(_window: Any) -> None:
        original_update()
        _start, _end, total = _window._comparison_page_range()
        if total > 0:
            _window.comparison_page_label.setFixedWidth(
                max(
                    page_reservation,
                    _window.comparison_page_label.fontMetrics().horizontalAdvance(
                        _window.comparison_page_label.text()
                    )
                    + 2 * TOKENS.spacing_sm,
                )
            )
            _window.comparison_page_range_label.setFixedWidth(
                max(
                    range_reservation,
                    _window.comparison_page_range_label.fontMetrics().horizontalAdvance(
                        _window.comparison_page_range_label.text()
                    )
                    + 2 * TOKENS.spacing_sm,
                )
            )
            return
        _window.comparison_page_label.setFixedWidth(page_reservation)
        _window.comparison_page_range_label.setFixedWidth(range_reservation)
        _window.comparison_page_group.setVisible(True)
        _window.comparison_page_label.setText("— / —")
        _window.comparison_page_range_label.setText("—")
        for button in (
            _window.previous_comparison_page_button,
            _window.next_comparison_page_button,
        ):
            button.setVisible(True)
            button.setEnabled(False)

    window._update_comparison_page_controls = WeakOwnerHook(window, update_controls)
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

    original_navigation = OwnerCallback(header.set_navigation_items)
    separator_ref = weakref.ref(separator)

    def set_navigation_items(
        _header: Any,
        items: list[tuple[str, str, str]],
        current_key: str,
        *,
        _original: Any = original_navigation,
    ) -> None:
        _original(items, current_key)
        current_separator = separator_ref()
        if current_separator is not None:
            current_separator.setVisible(len(items) > 1)

    header.set_navigation_items = WeakOwnerHook(header, set_navigation_items)

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

    original_difference = OwnerCallback(header.set_difference_reference)

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
        if not bool(kwargs.get("visible", False)):
            return
        a_slot = kwargs.get("a_slot")
        b_slot = kwargs.get("b_slot")
        if a_slot is not None:
            _header.difference_a_badge.setText(f"A {a_slot}")
        if b_slot is not None:
            _header.difference_b_badge.setText(f"B {b_slot}")

    header.set_difference_reference = WeakOwnerHook(header, set_difference_reference)


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
    original_validate = OwnerCallback(panel._validate)
    original_calculate = OwnerCallback(panel.calculate_difference)
    hint_ref = weakref.ref(hint)

    def validate(_panel: Any) -> str | None:
        reason = cast(str | None, original_validate())
        current_hint = hint_ref()
        if current_hint is None:
            return reason
        calculated_result = _panel.last_result is not None
        in_flight = _panel._worker is not None or _panel._preview_worker is not None
        pending = (
            reason is None
            and not _panel.has_cached_map()
            and not calculated_result
            and not in_flight
        )
        current_hint.setVisible(pending)
        if pending:
            _panel.status.setText("Not calculated")
        elif reason is None and calculated_result and _panel.status.text() == "Ready":
            _panel.status.setText("Calculated")
        return reason

    panel._validate = WeakOwnerHook(panel, validate)

    def calculate_difference(
        _panel: Any,
        _checked: bool = False,
        *,
        publish_result: bool = True,
    ) -> None:
        current_hint = hint_ref()
        if current_hint is not None:
            current_hint.hide()
        original_calculate(_checked, publish_result=publish_result)
        if current_hint is not None and (
            _panel._worker is not None or _panel._preview_worker is not None
        ):
            current_hint.hide()

    panel.calculate_difference = WeakOwnerHook(panel, calculate_difference)
    panel.calculate.pressed.connect(hint.hide)

    panel_ref = weakref.ref(panel)

    def calculated(*_args: object) -> None:
        current_hint = hint_ref()
        current_panel = panel_ref()
        if current_hint is not None:
            current_hint.hide()
        if (
            current_panel is not None
            and current_panel.last_result is not None
            and current_panel.status.text() == "Ready"
        ):
            current_panel.status.setText("Calculated")

    panel.result_ready.connect(calculated)
    panel.preview_updated.connect(calculated)
    panel._validate()


def _install_review_polish(review_controller: Any) -> None:
    if bool(review_controller.count_label.property("workflowPolished")):
        return
    review_controller.count_label.setProperty("workflowPolished", True)
    original_sync = OwnerCallback(review_controller._sync_controls)

    def sync_controls(_controller: Any) -> None:
        original_sync()
        count = _controller.state.picked_count
        _controller.count_label.setText(f"● Picked {count}")
        color = TOKENS.selection if count > 0 else TOKENS.text_secondary
        _controller.count_label.setStyleSheet(f"QLabel {{ color: {color}; font-weight: 600; }}")

    review_controller._sync_controls = WeakOwnerHook(review_controller, sync_controls)
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
    panel.install_empty_hint(hint)


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
    panel.install_empty_hint(hint)


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
