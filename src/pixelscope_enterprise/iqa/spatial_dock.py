"""Bottom-dock cards for provisional GRID-DERIVED spatial ROI suggestions.

Presentation only. All source crops use the SAME integer-pixel ROI in A/B.
Pixmap scaling is for thumbnail presentation, never model measurement or ROI
geometry. This widget owns neither IQA jobs nor a host MainWindow dock manager.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.ui.design_tokens import TOKENS
from pixelscope_enterprise.iqa.spatial_candidates import SpatialCandidate

_THUMB_WIDTH = 154
_THUMB_HEIGHT = 88


class SpatialCandidatesPanel(QWidget):
    """Three compact A | B stitch previews and an exact-three-choice stride."""

    candidate_clicked = Signal(int)
    stride_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("enterpriseIqaSpatialCandidatesPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(QLabel("SPATIAL HOTSPOTS · GRID-DERIVED (NOT OFFICIAL)", self), 1)
        header.addWidget(QLabel("Scan", self))
        self.stride_selector = QComboBox(self)
        self.stride_selector.setObjectName("enterpriseIqaSpatialStride")
        for label, stride in (
            ("Detailed · 64 px", 64),
            ("Standard · 128 px", 128),
            ("Fast · 256 px", 256),
        ):
            self.stride_selector.addItem(label, stride)
        self.stride_selector.setCurrentIndex(1)
        self.stride_selector.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._stride_selected
        )
        header.addWidget(self.stride_selector)
        layout.addLayout(header)

        self.status_label = QLabel("Choose an Attribute to inspect local differences.", self)
        self.status_label.setObjectName("enterpriseIqaSpatialStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.progress = QProgressBar(self)
        self.progress.setObjectName("enterpriseIqaSpatialBusy")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(5)
        self.progress.hide()
        layout.addWidget(self.progress)

        cards = QHBoxLayout()
        cards.setSpacing(8)
        self.buttons: list[QPushButton] = []
        self.previews: list[tuple[QLabel, QLabel]] = []
        self.titles: list[QLabel] = []
        self.details: list[QLabel] = []
        for index in range(3):
            card = QPushButton(self)
            card.setObjectName(f"enterpriseIqaSpatialCard{index + 1}")
            card.setCheckable(True)
            card.setEnabled(False)
            card.setMinimumWidth(160)
            card.setMinimumHeight(142)
            column = QVBoxLayout(card)
            column.setContentsMargins(7, 5, 7, 5)
            column.setSpacing(3)
            card_title = QLabel(f"#{index + 1}  —", card)
            card_title.setObjectName("enterpriseIqaSpatialCardTitle")
            column.addWidget(card_title)
            row = QHBoxLayout()
            row.setSpacing(2)
            left = self._image_label(card, "A · source unavailable")
            seam = QFrame(card)
            seam.setFixedWidth(2)
            seam.setStyleSheet(f"background-color: {TOKENS.accent};")
            right = self._image_label(card, "B · source unavailable")
            row.addWidget(left, 1)
            row.addWidget(seam)
            row.addWidget(right, 1)
            column.addLayout(row)
            detail = QLabel("—", card)
            detail.setObjectName("enterpriseIqaSpatialCardDetails")
            column.addWidget(detail)
            # Labels are visual content; mouse clicks reach the actual button.
            for child in (card_title, left, seam, right, detail):
                if isinstance(child, QWidget):
                    child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            card.clicked.connect(  # type: ignore[attr-defined]
                lambda _checked=False, i=index: self.candidate_clicked.emit(i)
            )
            cards.addWidget(card, 1)
            self.buttons.append(card)
            self.previews.append((left, right))
            self.titles.append(card_title)
            self.details.append(detail)
        layout.addLayout(cards, 1)
        self.setStyleSheet(
            f"QPushButton#enterpriseIqaSpatialCard1, QPushButton#enterpriseIqaSpatialCard2, "
            f"QPushButton#enterpriseIqaSpatialCard3 {{ background: {TOKENS.raised_background}; "
            f"border: 1px solid {TOKENS.border}; border-radius: 7px; text-align: left; }}"
            f"QPushButton:checked {{ border: 2px solid {TOKENS.accent}; }}"
            f"QPushButton:hover {{ border-color: {TOKENS.accent}; }}"
            f"QLabel#enterpriseIqaSpatialStatus {{ color: {TOKENS.text_secondary}; }}"
            f"QLabel#enterpriseIqaSpatialCardDetails {{ color: {TOKENS.text_secondary}; }}"
        )

    @staticmethod
    def _image_label(parent: QWidget, text: str) -> QLabel:
        label = QLabel(text, parent)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumSize(20, _THUMB_HEIGHT)
        label.setMaximumHeight(_THUMB_HEIGHT)
        label.setStyleSheet(f"background-color: {TOKENS.workspace_background};")
        return label

    def _stride_selected(self, _index: int) -> None:
        stride = self.stride_selector.currentData()
        if isinstance(stride, int):
            self.stride_changed.emit(stride)

    @staticmethod
    def _crop(source: QPixmap | None, candidate: SpatialCandidate) -> QPixmap | None:
        """Copy no more than the requested source ROI, not the entire 4K frame."""

        if source is None or source.isNull():
            return None
        rect = QRect(*candidate.roi)
        if not source.rect().contains(rect):
            return None
        crop = source.copy(rect)
        return crop.scaled(
            _THUMB_WIDTH,
            _THUMB_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def set_busy(self, message: str) -> None:
        self.status_label.setText(message)
        self.progress.show()
        self.clear_cards()

    def clear_cards(self) -> None:
        for i, button in enumerate(self.buttons):
            button.setEnabled(False)
            button.setChecked(False)
            self.titles[i].setText(f"#{i + 1}  —")
            self.details[i].setText("—")
            for label, source in zip(self.previews[i], ("A", "B"), strict=True):
                label.clear()
                label.setText(f"{source} · unavailable")

    def populate(
        self,
        candidates: Sequence[SpatialCandidate],
        pixmaps: tuple[QPixmap | None, QPixmap | None],
        unit: str,
    ) -> None:
        self.clear_cards()
        self.progress.hide()
        if not candidates:
            self.status_label.setText("No qualifying GRID-DERIVED hotspot for this Attribute.")
            return
        self.status_label.setText(
            "Provisional local suggestions · source-aligned A | B crops · "
            "click to focus all three viewers."
        )
        for i, candidate in enumerate(candidates[:3]):
            self.buttons[i].setEnabled(True)
            self.titles[i].setText(
                f"#{candidate.rank}  ({candidate.x}, {candidate.y})  "
                f"{candidate.width}×{candidate.height} px"
            )
            self.details[i].setText(
                f"GRID mean {candidate.mean:+.3f} {unit}  ·  "
                f"valid {candidate.valid_coverage:.0%}"
                + (" · exploratory" if candidate.mode == "exploratory_abs" else "")
            )
            for source, label, marker in zip(pixmaps, self.previews[i], ("A", "B"), strict=True):
                crop = self._crop(source, candidate)
                label.clear()
                if crop is None:
                    label.setText(f"{marker} · source unavailable")
                else:
                    label.setPixmap(crop)

    def mark_selected(self, index: int | None) -> None:
        for i, button in enumerate(self.buttons):
            button.setChecked(i == index and button.isEnabled())
