from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QComboBox, QWidget


def install_display_gain_shortcuts(
    window: QWidget,
    control: QComboBox,
) -> tuple[QShortcut, QShortcut]:
    """Bind window-level +/- commands to a discrete display-gain control.

    The binding is intentionally presentation-generic: P3-B supplies the RAW Gain
    combo, while P3-C can reuse the same command layer when the viewer surface is
    generalized to ordinary Gray/RGB/RGBA Display Gain.
    """

    control_alive = True

    increase = QShortcut(QKeySequence("+"), window)
    decrease = QShortcut(QKeySequence("-"), window)
    for shortcut in (increase, decrease):
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)

    def step(delta: int) -> None:
        if not control_alive or not control.isEnabled():
            return
        current = control.currentIndex()
        target = min(max(current + delta, 0), control.count() - 1)
        if target != current:
            control.setCurrentIndex(target)

    increase.activated.connect(lambda: step(1))  # type: ignore[attr-defined]
    decrease.activated.connect(lambda: step(-1))  # type: ignore[attr-defined]

    def control_destroyed(*_args: Any) -> None:
        nonlocal control_alive
        control_alive = False
        increase.setEnabled(False)
        decrease.setEnabled(False)

    control.destroyed.connect(control_destroyed)

    # Keep the Python wrappers explicitly owned by the MainWindow as well as by
    # Qt parentage. Future Display Gain controls can reuse this same command slot.
    setattr(window, "_display_gain_shortcuts", (increase, decrease))
    return increase, decrease
