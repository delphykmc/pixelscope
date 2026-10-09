"""Responsive source-aligned A|B stitched ROI evidence in the IQA bottom dock.

One canvas draws both patches from bounded 512px source crops; resizing repaints
cached pixels directly without generating scaled QPixmaps or clearing labels.
Grid-derived hotspot rankings are comparative proposals, not official scores.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pixelscope.ui.design_tokens import TOKENS
from pixelscope_enterprise.iqa.spatial_candidates import SpatialCandidate


class StitchedRoiCanvas(QWidget):
    """Paint source-native A|B crops with one fit transform and no inner gutters."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("enterpriseIqaStitchedRoiCanvas")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(64)
        self._a: QPixmap | None = None
        self._b: QPixmap | None = None
        self._roi_size: tuple[int, int] = (512, 512)
        self.setToolTip("Original source-pixel ROI: A left | B right, common fit, no crop offset")

    @property
    def has_a(self) -> bool:
        return self._a is not None and not self._a.isNull()

    @property
    def has_b(self) -> bool:
        return self._b is not None and not self._b.isNull()

    def set_patches(
        self,
        a: QPixmap | None,
        b: QPixmap | None,
        source_size: tuple[int, int],
    ) -> None:
        """Accept already-cropped pixmaps; never recompute them on a resize."""

        self._a = a if a is not None and not a.isNull() else None
        self._b = b if b is not None and not b.isNull() else None
        self._roi_size = source_size
        self.update()

    def fitted_rect(self) -> QRectF:
        """Exact single-canvas A+B geometry, centered with no internal letterboxing."""

        width, height = self._roi_size
        if width <= 0 or height <= 0:
            return QRectF()
        usable = self.contentsRect()
        if usable.width() <= 0 or usable.height() <= 0:
            return QRectF()
        scale = min(usable.width() / (2.0 * width), usable.height() / height)
        target_width, target_height = 2.0 * width * scale, height * scale
        return QRectF(
            usable.x() + (usable.width() - target_width) / 2.0,
            usable.y() + (usable.height() - target_height) / 2.0,
            target_width,
            target_height,
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor(TOKENS.raised_background))
        frame = self.fitted_rect()
        if frame.isEmpty():
            painter.end()
            return
        half = frame.width() / 2.0
        source_width, source_height = self._roi_size
        for index, patch in enumerate((self._a, self._b)):
            region = QRectF(frame.x() + index * half, frame.y(), half, frame.height())
            if patch is None:
                painter.fillRect(region, QColor(TOKENS.workspace_background))
                painter.setPen(QColor(TOKENS.text_secondary))
                painter.drawText(
                    region.adjusted(4, 4, -4, -4),
                    Qt.AlignmentFlag.AlignCenter,
                    f"{'A' if index == 0 else 'B'} source unavailable",
                )
            else:
                painter.drawPixmap(
                    region,
                    patch,
                    QRectF(0, 0, source_width, source_height),
                )
            # Labels identify semantic sources, not left/right preference or quality.
            tag = QRectF(region.left() + 5, region.top() + 5, 19, 18)
            painter.fillRect(tag, QColor(22, 25, 30, 215))
            painter.setPen(QColor("#f2f4f5"))
            painter.drawText(
                tag,
                Qt.AlignmentFlag.AlignCenter,
                "A" if index == 0 else "B",
            )
        painter.setPen(QColor(TOKENS.accent))
        seam_x = frame.left() + half
        painter.drawLine(
            int(round(seam_x)),
            int(round(frame.top())),
            int(round(seam_x)),
            int(round(frame.bottom())),
        )
        painter.end()


def _rank_badge(rank: int) -> QPixmap:
    """Compact vector-painted rank token; top discovery is visually dominant."""

    badge = QPixmap(28, 28)
    badge.fill(Qt.GlobalColor.transparent)
    painter = QPainter(badge)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    # Match the muted-red A/B Attribute card semantic accent for first rank;
    # ranking itself is magnitude-only, not an A-wins verdict.
    tone = "#e5857d" if rank == 1 else "#7595b4"
    painter.setBrush(QColor(tone) if rank == 1 else QColor(TOKENS.raised_background))
    painter.setPen(QPen(QColor(tone), 2))
    painter.drawEllipse(2, 2, 24, 24)
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(14 if rank == 1 else 12)
    painter.setFont(font)
    painter.setPen(QColor("#1a1d21") if rank == 1 else QColor(TOKENS.text_primary))
    painter.drawText(QRect(2, 2, 24, 24), Qt.AlignmentFlag.AlignCenter, str(rank))
    if rank == 1:
        # A tiny star marks the highest-impact proposal independent of hue.
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QPolygonF

        painter.setBrush(QColor("#fce8ce"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(23, 0), QPointF(25, 5), QPointF(29, 6),
                    QPointF(26, 9), QPointF(27, 13), QPointF(23, 11),
                    QPointF(19, 13), QPointF(20, 9), QPointF(17, 6),
                    QPointF(21, 5),
                ]
            )
        )
    painter.end()
    return badge


