"""Stable, one-line hover readouts for the independent IQA Analysis Window.

The caller reserves a width from the longest expected text once per result,
then changes only the displayed value as the pointer moves. The full value
remains available through the tooltip and accessibility name.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QStatusBar, QWidget


class ReservedHoverReadout(QLabel):
    """Fixed-width, right-elided hover label with lossless logical text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("—", parent)
        self._full_text = "—"
        self._reserved_samples: tuple[str, ...] = ("—",)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.reserve_width(self._reserved_samples)

    @property
    def full_text(self) -> str:
        return self._full_text

    def reserve_width(self, candidates: tuple[str, ...]) -> None:
        """Set the width for a result; hover updates must not resize the label."""

        if not candidates:
            raise ValueError("a hover readout requires at least one width candidate")
        self._reserved_samples = candidates
        metrics = self.fontMetrics()
        width = max(metrics.horizontalAdvance(text) for text in candidates)
        self.setFixedWidth(width + 2 * self.margin())
        self._refresh_text()

    def set_readout(self, text: str) -> None:
        self._full_text = text
        self._refresh_text()

    def _refresh_text(self) -> None:
        width = max(0, self.contentsRect().width() - 2 * self.margin())
        shown = self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, width)
        super().setText(shown)
        self.setToolTip(self._full_text)
        self.setAccessibleName(self._full_text)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange and hasattr(self, "_reserved_samples"):
            self.reserve_width(self._reserved_samples)


class ReservedHoverPair:
    """Two independent permanent readouts, leaving status messages untouched.

    The integration caller supplies the final position/RGB/map strings and
    widest expected candidates for each Result. This helper owns no scientific
    formatting, pixel lookup, or message priority decisions.
    """

    def __init__(self, status_bar: QStatusBar) -> None:
        self.position = ReservedHoverReadout(status_bar)
        self.position.setObjectName("enterpriseIqaHoverPosition")
        self.values = ReservedHoverReadout(status_bar)
        self.values.setObjectName("enterpriseIqaHoverValues")
        status_bar.addPermanentWidget(self.position)
        status_bar.addPermanentWidget(self.values)

    def reserve_for_result(
        self, position_candidates: tuple[str, ...], value_candidates: tuple[str, ...]
    ) -> None:
        """Change geometry at the result boundary, not for each hovered pixel."""

        self.position.reserve_width(position_candidates)
        self.values.reserve_width(value_candidates)
        self.clear()

    def update(self, position: str, values: str) -> None:
        self.position.set_readout(position)
        self.values.set_readout(values)

    def clear(self) -> None:
        self.update("—", "—")
