from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QAbstractButton, QComboBox, QHBoxLayout, QSizePolicy, QWidget

_QT_WIDGET_SIZE_MAX = 16_777_215


def _natural_width(widget: QWidget) -> int:
    """Return the polished content width required by the current font/style."""

    widget.ensurePolished()
    return max(widget.minimumSizeHint().width(), widget.sizeHint().width(), 1)


def _set_compact_button(
    button: QAbstractButton,
    *,
    compact_text: str,
    accessible_name: str,
) -> None:
    """Keep a compact visible command while preserving an unclipped content floor."""

    button.setText(compact_text)
    button.setAccessibleName(accessible_name)
    button.setMinimumWidth(0)
    natural_width = _natural_width(button)
    button.setMinimumWidth(natural_width)
    policy = button.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Minimum)
    button.setSizePolicy(policy)
    button.updateGeometry()


def _set_compact_gain_combo(combo: QComboBox) -> None:
    """Size the short Gain selector from its real items and native combo chrome."""

    # install_display_gain_control() historically reserved 70 logical px with
    # setFixedWidth(). Release that fixed width before asking the current Qt style
    # for a content-derived hint. AdjustToContents accounts for the widest item as
    # well as the platform combo-box frame/drop-down subcontrol.
    combo.setMinimumWidth(0)
    combo.setMaximumWidth(_QT_WIDGET_SIZE_MAX)
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    natural_width = _natural_width(combo)
    combo.setMinimumWidth(natural_width)
    policy = combo.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Fixed)
    combo.setSizePolicy(policy)
    combo.updateGeometry()


def _set_gain_group_floor(group: QWidget) -> None:
    """Prevent the Gain host from becoming narrower than its label/combo layout."""

    layout = group.layout()
    group.setMinimumWidth(0)
    policy = group.sizePolicy()
    policy.setHorizontalPolicy(QSizePolicy.Policy.Minimum)
    group.setSizePolicy(policy)
    if isinstance(layout, QHBoxLayout):
        layout.invalidate()
        group.ensurePolished()
        group.setMinimumWidth(max(layout.minimumSize().width(), layout.sizeHint().width(), 1))
    group.updateGeometry()


def install_dpi_safe_command_row(window: Any) -> None:
    """Apply content-aware floors to compact Image commands after PR #68 hardening."""

    gain_combo = window.findChild(QComboBox, "DisplayGainCombo")
    gain_group = window.findChild(QWidget, "DisplayGainControl")
    review = getattr(window, "review_selection_controller", None)
    clear_button = getattr(review, "clear_button", None)
    keep_button = getattr(review, "keep_button", None)

    if isinstance(clear_button, QAbstractButton):
        _set_compact_button(
            clear_button,
            compact_text="Clear",
            accessible_name="Clear Selection",
        )
    if isinstance(keep_button, QAbstractButton):
        _set_compact_button(
            keep_button,
            compact_text="Keep",
            accessible_name="Keep Selection",
        )
    if isinstance(gain_combo, QComboBox):
        _set_compact_gain_combo(gain_combo)
    if isinstance(gain_group, QWidget):
        _set_gain_group_floor(gain_group)
