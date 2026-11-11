"""Memo panel — one-click inspection notes, not a second Session workspace."""
from __future__ import annotations

import html
from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.core.review_record import ReviewDocumentV1, ReviewFindingV1
from pixelscope.io.review_repository import SourceResolutionV1


class ReviewPanel(QWidget):
    """Simple note list with a hidden-on-success recovery path.

    The controller restores each selected Memo automatically after source checks.
    No manual Verify/Activate controls are part of the everyday workflow.
    """

    add_requested = Signal()
    edit_requested = Signal(str, str, str, object)
    delete_requested = Signal(str)
    open_requested = Signal()
    save_requested = Signal()
    finding_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("memoPanel")
        self._document: ReviewDocumentV1 | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.header = QLabel("Memo — notes linked to image regions")
        self.header.setObjectName("reviewEvidenceHeader")
        layout.addWidget(self.header)
        self.findings = QListWidget(self)
        self.findings.setObjectName("namedFindingList")
        self.findings.setAccessibleName("Saved image inspection memos")
        layout.addWidget(self.findings, 3)

        self.crop_previews = QListWidget(self)
        self.crop_previews.setObjectName("memoSavedCropPreviews")
        self.crop_previews.setViewMode(QListWidget.ViewMode.IconMode)
        self.crop_previews.setIconSize(QSize(120, 80))
        self.crop_previews.setToolTip("Saved ROI images — readable even without originals")
        self.crop_previews.setMaximumHeight(160)
        self.crop_previews.setAccessibleName("Saved ROI crops, independent of original images")
        layout.addWidget(self.crop_previews)

        form = QGroupBox("Memo", self)
        grid = QFormLayout(form)
        self.title_edit = QLineEdit(form)
        self.title_edit.setObjectName("findingTitleEdit")
        self.title_edit.setMaxLength(256)
        self.note_edit = QPlainTextEdit(form)
        self.note_edit.setObjectName("findingNoteEdit")
        self.note_edit.setMaximumHeight(115)
        self._tags: tuple[str, ...] = ()
        grid.addRow("Title", self.title_edit)
        grid.addRow("Note", self.note_edit)
        # Legacy tags are preserved in .pxreview but not exposed as a required
        # editing workflow. They do not justify an additional form field.
        layout.addWidget(form)

        self.include_statistics = QCheckBox("Include current ROI statistics", self)
        self.include_statistics.setToolTip(
            "Copy already displayed native ROI Statistics into this memo. "
            "No new calculation; unavailable or stale results are never substituted."
        )
        layout.addWidget(self.include_statistics)

        row = QHBoxLayout()
        self.add_button = QPushButton("Add ROI", self)
        self.delete_button = QPushButton("Delete", self)
        for button in (self.add_button, self.delete_button):
            row.addWidget(button)
        layout.insertLayout(2, row)

        self.evidence_label = QLabel("Select a memo to revisit its ROI", self)
        self.evidence_label.setWordWrap(True)
        self.evidence_label.setObjectName("findingEvidenceStatus")
        layout.addWidget(self.evidence_label)
        footer = QHBoxLayout()
        self.open_button = QPushButton("Open Memo…", self)
        self.save_button = QPushButton("Save Memo…", self)
        footer.addWidget(self.open_button)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)
        self.status = QLabel("Select a memo to return to its saved image and ROI")
        self.status.setWordWrap(True)
        self.status.setObjectName("reviewStatusLabel")
        self.status.setOpenExternalLinks(True)
        self.status.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        layout.addWidget(self.status)

        self.findings.currentItemChanged.connect(self._selection_changed)  # type: ignore[attr-defined]
        self.add_button.clicked.connect(self.add_requested.emit)  # type: ignore[attr-defined]
        self.delete_button.clicked.connect(self._request_delete)  # type: ignore[attr-defined]
        self.open_button.clicked.connect(self.open_requested.emit)  # type: ignore[attr-defined]
        self.save_button.clicked.connect(self.save_requested.emit)  # type: ignore[attr-defined]
        self.title_edit.textEdited.connect(self._request_edit)  # type: ignore[attr-defined]
        self.note_edit.textChanged.connect(self._request_edit)  # type: ignore[attr-defined]
        self._set_selection_enabled(False)

    def _set_selection_enabled(self, has_finding: bool) -> None:
        self.delete_button.setEnabled(has_finding)
        self.title_edit.setEnabled(has_finding)
        self.note_edit.setEnabled(has_finding)

    @property
    def selected_finding_id(self) -> str | None:
        item = self.findings.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def metadata(self) -> tuple[str, str, tuple[str, ...]]:
        return (
            self.title_edit.text().strip(),
            self.note_edit.toPlainText(),
            self._tags,
        )

    def set_status(self, message: str) -> None:
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setToolTip("")
        self.status.setText(message)

    def show_saved_report(self, notebook: Path, report: Path) -> None:
        url = html.escape(QUrl.fromLocalFile(str(report)).toString(), quote=True)
        self.status.setTextFormat(Qt.TextFormat.RichText)
        self.status.setText(
            f'Saved {html.escape(notebook.name)} · <a href="{url}">Open report</a>'
            f"<br>{html.escape(report.parent.name)} / index.html"
        )
        self.status.setToolTip(str(report))

    def show_saved_crops(self, thumbnails: Mapping[str, bytes]) -> None:
        self.crop_previews.clear()
        if self._document is None:
            return
        labels = {s.source_key: s.display_tag or s.locator.basename for s in self._document.sources}
        for key, data in thumbnails.items():
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                scaled = pixmap.scaled(
                    QSize(120, 80),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                item = QListWidgetItem(QIcon(scaled), labels.get(key, "Image"))
                item.setToolTip("Saved 8-bit ROI preview — original pixels are unchanged")
                self.crop_previews.addItem(item)
        self.crop_previews.setVisible(bool(thumbnails))

    def set_dirty(self, dirty: bool, *, saved: bool = False) -> None:
        if not dirty and not saved and (self._document is None or not self._document.findings):
            self.header.setText("● Ready")
            self.header.setStyleSheet("color: #777777")
            return
        self.header.setText("● Unsaved" if dirty else "● Saved")
        self.header.setStyleSheet(
            "color: #c77a00; font-weight: bold" if dirty else "color: #23844b; font-weight: bold"
        )

    def _request_edit(self, *_args: object) -> None:
        key = self.selected_finding_id
        if key is not None:
            title, note, tags = self.metadata()
            self.edit_requested.emit(key, title, note, tags)

    def _request_delete(self) -> None:
        key = self.selected_finding_id
        if key is not None:
            self.delete_requested.emit(key)

    def set_document(self, document: ReviewDocumentV1, *, selected_id: str | None = None) -> None:
        self._document = document
        self.findings.blockSignals(True)
        self.findings.clear()
        for ordinal, finding in enumerate(document.findings, 1):
            label = f"ROI {ordinal} · {finding.title}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, finding.id)
            item.setToolTip(f"ROI: {finding.roi_ref or 'not set'}\nClick to revisit this note")
            self.findings.addItem(item)
            if finding.id == selected_id:
                self.findings.setCurrentItem(item)
        self.findings.blockSignals(False)
        self._selection_changed()

    def show_missing_images(self, keys: tuple[str, ...]) -> None:
        self.set_status("Original image unavailable — saved ROI crops and notes remain readable")

    def set_resolutions(self, resolutions: Mapping[str, SourceResolutionV1]) -> None:
        if resolutions and any(not r.may_bind_historical_finding for r in resolutions.values()):
            self.set_status(
                "Original image unavailable — saved ROI crops and notes remain readable"
            )

    def _selection_changed(self, *_args: object) -> None:
        key = self.selected_finding_id
        if self._document is None or key is None:
            self.show_saved_crops({})
            self._set_selection_enabled(False)
            self.evidence_label.setText("Select a memo to revisit its ROI")
            return
        finding: ReviewFindingV1 = next(f for f in self._document.findings if f.id == key)
        self.title_edit.blockSignals(True)
        self.note_edit.blockSignals(True)
        self.title_edit.setText(finding.title)
        self.note_edit.setPlainText(finding.note)
        self.title_edit.blockSignals(False)
        self.note_edit.blockSignals(False)
        self._tags = finding.tags
        source_names = {
            source.source_key: source.display_tag or source.locator.basename
            for source in self._document.sources
        }
        image_labels = ", ".join(source_names[key] for key in finding.source_keys)
        roi_label = (
            f"ROI: x={finding.roi_ref[0]}, y={finding.roi_ref[1]}, "
            f"{finding.roi_ref[2]}×{finding.roi_ref[3]}"
            if finding.roi_ref is not None
            else "Full image / no ROI"
        )
        self.evidence_label.setText(f"{roi_label}\nImages: {image_labels}")
        self._set_selection_enabled(True)
        self.set_resolutions({})
        self.finding_changed.emit(key)
