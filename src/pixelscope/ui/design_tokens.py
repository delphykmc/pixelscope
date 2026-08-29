from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QProxyStyle,
    QStyle,
    QStyleHintReturn,
    QStyleOption,
    QWidget,
)


@dataclass(frozen=True)
class DesignTokens:
    spacing_xs: int = 3
    spacing_sm: int = 6
    spacing_md: int = 10
    spacing_lg: int = 16
    control_height: int = 28
    icon_size: int = 16
    panel_background: str = "#25282d"
    workspace_background: str = "#141619"
    title_background: str = "#1e2023"
    raised_background: str = "#30343a"
    border: str = "#444950"
    text_primary: str = "#e7e9ec"
    text_secondary: str = "#aeb4bc"
    text_disabled: str = "#737980"
    accent: str = "#4aa3df"
    selection: str = "#ffd84d"
    warning: str = "#e0a84f"
    error: str = "#e06969"


TOKENS = DesignTokens()
WORKSPACE_CHROME_HEIGHT = TOKENS.control_height + 2 * TOKENS.spacing_xs


class EngineeringStyle(QProxyStyle):
    """Keep most disabled text flat while allowing explicit Windows-style etching."""

    def styleHint(
        self,
        hint: QStyle.StyleHint,
        option: QStyleOption | None = None,
        widget: QWidget | None = None,
        return_data: QStyleHintReturn | None = None,
    ) -> int:
        style_widget = _style_hint_widget(widget)
        if hint == QStyle.StyleHint.SH_EtchDisabledText:
            if style_widget is not None and bool(style_widget.property("etchedDisabledText")):
                return 1
            return 0
        return super().styleHint(hint, option, style_widget, return_data)


def _style_hint_widget(widget: object | None) -> QWidget | None:
    """Return only live QWidget callbacks; never dereference layout-item wrappers."""

    if isinstance(widget, QWidget):
        return widget
    return None


def apply_engineering_palette(app: QApplication) -> None:
    """Apply a compact neutral palette without globally restyling widget geometry."""

    app.setStyle(EngineeringStyle("Fusion"))
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(TOKENS.panel_background))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TOKENS.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(TOKENS.workspace_background))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(TOKENS.raised_background))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(TOKENS.raised_background))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TOKENS.text_primary))
    palette.setColor(QPalette.ColorRole.Text, QColor(TOKENS.text_primary))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TOKENS.text_secondary))
    palette.setColor(QPalette.ColorRole.Button, QColor(TOKENS.raised_background))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TOKENS.text_primary))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor(TOKENS.accent))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(TOKENS.accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#101316"))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            role,
            QColor(TOKENS.text_disabled),
        )
    app.setPalette(palette)


def menu_style() -> str:
    """Make unavailable menu commands visually distinct while retaining their icons."""

    return (
        f"QMenu::item:disabled {{ color: {TOKENS.text_disabled}; }}"
        "QMenu::item:disabled:selected { background: transparent; }"
    )


def panel_heading_style() -> str:
    return (
        f"QLabel {{ background: {TOKENS.title_background}; color: {TOKENS.text_primary}; "
        f"font-weight: 600; padding: 0 {TOKENS.spacing_sm}px; "
        f"border-bottom: 1px solid {TOKENS.border}; }}"
    )


def tile_style(active: bool) -> str:
    """Render Active and curation-selected as independent tile-wide states."""

    border = TOKENS.accent if active else TOKENS.border
    selected_border = (
        f"border: 3px solid {TOKENS.selection}; border-left: 5px solid {TOKENS.accent};"
        if active
        else f"border: 3px solid {TOKENS.selection};"
    )
    return (
        f"ImageViewer {{ background: {TOKENS.workspace_background}; "
        f"border: 2px solid {border}; }}"
        f'ImageViewer[reviewPicked="true"] {{ background: {TOKENS.workspace_background}; '
        f"{selected_border} }}"
    )


