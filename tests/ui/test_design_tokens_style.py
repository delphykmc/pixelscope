from __future__ import annotations

from typing import Any, cast

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyle, QWidget, QWidgetItem

from pixelscope.ui.design_tokens import (
    EngineeringStyle,
    TOKENS,
    apply_engineering_palette,
)


def test_engineering_style_ignores_qwidgetitem_style_hint(qtbot: object) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    item = QWidgetItem(widget)
    style = EngineeringStyle("Fusion")

    value = cast(Any, style).styleHint(
        QStyle.StyleHint.SH_ItemView_ActivateItemOnSingleClick,
        None,
        item,
        None,
    )

    assert isinstance(value, int)


def test_engineering_palette_keeps_placeholder_text_readable(qtbot: object) -> None:
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    apply_engineering_palette(app)

    assert app.palette().color(QPalette.ColorRole.PlaceholderText) == QColor(
        TOKENS.text_secondary
    )
