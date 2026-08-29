from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont
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

_COMPACT_LAYOUT_GROUP_WIDTH = 100
_COMPACT_PAGE_GROUP_WIDTH = 280
_COMPACT_GAIN_GROUP_WIDTH = 90
_COMPACT_PICK_COUNT_WIDTH = 50
_COMPACT_CURATION_ACTION_WIDTH = 56


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


def _set_compact_command_width(widget: QWidget, minimum_width: int) -> None:
    """Let a command group yield to the viewer while retaining a clickable floor."""

    widget.setMinimumWidth(minimum_width)
    policy = widget.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
    widget.setSizePolicy(policy)


def _polish_compact_command_row(window: Any, layout: QHBoxLayout) -> None:
    """Bound the composed Image command row without changing command ownership."""

    layout.setSpacing(TOKENS.spacing_md)

    layout_selector = getattr(window, "layout_selector", None)
    layout_group = (
        layout_selector.parentWidget() if isinstance(layout_selector, QComboBox) else None
    )
    page_group = getattr(window, "comparison_page_group", None)
    gain_group = window.findChild(QWidget, "DisplayGainControl")
    review = getattr(window, "review_selection_controller", None)
    count_label = getattr(review, "count_label", None)
    clear_button = getattr(review, "clear_button", None)
    keep_button = getattr(review, "keep_button", None)

    compact_groups = (
        (layout_group, _COMPACT_LAYOUT_GROUP_WIDTH, 1),
        (page_group, _COMPACT_PAGE_GROUP_WIDTH, 4),
        (gain_group, _COMPACT_GAIN_GROUP_WIDTH, 1),
        (count_label, _COMPACT_PICK_COUNT_WIDTH, 1),
        (clear_button, _COMPACT_CURATION_ACTION_WIDTH, 1),
        (keep_button, _COMPACT_CURATION_ACTION_WIDTH, 1),
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
        clear_button.setAccessibleName("Clear Selection")
        clear_button.setToolTip(
            "Clear Selection: clear temporary Picks without changing Files Selected"
        )
    if isinstance(keep_button, QAbstractButton):
        keep_button.setAccessibleName("Keep Selection")
        keep_button.setToolTip(
            "Keep Selection: replace Files Selected with temporary Picks in original order"
        )

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
        TOKENS.spacing_md,
        TOKENS.spacing_xs,
        TOKENS.spacing_md,
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

    _polish_analysis_export_controls(window)
    _polish_compact_command_row(window, layout)

    # The controls-state cache predates the widget replacement. Reset it once so
    # the new buttons receive the same endpoint state as actions and shortcuts.
    window._comparison_page_controls_state = None
    window._update_comparison_page_controls()
