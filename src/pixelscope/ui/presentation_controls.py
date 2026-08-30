from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEvent, QMetaObject, QObject, QSize, Qt, Slot
from PySide6.QtGui import QFont, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.toolbar_icons import toolbar_icon

_COMPACT_PICK_COUNT_WIDTH = 50
_QT_WIDGET_SIZE_MAX = 16_777_215


def _presentation_controls_style() -> str:
    """Return compact dark command-bar styling from the shared engineering tokens."""

    return (
        f"QWidget#presentationControls {{ background: {TOKENS.panel_background}; "
        f"border-bottom: 1px solid {TOKENS.border}; }}"
        f"QWidget#presentationControls QLabel {{ color: {TOKENS.text_secondary}; }}"
        f"QWidget#presentationControls QLabel:disabled {{ color: {TOKENS.text_disabled}; }}"
        f"QWidget#presentationControls QLabel#comparisonPageStatus {{ "
        f"color: {TOKENS.text_primary}; font-weight: 600; }}"
        f"QWidget#presentationControls QLabel#comparisonPageRange {{ "
        f"color: {TOKENS.text_secondary}; }}"
        f"QWidget#presentationControls QComboBox {{ background: {TOKENS.raised_background}; "
        f"color: {TOKENS.text_primary}; border: 1px solid {TOKENS.border}; "
        f"border-radius: 2px; padding: 0 {TOKENS.spacing_sm}px; }}"
        f"QWidget#presentationControls QComboBox:hover {{ "
        f"border-color: {TOKENS.text_secondary}; }}"
        f"QWidget#presentationControls QComboBox:focus {{ border-color: {TOKENS.accent}; }}"
        f"QWidget#presentationControls QComboBox:disabled {{ "
        f"background: {TOKENS.panel_background}; color: {TOKENS.text_disabled}; "
        f"border-color: {TOKENS.border}; }}"
        "QWidget#presentationControls QToolButton#previousComparisonPage, "
        "QWidget#presentationControls QToolButton#nextComparisonPage { "
        "background: transparent; border: 1px solid transparent; "
        "border-radius: 2px; padding: 0; }"
        "QWidget#presentationControls QToolButton#previousComparisonPage:hover, "
        "QWidget#presentationControls QToolButton#nextComparisonPage:hover { "
        f"background: {TOKENS.raised_background}; border-color: {TOKENS.border}; }}"
        "QWidget#presentationControls QToolButton#previousComparisonPage:pressed, "
        "QWidget#presentationControls QToolButton#nextComparisonPage:pressed { "
        f"background: {TOKENS.workspace_background}; border-color: {TOKENS.accent}; }}"
        "QWidget#presentationControls QToolButton#previousComparisonPage:disabled, "
        "QWidget#presentationControls QToolButton#nextComparisonPage:disabled { "
        "background: transparent; border-color: transparent; }"
    )


def _analysis_action_button_style() -> str:
    """Render Analysis actions as quiet commands that reveal button chrome on use."""

    hover_background = "#4b5058"
    hover_border = "#6a737e"
    pressed_background = "#34383e"
    pressed_border_high = "#25282d"
    pressed_border_low = "#59616b"
    disabled_text = "#666b72"
    return (
        "QPushButton, QToolButton { "
        f"background: transparent; color: {TOKENS.text_primary}; "
        "border: 1px solid transparent; border-radius: 3px; }"
        f"QPushButton {{ padding: {TOKENS.spacing_xs}px {TOKENS.spacing_md}px; }}"
        f"QToolButton {{ padding: 1px {TOKENS.spacing_xs}px; }}"
        "QPushButton:hover:enabled, QToolButton:hover:enabled { "
        f"background: {hover_background}; border-color: {hover_border}; }}"
        "QPushButton:pressed:enabled, QToolButton:pressed:enabled { "
        f"background: {pressed_background}; "
        f"border-top-color: {pressed_border_high}; "
        f"border-left-color: {pressed_border_high}; "
        f"border-right-color: {pressed_border_low}; "
        f"border-bottom-color: {pressed_border_low}; "
        f"padding-top: {TOKENS.spacing_xs + 1}px; "
        f"padding-bottom: {max(0, TOKENS.spacing_xs - 1)}px; }}"
        "QPushButton:focus:enabled, QToolButton:focus:enabled { "
        f"border-color: {TOKENS.accent}; }}"
        "QPushButton:disabled, QToolButton:disabled { "
        f"background: transparent; color: {disabled_text}; "
        "border-color: transparent; }"
    )


def _set_bold_label(label: QLabel) -> None:
    font = label.font()
    font.setWeight(QFont.Weight.Bold)
    label.setFont(font)


