from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from pixelscope.ui.design_tokens import TOKENS

SESSION_RESTORE_STEPS: tuple[str, ...] = (
    "Reading Session",
    "Restoring sources",
    "Restoring workspace",
    "Loading current page",
    "Restoring display",
    "Restoring analysis",
    "Rebuilding Difference",
    "Finalizing workspace",
)


class SessionRestoreOverlay(QFrame):
    """MainWindow-owned soft-modal progress UI for Session reconstruction."""

    def __init__(
        self,
        parent: QWidget,
        steps: Sequence[str] = SESSION_RESTORE_STEPS,
    ) -> None:
        super().__init__(parent)
        self._steps = tuple(steps)
        self.setObjectName("sessionRestoreOverlay")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation, True)
        self.setStyleSheet(self._style())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.card = QFrame(self)
        self.card.setObjectName("sessionRestoreCard")
        self.card.setMinimumWidth(440)
        self.card.setMaximumWidth(560)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(TOKENS.spacing_md)

        title = QLabel("Restoring Session", self.card)
        title.setObjectName("sessionRestoreTitle")
        card_layout.addWidget(title)

        self.progress_bar = QProgressBar(self.card)
        self.progress_bar.setObjectName("sessionRestoreProgress")
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setTextVisible(False)
        card_layout.addWidget(self.progress_bar)

        self.step_label = QLabel(self.card)
        self.step_label.setObjectName("sessionRestoreStep")
        card_layout.addWidget(self.step_label)

        self.detail_label = QLabel(self.card)
        self.detail_label.setObjectName("sessionRestoreDetail")
        self.detail_label.setWordWrap(True)
        card_layout.addWidget(self.detail_label)

        self.step_rows: list[QLabel] = []
        for step in self._steps:
            row = QLabel(step, self.card)
            row.setObjectName("sessionRestoreStepRow")
            self.step_rows.append(row)
            card_layout.addWidget(row)

        outer.addWidget(self.card)
        parent.installEventFilter(self)
        self.hide()
        self.update_progress(1, 0.0, "Preparing Session restore")

    @property
    def step_count(self) -> int:
        return len(self._steps)

    def begin(self, detail: str = "Reading and validating Session") -> None:
        self._sync_geometry()
        self.update_progress(1, 0.0, detail)
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def update_progress(self, step: int, fraction: float, detail: str) -> None:
        if not self._steps:
            return
        step = max(1, min(step, len(self._steps)))
        fraction = max(0.0, min(float(fraction), 1.0))
        overall = ((step - 1) + fraction) / len(self._steps)
        self.progress_bar.setValue(round(overall * self.progress_bar.maximum()))
        self.step_label.setText(
            f"Step {step} of {len(self._steps)} · {self._steps[step - 1]}"
        )
        self.detail_label.setText(detail)
        self._update_rows(step)

    def finish(self, detail: str = "Session restored") -> None:
        if self._steps:
            self.update_progress(len(self._steps), 1.0, detail)
        self.hide()

    def abort(self) -> None:
        self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parentWidget() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
        ):
            self._sync_geometry()
            if self.isVisible():
                self.raise_()
        return super().eventFilter(watched, event)

    def event(self, event: QEvent) -> bool:
        if self.isVisible() and event.type() in (
            QEvent.Type.ShortcutOverride,
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
            QEvent.Type.Wheel,
        ):
            event.accept()
            return True
        return super().event(event)

    def _sync_geometry(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

    def _update_rows(self, current_step: int) -> None:
        rows = zip(self.step_rows, self._steps, strict=True)
        for index, (row, title) in enumerate(rows, start=1):
            if index < current_step:
                state = "done"
                prefix = "✓"
            elif index == current_step:
                state = "current"
                prefix = "●"
            else:
                state = "pending"
                prefix = "○"
            row.setProperty("restoreState", state)
            row.setText(f"{prefix}  {title}")
            row.style().unpolish(row)
            row.style().polish(row)

    @staticmethod
    def _style() -> str:
        return (
            "QFrame#sessionRestoreOverlay { background: rgba(10, 12, 15, 205); }"
            f"QFrame#sessionRestoreCard {{ background: {TOKENS.panel_background}; "
            f"border: 1px solid {TOKENS.border}; border-radius: 6px; }}"
            f"QLabel#sessionRestoreTitle {{ color: {TOKENS.text_primary}; "
            "font-size: 18px; font-weight: 700; }"
            f"QLabel#sessionRestoreStep {{ color: {TOKENS.text_primary}; "
            "font-weight: 600; }"
            f"QLabel#sessionRestoreDetail {{ color: {TOKENS.text_secondary}; }}"
            f"QLabel#sessionRestoreStepRow {{ color: {TOKENS.text_disabled}; "
            "padding: 1px 0; }"
            "QLabel#sessionRestoreStepRow[restoreState=\"done\"] { "
            f"color: {TOKENS.text_secondary}; }}"
            "QLabel#sessionRestoreStepRow[restoreState=\"current\"] { "
            f"color: {TOKENS.accent}; font-weight: 700; }}"
            "QProgressBar#sessionRestoreProgress { "
            f"background: {TOKENS.workspace_background}; "
            f"border: 1px solid {TOKENS.border}; border-radius: 3px; "
            "min-height: 8px; max-height: 8px; }"
            "QProgressBar#sessionRestoreProgress::chunk { "
            f"background: {TOKENS.accent}; border-radius: 2px; }}"
        )
