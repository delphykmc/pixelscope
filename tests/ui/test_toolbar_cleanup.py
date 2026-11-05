"""UX contract: W05/W06 duplicate toolbar controls are not exposed."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow


def test_toolbar_uses_existing_file_view_and_difference_commands(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    window.show()
    toolbar = window.main_toolbar
    open_action = window.action_map["Open Images..."]
    assert open_action not in toolbar.actions()
    assert open_action in window._menu_map["File"].actions()
    assert window.findChild(QWidget, "workspacePresetControl") is not None
    assert window.findChild(QWidget, "comparisonPresetControl") is not None
    for name in ("workspacePresetControl", "comparisonPresetControl"):
        action = next(
            action
            for action in toolbar.actions()
            if (widget := toolbar.widgetForAction(action)) is not None
            and widget.objectName() == name
        )
        assert not action.isVisible(), name
    window.close()