class _ElidingMetadataLabel(QLabel):
    """Keep complete label text as metadata while painting within its allocation."""

    def __init__(
        self,
        text: str,
        description: str,
        maximum_compact_width: int,
        parent: QWidget,
    ) -> None:
        super().__init__(text, parent)
        self._description = description
        self._maximum_compact_width = maximum_compact_width
        self.setMinimumWidth(0)
        self.setMaximumWidth(maximum_compact_width)
        self._sync_metadata(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API override
        super().setText(text)
        self._sync_metadata(text)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API override
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def setFixedWidth(self, width: int) -> None:  # noqa: N802 - Qt API override
        """Translate legacy reservations into an eliding upper bound."""

        self.setMinimumWidth(0)
        self.setMaximumWidth(min(width, self._maximum_compact_width))

    def paintEvent(self, _event: object) -> None:  # noqa: N802 - Qt API override
        painter = QPainter(self)
        elided = self.fontMetrics().elidedText(
            self.text(),
            Qt.TextElideMode.ElideRight,
            max(0, self.contentsRect().width()),
        )
        self.style().drawItemText(
            painter,
            self.contentsRect(),
            int(self.alignment()),
            self.palette(),
            self.isEnabled(),
            elided,
            QPalette.ColorRole.WindowText,
        )

    def _sync_metadata(self, text: str) -> None:
        self.setToolTip(text)
        self.setAccessibleName(f"{self._description}: {text}" if text else self._description)


def _replace_page_label(
    window: Any,
    attribute_name: str,
    description: str,
    stretch: int,
    maximum_width: int,
) -> QLabel:
    old_label = getattr(window, attribute_name)
    if isinstance(old_label, _ElidingMetadataLabel):
        return old_label
    parent = old_label.parentWidget()
    parent_layout = parent.layout() if parent is not None else None
    if not isinstance(parent, QWidget) or not isinstance(parent_layout, QHBoxLayout):
        raise RuntimeError("Comparison Page label must belong to the page command group")
    index = parent_layout.indexOf(old_label)
    if index < 0:
        raise RuntimeError("Comparison Page label is missing from its command layout")

    label = _ElidingMetadataLabel(old_label.text(), description, maximum_width, parent)
    label.setObjectName(old_label.objectName())
    label.setAlignment(old_label.alignment())
    label.setEnabled(old_label.isEnabled())
    label.setVisible(not old_label.isHidden())
    label.setMinimumWidth(0)
    label.setMaximumWidth(maximum_width)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    parent_layout.removeWidget(old_label)
    parent_layout.insertWidget(index, label, stretch)
    old_label.hide()
    old_label.setParent(None)
    old_label.deleteLater()
    setattr(window, attribute_name, label)
    return label


def _set_compact_command_width(widget: QWidget, minimum_width: int) -> None:
    """Let a command group yield to the viewer while retaining a clickable floor."""

    widget.setMinimumWidth(minimum_width)
    policy = widget.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
    widget.setSizePolicy(policy)


def _natural_width(widget: QWidget) -> int:
    """Return the current font/style content width, including native widget chrome."""

    widget.ensurePolished()
    return max(widget.minimumSizeHint().width(), widget.sizeHint().width(), 1)


class _CommandRowMetricRefresh(QObject):
    """Own content-aware command floors for the lifetime of one composed window."""

    _METRIC_EVENTS = (QEvent.Type.FontChange, QEvent.Type.StyleChange)

    def __init__(
        self,
        window: Any,
        command_layout: QHBoxLayout,
        page_group: QWidget,
        layout_combo: QComboBox,
        gain_combo: QComboBox,
        clear_button: QAbstractButton,
        keep_button: QAbstractButton,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._command_layout = command_layout
        self._page_group = page_group
        self._layout_combo = layout_combo
        self._gain_combo = gain_combo
        self._clear_button = clear_button
        self._keep_button = keep_button
        self._groups = (layout_combo.parentWidget(), gain_combo.parentWidget())
        self._refreshing = False
        self._refresh_pending = False
        for widget in self._watched_widgets():
            widget.installEventFilter(self)
        self.refresh()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() in self._METRIC_EVENTS and not self._refresh_pending:
            # Event filters run before QWidget processes the metric-changing
            # event. Queue one receiver-owned refresh so size hints have been
            # invalidated first; Qt drops the call if this owner is destroyed.
            self._refresh_pending = True
            QMetaObject.invokeMethod(  # type: ignore[call-overload]
                self,
                "_refresh_after_metric_change",
                Qt.ConnectionType.QueuedConnection,
            )
        return super().eventFilter(watched, event)

    @Slot()
    def _refresh_after_metric_change(self) -> None:
        self._refresh_pending = False
        self.refresh()

    def refresh(self) -> None:
        """Recompute actionable floors from the current Qt font and style metrics."""

        if self._refreshing:
            return
        self._refreshing = True
        try:
            page_layout = self._page_group.layout()
            self._page_group.setMinimumWidth(0)
            page_policy = self._page_group.sizePolicy()
            page_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
            self._page_group.setSizePolicy(page_policy)
            if isinstance(page_layout, QHBoxLayout):
                page_layout.invalidate()
                # The two zero-minimum eliding labels still need one boundary
                # pixel each to remain inside the native host rectangle.
                self._page_group.setMinimumWidth(page_layout.minimumSize().width() + 2)
            self._page_group.updateGeometry()

            for button in (self._clear_button, self._keep_button):
                button.setMinimumWidth(0)
                policy = button.sizePolicy()
                policy.setHorizontalPolicy(QSizePolicy.Policy.Minimum)
                button.setSizePolicy(policy)
                button.setMinimumWidth(_natural_width(button))
                button.updateGeometry()

            for combo in (self._layout_combo, self._gain_combo):
                # Release legacy fixed reservations before asking Qt for the
                # widest item plus the current style's frame/drop-down chrome.
                combo.setMinimumWidth(0)
                combo.setMaximumWidth(_QT_WIDGET_SIZE_MAX)
                combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
                policy = combo.sizePolicy()
                policy.setHorizontalPolicy(QSizePolicy.Policy.MinimumExpanding)
                combo.setSizePolicy(policy)
                combo.setMinimumWidth(_natural_width(combo))
                combo.updateGeometry()

            for group in self._groups:
                if not isinstance(group, QWidget):
                    continue
                group_layout = group.layout()
                group.setMinimumWidth(0)
                policy = group.sizePolicy()
                policy.setHorizontalPolicy(QSizePolicy.Policy.MinimumExpanding)
                group.setSizePolicy(policy)
                if isinstance(group_layout, QHBoxLayout):
                    group_layout.invalidate()
                    group.setMinimumWidth(max(group_layout.minimumSize().width(), 1))
                group.updateGeometry()
            self._command_layout.invalidate()
            self._command_layout.activate()
        finally:
            self._refreshing = False

    def _watched_widgets(self) -> tuple[QWidget, ...]:
        widgets: list[QWidget] = []
        if isinstance(self._window, QWidget):
            widgets.append(self._window)
        widgets.extend(
            [
                self._page_group,
                self._layout_combo,
                self._gain_combo,
                self._clear_button,
                self._keep_button,
            ]
        )
        widgets.extend(group for group in self._groups if isinstance(group, QWidget))
        return tuple(widgets)


def _install_command_row_metric_refresh(
    window: Any,
    command_layout: QHBoxLayout,
    page_group: object,
    layout_combo: object,
    gain_combo: object,
    clear_button: object,
    keep_button: object,
) -> None:
    """Install or refresh the one content-floor owner for the composed command row."""

    existing = getattr(window, "_command_row_metric_refresh", None)
    if isinstance(existing, _CommandRowMetricRefresh):
        existing.refresh()
        return
    if not (
        isinstance(page_group, QWidget)
        and isinstance(layout_combo, QComboBox)
        and isinstance(gain_combo, QComboBox)
        and isinstance(clear_button, QAbstractButton)
        and isinstance(keep_button, QAbstractButton)
    ):
        return
    owner = _CommandRowMetricRefresh(
        window,
        command_layout,
        page_group,
        layout_combo,
        gain_combo,
        clear_button,
        keep_button,
    )
    window._command_row_metric_refresh = owner


def _polish_compact_command_row(window: Any, layout: QHBoxLayout) -> None:
    """Bound the composed Image command row without changing command ownership."""

    layout.setSpacing(TOKENS.spacing_sm)

    layout_selector = getattr(window, "layout_selector", None)
    layout_group = (
        layout_selector.parentWidget() if isinstance(layout_selector, QComboBox) else None
    )
    page_group = getattr(window, "comparison_page_group", None)
    page_layout = page_group.layout() if isinstance(page_group, QWidget) else None
    if isinstance(page_layout, QHBoxLayout):
        page_layout.setSpacing(TOKENS.spacing_xs)
        if isinstance(page_group, QWidget):
            page_group.setMinimumWidth(0)
        page_layout.invalidate()
    gain_group = window.findChild(QWidget, "DisplayGainControl")
    review = getattr(window, "review_selection_controller", None)
    count_label = getattr(review, "count_label", None)
    clear_button = getattr(review, "clear_button", None)
    keep_button = getattr(review, "keep_button", None)

    compact_groups = (
        (page_group, 0, 4),
        (count_label, _COMPACT_PICK_COUNT_WIDTH, 1),
    )
    for widget, minimum_width, stretch in compact_groups:
        if not isinstance(widget, QWidget):
            continue
        _set_compact_command_width(widget, minimum_width)
        index = layout.indexOf(widget)
        if index >= 0:
            layout.setStretch(index, stretch)

    gain_label = window.findChild(QLabel, "DisplayGainLabel")
    if gain_label is not None:
        full_name = "Display Gain"
        gain_label.setText("Gain")
        gain_label.setAccessibleName(full_name)
        gain_label.setToolTip(full_name)

    if isinstance(clear_button, QAbstractButton):
        clear_button.setText("Clear")
        clear_button.setAccessibleName("Clear Selection")
        clear_button.setToolTip(
            "Clear Selection: clear temporary Picks without changing Files Selected"
        )
    if isinstance(keep_button, QAbstractButton):
        keep_button.setText("Keep")
        keep_button.setAccessibleName("Keep Selection")
        keep_button.setToolTip(
            "Keep Selection: replace Files Selected with temporary Picks in original order"
        )

    gain_combo = window.findChild(QComboBox, "DisplayGainCombo")
    _install_command_row_metric_refresh(
        window,
        layout,
        page_group,
        layout_selector,
        gain_combo,
        clear_button,
        keep_button,
    )

    for widget, stretch in (
        (layout_group, 1),
        (gain_group, 1),
        (clear_button, 1),
        (keep_button, 1),
    ):
        if not isinstance(widget, QWidget):
            continue
        index = layout.indexOf(widget)
        if index >= 0:
            layout.setStretch(index, stretch)

    # Keep some ordinary trailing breathing room, while allowing command groups to
    # receive surplus width again on a wide/FHD desktop.
    if layout.count() > 0 and layout.itemAt(layout.count() - 1).spacerItem() is not None:
        layout.setStretch(layout.count() - 1, 1)


def _polish_analysis_export_controls(window: Any) -> None:
    """Polish Statistics/Difference export affordances without changing ownership."""

    controller = getattr(window, "analysis_export_controller", None)
    statistics = getattr(window, "comparison_analysis_panel", None)
    difference = getattr(window, "difference_panel", None)
    if controller is None or statistics is None or difference is None:
        return

    for group in (statistics.region_group, statistics.image_summary_group):
        if isinstance(group, QGroupBox):
            group.setStyleSheet("QGroupBox::title { font-weight: bold; }")

    statistics_group = statistics.statistics_group
    statistics_layout = statistics_group.layout()
    copy_button = getattr(controller, "statistics_copy_button", None)
    existing_header = getattr(controller, "statistics_header", None)
    if (
        isinstance(statistics_group, QGroupBox)
        and isinstance(statistics_layout, QVBoxLayout)
        and not isinstance(existing_header, QWidget)
    ):
        statistics_group.setTitle("")
        header = QWidget(statistics_group)
        header.setObjectName("channelStatisticsHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(TOKENS.spacing_sm)
        label = QLabel("Channel statistics", header)
        label.setObjectName("channelStatisticsHeading")
        _set_bold_label(label)
        header_layout.addWidget(label)
        if isinstance(copy_button, QToolButton):
            header_layout.addWidget(copy_button)
        header_layout.addStretch(1)
        statistics_layout.insertWidget(0, header)
        controller.statistics_heading_label = label
        controller.statistics_header = header

    command_style = _analysis_action_button_style()
    analysis_buttons = (
        getattr(controller, "statistics_copy_button", None),
        getattr(difference, "calculate", None),
        getattr(controller, "difference_metrics_export_button", None),
        getattr(controller, "difference_metrics_copy_button", None),
    )
    for button in analysis_buttons:
        if not isinstance(button, QAbstractButton):
            continue
        if isinstance(button, QToolButton):
            button.setAutoRaise(False)
        button.setProperty("etchedDisabledText", True)
        button.setStyleSheet(command_style)
        button.setFixedHeight(TOKENS.control_height)

    if isinstance(copy_button, QAbstractButton):
        copy_button.setFixedWidth(TOKENS.control_height + 2)
        copy_button.setIconSize(QSize(18, 18))
    difference_copy = getattr(controller, "difference_metrics_copy_button", None)
    if isinstance(difference_copy, QAbstractButton):
        difference_copy.setFixedWidth(TOKENS.control_height + 2)
        difference_copy.setIconSize(QSize(18, 18))
    difference_csv = getattr(controller, "difference_metrics_export_button", None)
    if isinstance(difference_csv, QAbstractButton):
        difference_csv.setMinimumWidth(46)
    calculate = getattr(difference, "calculate", None)
    if isinstance(calculate, QAbstractButton):
        calculate.setMinimumWidth(92)

    difference_heading = getattr(controller, "difference_metrics_label", None)
    if isinstance(difference_heading, QLabel):
        _set_bold_label(difference_heading)


def _replace_page_button(
    window: Any,
    attribute_name: str,
    icon_kind: str,
    accessible_name: str,
    callback: Any,
) -> QToolButton:
    old_button = getattr(window, attribute_name)
    replaced = not isinstance(old_button, QToolButton)
    if replaced:
        parent = old_button.parentWidget()
        parent_layout = parent.layout() if parent is not None else None
        if not isinstance(parent_layout, QHBoxLayout):
            raise RuntimeError("Comparison Page button must belong to the page command group")
        index = parent_layout.indexOf(old_button)
        if index < 0:
            raise RuntimeError("Comparison Page button is missing from its command layout")

        button = QToolButton(parent)
        button.setObjectName(old_button.objectName())
        button.setEnabled(old_button.isEnabled())
        button.setVisible(not old_button.isHidden())
        parent_layout.removeWidget(old_button)
        parent_layout.insertWidget(index, button)
        old_button.hide()
        old_button.setParent(None)
        old_button.deleteLater()
        setattr(window, attribute_name, button)
    else:
        button = old_button

    button.setIcon(toolbar_icon(icon_kind))
    button.setIconSize(window.main_toolbar.iconSize())
    button.setText(accessible_name.removesuffix(" Comparison Page"))
    button.setAccessibleName(accessible_name)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setFixedSize(TOKENS.control_height, TOKENS.control_height)
    shortcut = "Ctrl+Left" if icon_kind == "previous_page" else "Ctrl+Right"
    button.setToolTip(f"{accessible_name} ({shortcut})")
    button.setStatusTip(button.toolTip())
    if replaced:
        button.clicked.connect(callback)  # type: ignore[attr-defined]
    return button


def polish_presentation_controls(window: Any) -> None:
    """Polish the P3 presentation row without changing command or state ownership."""

    host = getattr(window, "presentation_controls", None)
    layout = getattr(window, "presentation_controls_layout", None)
    if not isinstance(host, QWidget) or not isinstance(layout, QHBoxLayout):
        return

    host.setAccessibleName("Image presentation controls")
    host.setStyleSheet(_presentation_controls_style())
    host.setMinimumHeight(TOKENS.control_height + 2 * TOKENS.spacing_xs)
    layout.setContentsMargins(
        TOKENS.spacing_sm,
        TOKENS.spacing_xs,
        TOKENS.spacing_sm,
        TOKENS.spacing_xs,
    )
    layout.setSpacing(TOKENS.spacing_md)

    layout_selector = getattr(window, "layout_selector", None)
    if isinstance(layout_selector, QComboBox):
        layout_selector.setAccessibleName("Layout")
        layout_selector.setFixedHeight(TOKENS.control_height)
        layout_selector.setMinimumWidth(118)

    gain_selector = window.findChild(QComboBox, "DisplayGainCombo")
    if gain_selector is not None:
        gain_selector.setAccessibleName("Display Gain")
        gain_selector.setFixedHeight(TOKENS.control_height)

    gain_group = window.findChild(QWidget, "DisplayGainControl")
    gain_layout = gain_group.layout() if gain_group is not None else None
    if isinstance(gain_layout, QHBoxLayout):
        gain_layout.setContentsMargins(0, 0, 0, 0)
        gain_layout.setSpacing(TOKENS.spacing_sm)

    _replace_page_button(
        window,
        "previous_comparison_page_button",
        "previous_page",
        "Previous Comparison Page",
        window.previous_comparison_page,
    )
    _replace_page_button(
        window,
        "next_comparison_page_button",
        "next_page",
        "Next Comparison Page",
        window.next_comparison_page,
    )
    _replace_page_label(window, "comparison_page_label", "Comparison Page", 1, 54)
    _replace_page_label(
        window,
        "comparison_page_range_label",
        "Comparison Page range",
        2,
        90,
    )

    _polish_analysis_export_controls(window)
    _polish_compact_command_row(window, layout)

    # The controls-state cache predates the widget replacement. Reset it once so
    # the new buttons receive the same endpoint state as actions and shortcuts.
    window._comparison_page_controls_state = None
    window._update_comparison_page_controls()
