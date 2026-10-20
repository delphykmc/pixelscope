"""Stable, one-line hover readouts for the independent IQA Analysis Window.

The caller reserves a width from the longest expected text once per result,
then changes only the displayed value as the pointer moves. The full value
remains available through the tooltip and accessibility name.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


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
        shown = self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, width
        )
        super().setText(shown)
        self.setToolTip(self._full_text)
        self.setAccessibleName(self._full_text)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange and hasattr(self, "_reserved_samples"):
            self.reserve_width(self._reserved_samples)
