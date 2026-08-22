from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QStyle, QWidget, QWidgetItem

from pixelscope.ui.design_tokens import EngineeringStyle


def test_engineering_style_normalizes_qwidgetitem_style_hint(qtbot: object) -> None:
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
