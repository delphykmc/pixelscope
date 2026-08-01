from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


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
    raised_background: str = "#30343a"
    border: str = "#444950"
    text_primary: str = "#e7e9ec"
    text_secondary: str = "#aeb4bc"
    accent: str = "#4aa3df"
    warning: str = "#e0a84f"
    error: str = "#e06969"


TOKENS = DesignTokens()


def apply_engineering_palette(app: QApplication) -> None:
    """Apply a compact neutral palette without globally restyling widget geometry."""

    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(TOKENS.panel_background))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TOKENS.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(TOKENS.workspace_background))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(TOKENS.raised_background))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(TOKENS.raised_background))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TOKENS.text_primary))
    palette.setColor(QPalette.ColorRole.Text, QColor(TOKENS.text_primary))
    palette.setColor(QPalette.ColorRole.Button, QColor(TOKENS.raised_background))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TOKENS.text_primary))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, QColor(TOKENS.accent))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(TOKENS.accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#101316"))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor("#737980"),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor("#737980"),
    )
    app.setPalette(palette)


def panel_heading_style() -> str:
    return (
        f"QLabel {{ color: {TOKENS.text_primary}; font-weight: 600; "
        f"padding: {TOKENS.spacing_sm}px; }}"
    )


def tile_style(active: bool) -> str:
    border = TOKENS.accent if active else TOKENS.border
    return (
        f"ImageViewer {{ background: {TOKENS.workspace_background}; "
        f"border: 2px solid {border}; }}"
    )


def tile_header_style() -> str:
    return (
        f"QWidget#tileHeader {{ background: {TOKENS.panel_background}; "
        f"border-bottom: 1px solid {TOKENS.border}; }}"
        f"QLabel#slotBadge {{ background: {TOKENS.raised_background}; "
        f"color: {TOKENS.text_primary}; padding: 1px 5px; font-weight: 700; }}"
        f"QLabel#tileMeta {{ color: {TOKENS.text_secondary}; }}"
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
        f"QToolButton:checked {{ background: {TOKENS.raised_background}; "
        f"border: 1px solid {TOKENS.accent}; color: {TOKENS.text_primary}; }}"
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
        f"border-color: {TOKENS.border}; color: #737980; }}"
    )


def channel_button_style(color: str) -> str:
    return (
        f"QToolButton {{ color: {TOKENS.text_secondary}; "
        f"background: {TOKENS.workspace_background}; border: 1px solid {TOKENS.border}; }}"
        f"QToolButton:checked {{ color: {color}; background: {TOKENS.raised_background}; "
        f"border: 1px solid {color}; font-weight: 700; }}"
    )