def tile_header_style() -> str:
    return (
        f"QWidget#tileHeader {{ background: {TOKENS.panel_background}; "
        f"border-bottom: 1px solid {TOKENS.border}; }}"
        f"QLabel#slotBadge {{ background: {TOKENS.raised_background}; "
        f"color: {TOKENS.text_primary}; padding: 1px 5px; font-weight: 700; }}"
        f"QLabel#tileMeta {{ color: {TOKENS.text_secondary}; }}"
        "QToolButton#reviewPick { background: transparent; border: 1px solid transparent; "
        f"border-radius: 2px; padding: 1px {TOKENS.spacing_sm}px; }}"
        f"QToolButton#reviewPick:hover {{ background: {TOKENS.raised_background}; "
        f"border-color: {TOKENS.border}; }}"
        f"QToolButton#reviewPick:checked {{ background: {TOKENS.workspace_background}; "
        f"color: {TOKENS.selection}; border-color: {TOKENS.selection}; font-weight: 700; }}"
        f"QToolButton#reviewPick:pressed {{ background: {TOKENS.workspace_background}; "
        f"border-color: {TOKENS.selection}; }}"
        "QToolButton#primaryFlag { background: transparent; border: 1px solid transparent; }"
        f"QToolButton#primaryFlag:hover {{ background: {TOKENS.raised_background}; "
        f"border-color: {TOKENS.border}; }}"
        f"QToolButton#primaryFlag:checked {{ background: {TOKENS.raised_background}; "
        f"border-color: {TOKENS.accent}; }}"
        f"QToolButton#primaryFlag:pressed {{ background: {TOKENS.workspace_background}; "
        f"border-color: {TOKENS.accent}; }}"
    )


def empty_state_style() -> str:
    return (
        f"QWidget#emptyState {{ background: {TOKENS.workspace_background}; }}"
        f"QLabel#emptyTitle {{ color: {TOKENS.text_primary}; font-size: 20px; "
        "font-weight: 600; }"
        f"QLabel#emptyHint {{ color: {TOKENS.text_secondary}; }}"
    )


def toolbar_style() -> str:
    return (
        f"QToolBar {{ spacing: {TOKENS.spacing_xs}px; }}"
        "QToolButton { border: 1px solid transparent; border-radius: 2px; "
        f"padding: {TOKENS.spacing_xs}px {TOKENS.spacing_sm}px; }}"
        f"QToolButton:hover {{ background: {TOKENS.raised_background}; "
        f"border-color: {TOKENS.border}; }}"
        f"QToolButton:pressed {{ background: {TOKENS.workspace_background}; "
        f"border-color: {TOKENS.accent}; }}"
        f"QToolButton:checked {{ background: {TOKENS.raised_background}; "
        f"border-color: {TOKENS.accent}; color: {TOKENS.text_primary}; }}"
        "QToolButton:disabled { background: transparent; border-color: transparent; "
        f"color: {TOKENS.text_disabled}; }}"
    )


def dock_title_button_style() -> str:
    return (
        "QToolButton { background: transparent; border: 1px solid transparent; }"
        f"QToolButton:hover {{ background: {TOKENS.raised_background}; "
        f"border-color: {TOKENS.border}; }}"
        f"QToolButton:pressed {{ background: {TOKENS.workspace_background}; "
        f"border-color: {TOKENS.accent}; }}"
    )


def primary_button_style() -> str:
    return (
        f"QPushButton#primaryAction {{ background: {TOKENS.raised_background}; "
        f"color: {TOKENS.text_primary}; border: 1px solid {TOKENS.accent}; "
        f"padding: {TOKENS.spacing_xs}px {TOKENS.spacing_md}px; font-weight: 600; }}"
        f"QPushButton#primaryAction:hover {{ background: {TOKENS.panel_background}; }}"
        f"QPushButton:disabled {{ background: {TOKENS.raised_background}; "
        f"border-color: {TOKENS.border}; color: {TOKENS.text_disabled}; }}"
    )


def channel_button_style(color: str) -> str:
    return (
        f"QToolButton {{ color: {TOKENS.text_secondary}; "
        f"background: {TOKENS.workspace_background}; border: 1px solid {TOKENS.border}; }}"
        f"QToolButton:checked {{ color: {color}; background: {TOKENS.raised_background}; "
        f"border: 1px solid {color}; font-weight: 700; }}"
    )