"""Remove W05/W06 duplicate toolbar UI without deleting their state owners.

The same actions and typed controllers remain available from established
File/View/Difference paths and in tests. Qt-widget actions are hidden rather
than destroyed to preserve QObject lifetime and runtime compatibility.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QToolBar, QWidget


def remove_redundant_toolbar_controls(window: Any) -> None:
    toolbar = getattr(window, "main_toolbar", None)
    if not isinstance(toolbar, QToolBar):
        return
    # W06 reuses the original File QAction (also installed in File menu).
    open_action = getattr(window, "action_map", {}).get("Open Images...")
    if open_action is not None and open_action in toolbar.actions():
        actions = toolbar.actions()
        index = actions.index(open_action)
        toolbar.removeAction(open_action)
        open_action.setIcon(QIcon())  # File menu is uniformly text-first.
        if index < len(toolbar.actions()) and toolbar.actions()[index].isSeparator():
            toolbar.actions()[index].setVisible(False)

    for name in ("workspacePresetControl", "comparisonPresetControl"):
        actions = toolbar.actions()
        for index, action in enumerate(actions):
            widget = toolbar.widgetForAction(action)
            if not isinstance(widget, QWidget) or widget.objectName() != name:
                continue
            action.setVisible(False)
            if index and actions[index - 1].isSeparator():
                actions[index - 1].setVisible(False)
            if index + 1 < len(actions) and actions[index + 1].isSeparator():
                actions[index + 1].setVisible(False)
            break
