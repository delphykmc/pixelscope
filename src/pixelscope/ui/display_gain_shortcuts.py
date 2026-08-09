from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QComboBox, QWidget


def install_display_gain_shortcuts(
    presentation_scope: QWidget,
    control: QComboBox,
) -> tuple[QShortcut, QShortcut]:
    """Bind +/- commands to a discrete gain control inside the viewer surface.

    The binding is intentionally presentation-generic: P3-B supplies the RAW Gain
    combo, while P3-C can reuse the same command layer when the viewer surface is
    generalized to ordinary Gray/RGB/RGBA Display Gain.

    ``WidgetWithChildrenShortcut`` is deliberate. Display Gain owns +/- only while
    focus is inside the image-presentation subtree; sibling UI such as the Files
    tree keeps its native Qt key handling, including +/- expand/collapse.
    """

    control_alive = True

    increase = QShortcut(QKeySequence("+"), presentation_scope)
    decrease = QShortcut(QKeySequence("-"), presentation_scope)
    for shortcut in (increase, decrease):
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)

    def step(delta: int) -> None:
        if not control_alive or not control.isEnabled() or control.count() <= 0:
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

    control.destroyed.connect(control_destroyed)  # type: ignore[attr-defined]

    # Retain Python wrappers explicitly on the presentation owner in addition to
    # Qt parentage. P3-C can reuse this same command slot when the toolbar surface
    # is generalized from RAW Gain to Display Gain.
    setattr(presentation_scope, "_display_gain_shortcuts", (increase, decrease))
    return increase, decrease
