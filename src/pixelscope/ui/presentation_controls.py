from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QToolButton, QWidget

from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.toolbar_icons import toolbar_icon


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

    # The controls-state cache predates the widget replacement. Reset it once so
    # the new buttons receive the same endpoint state as actions and shortcuts.
    window._comparison_page_controls_state = None
    window._update_comparison_page_controls()
