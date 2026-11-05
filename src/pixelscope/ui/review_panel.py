"""Memo panel — one-click inspection notes, not a second Session workspace."""
from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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
    activate_requested = Signal(str)
    open_requested = Signal()
    save_requested = Signal()
    export_roi_requested = Signal()
    candidate_requested = Signal(str)
    verify_requested = Signal()
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

        form = QGroupBox("Memo", self)
        grid = QFormLayout(form)
        self.title_edit = QLineEdit(form)
        self.title_edit.setObjectName("findingTitleEdit")
        self.title_edit.setMaxLength(256)
        self.note_edit = QPlainTextEdit(form)
        self.note_edit.setObjectName("findingNoteEdit")
        self.note_edit.setMaximumHeight(115)
        self.tags_edit = QLineEdit(form)
        self.tags_edit.setObjectName("findingTagsEdit")
        self.tags_edit.setPlaceholderText("comma-separated tags")
        grid.addRow("Title", self.title_edit)
        grid.addRow("Note", self.note_edit)
        # Legacy tags are preserved in .pxreview but not exposed as a required
        # editing workflow. They do not justify an additional form field.
        layout.addWidget(form)

        row = QHBoxLayout()
        self.add_button = QPushButton("Add Memo", self)
        self.edit_button = QPushButton("Update", self)
        self.delete_button = QPushButton("Delete", self)
        for button in (self.add_button, self.edit_button, self.delete_button):
            row.addWidget(button)
        layout.addLayout(row)

        self.export_roi_button = QPushButton("Export ROI PNGs…", self)
        self.export_roi_button.setObjectName("memoExportRoiPngs")
        self.export_roi_button.setToolTip(
            "Save one PNG per loaded source on the current comparison page, "
            "using the same ROI in reference pixel coordinates. "
            "Exports the canonical 8-bit preview, without drawn overlays."
        )
        layout.addWidget(self.export_roi_button)

        self.evidence_label = QLabel("Select a memo to revisit its ROI", self)
        self.evidence_label.setWordWrap(True)
        self.evidence_label.setObjectName("findingEvidenceStatus")
        layout.addWidget(self.evidence_label)
        # Source recovery is exceptional; do not expose byte verification or
        # activation mechanics beside everyday image notes.
        self.sources_group = QGroupBox("Locate missing images", self)
        sources_layout = QVBoxLayout(self.sources_group)
        self.sources = QListWidget(self.sources_group)
        self.sources.setObjectName("reviewSourceStatuses")
        sources_layout.addWidget(self.sources)
        self.candidate_button = QPushButton("Locate image…", self.sources_group)
        sources_layout.addWidget(self.candidate_button)
        layout.addWidget(self.sources_group)
        self.sources_group.hide()

        footer = QHBoxLayout()
        self.open_button = QPushButton("Open Memo…", self)
        self.save_button = QPushButton("Save Memo…", self)
        footer.addWidget(self.open_button)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)
        self.status = QLabel("Select a memo to return to its saved image and ROI")
        self.status.setWordWrap(True)
        self.status.setObjectName("reviewStatusLabel")
        layout.addWidget(self.status)

        self.findings.currentItemChanged.connect(self._selection_changed)  # type: ignore[attr-defined]
        self.add_button.clicked.connect(self.add_requested.emit)  # type: ignore[attr-defined]
        self.edit_button.clicked.connect(self._request_edit)  # type: ignore[attr-defined]
        self.delete_button.clicked.connect(self._request_delete)  # type: ignore[attr-defined]
        self.open_button.clicked.connect(self.open_requested.emit)  # type: ignore[attr-defined]
        self.save_button.clicked.connect(self.save_requested.emit)  # type: ignore[attr-defined]
        self.export_roi_button.clicked.connect(self.export_roi_requested.emit)  # type: ignore[attr-defined]
        self.candidate_button.clicked.connect(self._request_candidate)  # type: ignore[attr-defined]
        self._set_selection_enabled(False)

    def _set_selection_enabled(self, has_finding: bool) -> None:
        self.edit_button.setEnabled(has_finding)
        self.delete_button.setEnabled(has_finding)
        self.candidate_button.setEnabled(has_finding)

    @property
    def selected_finding_id(self) -> str | None:
        item = self.findings.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    @property
    def selected_source_key(self) -> str | None:
        item = self.sources.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def metadata(self) -> tuple[str, str, tuple[str, ...]]:
        return (
            self.title_edit.text().strip(),
            self.note_edit.toPlainText(),
            tuple(tag.strip() for tag in self.tags_edit.text().split(",") if tag.strip()),
        )

    def set_status(self, message: str) -> None:
        self.status.setText(message)

    def _request_edit(self) -> None:
        key = self.selected_finding_id
        if key is not None:
            title, note, tags = self.metadata()
            self.edit_requested.emit(key, title, note, tags)

    def _request_delete(self) -> None:
        key = self.selected_finding_id
        if key is not None:
            self.delete_requested.emit(key)

    def _request_activate(self) -> None:
        key = self.selected_finding_id
        if key is not None:
            self.activate_requested.emit(key)

    def _request_candidate(self) -> None:
        key = self.selected_source_key
        if key is not None:
            self.candidate_requested.emit(key)

    def set_document(self, document: ReviewDocumentV1, *, selected_id: str | None = None) -> None:
        self._document = document
        self.findings.blockSignals(True)
        self.findings.clear()
        for finding in document.findings:
            source_count = len(finding.source_keys)
            label = f"{finding.title}  ·  {source_count} image(s)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, finding.id)
            item.setToolTip(f"ROI: {finding.roi_ref or 'not set'}\nClick to revisit this note")
            self.findings.addItem(item)
            if finding.id == selected_id:
                self.findings.setCurrentItem(item)
        self.findings.blockSignals(False)
        self._selection_changed()

    def show_missing_images(self, keys: tuple[str, ...]) -> None:
        """Expose only the missing-source correction, never manual Verify."""
        self.sources.clear()
        if self._document is None:
            return
        by_key = {source.source_key: source for source in self._document.sources}
        for key in keys:
            source = by_key.get(key)
            if source is not None:
                item = QListWidgetItem(source.display_tag or source.locator.basename)
                item.setData(Qt.ItemDataRole.UserRole, key)
                self.sources.addItem(item)
        self.sources_group.setVisible(self.sources.count() > 0)
        if self.sources.count():
            self.sources.setCurrentRow(0)

    def set_resolutions(self, resolutions: Mapping[str, SourceResolutionV1]) -> None:
        self.sources.clear()
        selected = self.selected_finding_id
        if self._document is None or selected is None:
            self._set_selection_enabled(False)
            return
        finding = next((f for f in self._document.findings if f.id == selected), None)
        if finding is None:
            self._set_selection_enabled(False)
            return
        by_key = {s.source_key: s for s in self._document.sources}
        complete = True
        for key in finding.source_keys:
            source = by_key[key]
            resolution = resolutions.get(key)
            state = resolution.status if resolution is not None else "candidate_unverified"
            complete = bool(
                complete and resolution is not None and resolution.may_bind_historical_finding
            )
            label = source.display_tag or source.locator.basename
            item = QListWidgetItem(f"{label}: {state}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(resolution.reason if resolution else "Candidate not yet checked")
            self.sources.addItem(item)
        self.sources_group.setVisible(not complete and bool(resolutions))
        self.candidate_button.setEnabled(not complete and self.sources.count() > 0)
        if self.sources.count():
            self.sources.setCurrentRow(0)

    def _selection_changed(self, *_args: object) -> None:
        key = self.selected_finding_id
        if self._document is None or key is None:
            self._set_selection_enabled(False)
            self.evidence_label.setText("Select a memo to revisit its ROI")
            self.sources.clear()
            self.sources_group.hide()
            return
        finding: ReviewFindingV1 = next(f for f in self._document.findings if f.id == key)
        self.title_edit.setText(finding.title)
        self.note_edit.setPlainText(finding.note)
        self.tags_edit.setText(", ".join(finding.tags))
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