def _blend_rank_tint(base: str, tint: str, fraction: float) -> str:
    """Use the exact quiet/hover/selected mixing levels of Attribute Top-3."""

    a = QColor(base)
    b = QColor(tint)
    return QColor(
        round(a.red() * (1.0 - fraction) + b.red() * fraction),
        round(a.green() * (1.0 - fraction) + b.green() * fraction),
        round(a.blue() * (1.0 - fraction) + b.blue() * fraction),
    ).name()


class SpatialCandidatesPanel(QWidget):
    """Three resizable stitched source comparison cards and one scan preset."""

    candidate_clicked = Signal(int)
    stride_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("enterpriseIqaSpatialCandidatesPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 3, 7, 5)
        layout.setSpacing(3)

        header = QHBoxLayout()
        self.heading = QLabel("ROI   TOP 3", self)
        self.heading.setObjectName("enterpriseIqaSpatialHeading")
        self.heading.setToolTip(
            "Ranks provisional GRID-derived spatial differences by local magnitude, "
            "not by an official ROI quality score."
        )
        self.heading.setStyleSheet(f"color: {TOKENS.text_primary}; font-weight: 700;")
        header.addWidget(self.heading)
        self.provenance_badge = QLabel("GRID", self)
        self.provenance_badge.setObjectName("enterpriseIqaGridBadge")
        self.provenance_badge.setToolTip(
            "Provisional GRID-derived ROI candidates. Not official IQA quality scores."
        )
        self.provenance_badge.setStyleSheet(
            f"color: {TOKENS.accent}; background-color: {TOKENS.title_background}; "
            f"border: 1px solid {TOKENS.border}; border-radius: 4px; padding: 1px 5px;"
        )
        header.addWidget(self.provenance_badge)
        header.addStretch(1)
        self.stride_selector = QComboBox(self)
        self.stride_selector.setObjectName("enterpriseIqaSpatialStride")
        for label, stride in (
            ("Detailed · 64 px", 64),
            ("Standard · 128 px", 128),
            ("Fast · 256 px", 256),
        ):
            self.stride_selector.addItem(label, stride)
        self.stride_selector.setCurrentIndex(1)
        self.stride_selector.setToolTip("Spatial search step in source pixels (not ROI size)")
        self.stride_selector.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._stride_selected
        )
        header.addWidget(self.stride_selector)
        layout.addLayout(header)

        self.status_label = QLabel("Peak |Δ|  ↓   ·   A/B ROI", self)
        self.status_label.setObjectName("enterpriseIqaSpatialStatus")
        self.status_label.setToolTip(
            "Mean of signed valid spatial grid cells inside a proposed source ROI. "
            "Ranking strength is relative among the three proposals only."
        )
        self.status_label.setWordWrap(False)
        self.status_label.setStyleSheet(f"color: {TOKENS.text_secondary};")
        layout.addWidget(self.status_label)
        self.progress = QProgressBar(self)
        self.progress.setObjectName("enterpriseIqaSpatialBusy")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(4)
        self.progress.hide()
        layout.addWidget(self.progress)

        row = QHBoxLayout()
        row.setSpacing(7)
        self.buttons: list[QPushButton] = []
        self.previews: list[StitchedRoiCanvas] = []
        self.titles: list[QLabel] = []
        self.rank_badges: list[QLabel] = []
        self.details: list[QLabel] = []
        self.impact_bars: list[QProgressBar] = []
        for index in range(3):
            card = QPushButton(self)
            card.setObjectName(f"enterpriseIqaSpatialCard{index + 1}")
            card.setCheckable(True)
            card.setEnabled(False)
            card.setMinimumHeight(108)
            card.setMinimumWidth(130)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            column = QVBoxLayout(card)
            column.setContentsMargins(5, 3, 5, 3)
            column.setSpacing(2)
            card_header = QHBoxLayout()
            card_header.setSpacing(5)
            rank_badge = QLabel(card)
            rank_badge.setObjectName(f"enterpriseIqaSpatialRank{index + 1}")
            rank_badge.setPixmap(_rank_badge(index + 1))
            rank_badge.setFixedSize(28, 28)
            rank_badge.setToolTip(
                f"#{index + 1}: ordered by relative GRID-derived search magnitude"
            )
            card_header.addWidget(rank_badge)
            card_title = QLabel("—", card)
            card_title.setObjectName("enterpriseIqaSpatialCardTitle")
            card_title.setStyleSheet(f"color: {TOKENS.text_primary}; font-weight: 600;")
            card_header.addWidget(card_title, 1)
            column.addLayout(card_header)
            preview = StitchedRoiCanvas(card)
            column.addWidget(preview, 1)
            detail = QLabel("—", card)
            detail.setObjectName("enterpriseIqaSpatialCardDetails")
            detail.setToolTip(
                "GRID-derived local mean; valid denotes spatial mask coverage. "
                "Not a verified official regional uplift."
            )
            detail.setStyleSheet(f"color: {TOKENS.text_secondary};")
            column.addWidget(detail)
            impact = QProgressBar(card)
            impact.setObjectName("enterpriseIqaSpatialRelativeImpact")
            impact.setRange(0, 100)
            impact.setValue(0)
            impact.setTextVisible(False)
            impact.setMaximumHeight(3)
            impact.setToolTip("Relative search score vs #1; not a calibrated quality rating")
            impact.setStyleSheet(
                f"QProgressBar {{ background-color: {TOKENS.panel_background}; "
                "border: none; }"
                f"QProgressBar::chunk {{ background-color: "
                f"{'#e5857d' if index == 0 else TOKENS.accent}; }}"
            )
            column.addWidget(impact)
            # Narrow, native per-button styling avoids complex parent QSS selector
            # parsing and any propagation into the custom paint canvas.
            accent = "#e5857d" if index == 0 else "#7595b4"
            base = TOKENS.raised_background
            card.setProperty("spatialRankTone", "top" if index == 0 else "other")
            card.setStyleSheet(
                f"QPushButton {{ background-color: {_blend_rank_tint(base, accent, 0.14)}; "
                f"border: 1px solid {TOKENS.border}; border-left: 4px solid {accent}; "
                "border-radius: 9px; text-align: left; }"
                f"QPushButton:hover {{ background-color: {_blend_rank_tint(base, accent, 0.22)}; "
                f"border-color: {accent}; }}"
                f"QPushButton:checked {{ background-color: {_blend_rank_tint(base, accent, 0.30)}; "
                f"border: 2px solid {accent}; border-left: 5px solid {accent}; }}"
            )
            for child in (rank_badge, card_title, preview, detail, impact):
                child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            card.clicked.connect(  # type: ignore[attr-defined]
                lambda _checked=False, i=index: self.candidate_clicked.emit(i)
            )
            row.addWidget(card, 1)
            self.buttons.append(card)
            self.previews.append(preview)
            self.titles.append(card_title)
            self.rank_badges.append(rank_badge)
            self.details.append(detail)
            self.impact_bars.append(impact)
        layout.addLayout(row, 1)

    def _stride_selected(self, _index: int) -> None:
        value = self.stride_selector.currentData()
        if isinstance(value, int):
            self.stride_changed.emit(value)

    @staticmethod
    def _crop(source: QPixmap | None, candidate: SpatialCandidate) -> QPixmap | None:
        """Bounded 512px source crop once, on GUI thread; not on every resize."""

        if source is None or source.isNull():
            return None
        rect = QRect(*candidate.roi)
        if not source.rect().contains(rect):
            return None
        return source.copy(rect)

    def set_busy(self, message: str) -> None:
        self.status_label.setText(message)
        self.progress.show()
        self.clear_cards()

    def clear_cards(self) -> None:
        for i, card in enumerate(self.buttons):
            card.setEnabled(False)
            card.setChecked(False)
            self.titles[i].setText("—")
            self.details[i].setText("—")
            self.previews[i].set_patches(None, None, (512, 512))
            self.impact_bars[i].setValue(0)

    def populate(
        self,
        candidates: Sequence[SpatialCandidate],
        pixmaps: tuple[QPixmap | None, QPixmap | None],
        unit: str,
    ) -> None:
        self.clear_cards()
        self.progress.hide()
        if not candidates:
            self.status_label.setText("No qualifying local GRID hotspot for this Attribute.")
            return
        self.status_label.setText("Peak |Δ|  ↓   ·   A/B ROI")
        leader = candidates[0].score
        for i, candidate in enumerate(candidates[:3]):
            self.buttons[i].setEnabled(True)
            self.titles[i].setText(f"({candidate.x}, {candidate.y})")
            self.titles[i].setToolTip(
                f"GRID proposal #{i + 1}: x={candidate.x}, y={candidate.y}, "
                f"source ROI {candidate.width}×{candidate.height} px"
            )
            self.details[i].setText(
                f"Δ {candidate.mean:+.2f} {unit}  ·  {candidate.valid_coverage:.0%}"
                + (" · ?" if candidate.mode == "exploratory_abs" else "")
            )
            self.details[i].setToolTip(
                f"ROI: ({candidate.x}, {candidate.y}) "
                f"{candidate.width}×{candidate.height} px; "
                f"mean {candidate.mean:+.4f} {unit}. GRID-derived only. "
                + (
                    "Exploratory (OFFICIAL sign missing)."
                    if candidate.mode == "exploratory_abs"
                    else ""
                )
            )
            a = self._crop(pixmaps[0], candidate)
            b = self._crop(pixmaps[1], candidate)
            self.previews[i].set_patches(a, b, (candidate.width, candidate.height))
            self.impact_bars[i].setValue(
                round(100.0 * candidate.score / leader) if leader > 0 else 0
            )

    def mark_selected(self, index: int | None) -> None:
        for i, button in enumerate(self.buttons):
            button.setChecked(i == index and button.isEnabled())
