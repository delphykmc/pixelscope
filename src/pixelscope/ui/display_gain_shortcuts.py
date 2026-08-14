from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QComboBox, QWidget


def install_display_gain_shortcuts(
    presentation_scope: QWidget,
    control: QComboBox,
) -> tuple[QShortcut, QShortcut]:
    """Bind +/- commands to the discrete Display Gain control inside viewer UI.

    ``WidgetWithChildrenShortcut`` is deliberate. Display Gain owns +/- only while
    focus is inside the image-presentation subtree; sibling UI such as the Files
    tree keeps its native Qt key handling, including +/- expand/collapse.
    """

    presentation_owner: Any = presentation_scope
    existing = getattr(presentation_owner, "_display_gain_shortcuts", None)
    existing_control = getattr(presentation_owner, "_display_gain_shortcut_control", None)
    if (
        existing_control is control
        and isinstance(existing, tuple)
        and len(existing) == 2
        and all(isinstance(shortcut, QShortcut) for shortcut in existing)
    ):
        return existing

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
        # Do not touch shortcut wrappers here: during parent teardown Qt may
        # already have deleted them before the sibling toolbar control emits
        # destroyed. The Python guard is sufficient to prevent later control use.
        control_alive = False

    control.destroyed.connect(control_destroyed)  # type: ignore[attr-defined]

    # Retain Python wrappers explicitly on the presentation owner in addition to
    # Qt parentage so the command lifetime follows the viewer presentation scope.
    # QWidget intentionally has no static declaration for these private Python-only
    # lifetime anchors, so keep the dynamic boundary local and explicit.
    presentation_owner._display_gain_shortcuts = increase, decrease
    presentation_owner._display_gain_shortcut_control = control
    return increase, decrease
