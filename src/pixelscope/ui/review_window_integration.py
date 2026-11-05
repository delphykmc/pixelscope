"""W09b opt-in GUI composition. Installer is called by the Base orchestrator.

No runtime method monkey-patching, alternative source registry or Session
handler. Terminal foreground/layout events must be forwarded by the owner
through on_owner_terminal; never retry via sleeps or polling.
"""
from __future__ import annotations

import weakref
from pathlib import Path
from threading import Event
from typing import Any

import numpy as np
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QMessageBox,
)

from pixelscope.core.review_record import (
    ReviewDifferenceIntentV1,
    ReviewValidationError,
)
from pixelscope.core.review_workflow import ReviewLibrary
from pixelscope.io.memo_roi_export import export_roi_pngs
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.review_native_decoder import ENCODED_IMAGE_EXTENSIONS
from pixelscope.io.review_repository import ReviewConflictError, normalize_review_path
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.ui.display_gain import display_gain_state
from pixelscope.ui.raw_open_dialog import RawOpenDialog
from pixelscope.ui.review_capture_adapter import (
    AttestedFinding,
    CaptureGuiFence,
    StagedFinding,
    assert_same_capture_context,
    attest_staged_finding,
    capture_gui_fence,
    stage_named_finding,
)
from pixelscope.ui.review_main_window_adapter import MainWindowReviewRestoreAuthority
from pixelscope.ui.review_panel import ReviewPanel
from pixelscope.ui.review_restore_controller import (
    ApprovedCandidate,
    RestoreReport,
    ReviewRestoreController,
)
from pixelscope.ui.yuv_open_dialog import YuvOpenDialog
from pixelscope.workers.task_worker import TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool


class NamedReviewCoordinator:
    """Presentation glue and explicit profile/relink UI; MainWindow owns commits."""

    def __init__(self, window: Any) -> None:
        self._window_ref = weakref.ref(window)
        self.library = ReviewLibrary()
        self.panel = ReviewPanel()
        self.dock = QDockWidget("Memo", window)
        self.dock.setObjectName("namedReviewDock")
        self.dock.setWidget(self.panel)
        self.dock.setMinimumWidth(320)
        self.dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)
        window.register_contributed_dock(self.dock)
        self.dock.hide()
        self.authority = MainWindowReviewRestoreAuthority(window, self.library.document)
        self.restore = ReviewRestoreController(self.library, self.authority, self.panel)
        self._approved: dict[str, ApprovedCandidate] = {}
        self._auto_restore_id: str | None = None
        self._skip_next_selection_restore = False
        self._capture_epoch = 0
        self._capture_worker: TaskWorker | None = None
        self._capture_task_id: str | None = None
        self._capture_cancel: Event | None = None
        self._capture_stage: StagedFinding | None = None
        self._capture_fence: CaptureGuiFence | None = None
        self._export_epoch = 0
        self._export_task_id: str | None = None
        self._export_worker: TaskWorker | None = None
        self._export_cancel: Event | None = None
        self._closed = False
        self.action = QAction("Memo", window)
        self.action.setToolTip("Show or hide image inspection notes")
        self.action.setCheckable(True)
        self.action.triggered.connect(self._toggle_visibility)  # type: ignore[attr-defined]
        self.dock.visibilityChanged.connect(self._dock_visibility_changed)  # type: ignore[attr-defined]
        # Keep the W05/W06 critical toolbar footprint unchanged at 960/1400px.
        view_menu = window._menu_map["View"]
        # Use the strongly owned canonical menu; transient QMenu wrappers from
        # QAction.menu() may have lost their native object during Qt composition.
        view_menu.addAction(self.action)

        self.panel.add_requested.connect(self.add)
        self.panel.edit_requested.connect(self.edit)
        self.panel.delete_requested.connect(self.delete)
        self.panel.activate_requested.connect(self.activate)
        self.panel.open_requested.connect(self.open_dialog)
        self.panel.save_requested.connect(self.save_dialog)
        self.panel.export_roi_requested.connect(self.export_roi_dialog)
        self.panel.candidate_requested.connect(self.choose_candidate)
        self.panel.verify_requested.connect(self.verify)
        self.panel.finding_changed.connect(self.select_finding)
        self.restore.verification_completed.connect(self._verified)
        self.restore.verification_failed.connect(self._verification_failed)
        self.restore.restore_completed.connect(self._restored)
        self.panel.set_document(self.library.document)
        # Memo is an optional View dock, not a second workspace layout mode.
        self._workspace_presets = None

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None or window._closing or self._closed:
            raise RuntimeError("Named Finding owner closed")
        return window

    def show(self) -> None:
        """Expose the notes dock without silently changing the workspace layout."""
        if self._closed:
            return
        self.dock.show()
        self.dock.raise_()

    @Slot(bool)
    def _toggle_visibility(self, show: bool) -> None:
        """View > Named Findings has the same reversible contract as other docks."""
        if self._closed:
            return
        if show:
            self.show()
        else:
            self.dock.hide()

    @Slot(bool)
    def _dock_visibility_changed(self, visible: bool) -> None:
        """The dock X button and the View checkmark are one visibility state."""
        if self._closed:
            return
        blocked = self.action.blockSignals(True)
        try:
            self.action.setChecked(visible)
        finally:
            self.action.blockSignals(blocked)

    @Slot(int)
    def _workspace_changed(self, _index: int) -> None:
        # Deprecated W06 layout integration: Memo is solely View-controlled.
        return

    def _error(self, message: str) -> None:
        self.panel.set_status(message)
        QMessageBox.warning(self.panel, "Named Finding", message)

    @Slot()
    def export_roi_dialog(self) -> None:
        """Export the *working page* ROI with no Review save/capture prerequisite."""
        if self._closed:
            return
        try:
            window = self.window
            roi = window._shared_roi
            if roi is None:
                self.panel.set_status("Draw an ROI first, then export PNG crops")
                return
            page = tuple(window.current_comparison_documents())
            if not page:
                self.panel.set_status("Select images before exporting an ROI")
                return
            images = []
            for document in page:
                preview = document.preview
                if (
                    document.loading_state != "ready"
                    or not isinstance(preview, np.ndarray)
                    or preview.dtype != np.uint8
                    or document.source is None
                ):
                    raise ValueError(
                        f"Wait for {document.display_name} to finish loading before export"
                    )
                images.append((document.display_name, preview))
            directory = QFileDialog.getExistingDirectory(
                self.panel,
                "Export selected ROI PNGs (current comparison page)",
            )
            if not directory:
                return
            # Freeze ROI and preview references at the user's click. Encoding and
            # file writes run in the bounded worker, never the GUI event loop.
            self.cancel_export()
            epoch = self._export_epoch
            cancel = Event()
            worker = TaskWorker(
                export_roi_pngs,
                Path(directory),
                tuple(images),
                roi,
                cancel=cancel.is_set,
                generation=epoch,
            )
            self._export_cancel = cancel
            self._export_worker = worker
            self._export_task_id = worker.task_id
            worker.signals.succeeded.connect(self._export_succeeded)
            worker.signals.failed.connect(self._export_failed)
            worker.signals.finished.connect(self._export_finished)
            analysis_thread_pool().start(worker)
            self.panel.set_status(
                f"Exporting ROI {roi.width}×{roi.height} for {len(images)} page image(s)…"
            )
        except (OSError, ValueError, RuntimeError) as exc:
            self._error(f"ROI PNG export unavailable: {exc}")

    @Slot(str, object, int, object)
    def _export_succeeded(self, task_id: str, _document: object, epoch: int, value: object) -> None:
        if self._closed or task_id != self._export_task_id or epoch != self._export_epoch:
            return
        if isinstance(value, tuple):
            message = (
                f"Exported {len(value)} ROI PNG(s) to {value[0].parent}"
                if value
                else "No ROI crops exported"
            )
            self.panel.set_status(message)

    @Slot(str, object, int, object)
    def _export_failed(self, task_id: str, _document: object, epoch: int, error: object) -> None:
        if not self._closed and epoch == self._export_epoch and task_id == self._export_task_id:
            self._error(f"ROI PNG export failed: {getattr(error, 'message', error)}")

    @Slot(str)
    def _export_finished(self, task_id: str) -> None:
        if task_id == self._export_task_id:
            self._export_worker = None
            self._export_task_id = None
            self._export_cancel = None

    def cancel_export(self) -> None:
        self._export_epoch += 1
        if self._export_cancel is not None:
            self._export_cancel.set()
        if self._export_worker is not None:
            self._export_worker.cancel()
        self._export_worker = None
        self._export_task_id = None
        self._export_cancel = None

    def cancel_capture(self) -> None:
        self._capture_epoch += 1
        if self._capture_cancel is not None:
            self._capture_cancel.set()
        if self._capture_worker is not None:
            self._capture_worker.cancel()
        self._capture_worker = None
        self._capture_task_id = None
        self._capture_cancel = None
        self._capture_stage = None
        self._capture_fence = None

    @Slot()
    def add(self) -> None:
        if self._closed:
            return
        self.cancel_capture()
        try:
            window = self.window
            title, note, tags = self.panel.metadata()
            if not title:
                title = f"Finding {len(self.library.document.findings) + 1}"
            page = tuple(window.current_comparison_documents())
            if not page:
                raise ReviewValidationError("No comparison sources are selected")
            panel = window.comparison_analysis_panel
            keys = {d.document_id: panel.source_key_for_document(d.document_id) for d in page}
            panel.bind_review_source_keys(keys)
            primary = window._primary_document_for_page(list(page))
            if primary is None:
                raise ReviewValidationError("Primary source is not available")
            pair = window.difference_panel.selected_documents()
            if (
                pair is not None
                and window.diff_action.isChecked()
                and all(d.document_id in keys for d in pair)
            ):
                reference_id, target_id = pair[0].document_id, pair[1].document_id
                difference = window.difference_panel
                recipe = ReviewDifferenceIntentV1(
                    keys[reference_id],
                    keys[target_id],
                    difference.channel.currentText(),
                    difference.mode.currentText(),
                    float(difference.threshold.value()),
                    int(difference.gain.value()),
                    difference.region.currentText(),
                )
            else:
                reference_id = primary.document_id
                target_id = None
                recipe = None
            roi = window._shared_roi
            line = window._shared_line
            stage = stage_named_finding(
                window.multi_compare_view,
                page,
                keys,
                title=title,
                note=note,
                tags=tags,
                reference_document_id=reference_id,
                primary_document_id=primary.document_id,
                pair_target_document_id=target_id,
                roi_ref=None if roi is None else (roi.x, roi.y, roi.width, roi.height),
                line_ref=None if line is None else (line.x1, line.y1, line.x2, line.y2),
                channel="All",
                display_gain=display_gain_state().gain,
                difference_intent=recipe,
                analysis_panel=None,  # ROI/image note, not a statistics report.
                # Editable local Memo bookmarks need their exact source paths.
                # Portable HTML exports must explicitly strip these private paths.
                persist_local_paths=True,
                single_viewer=(
                    window.viewer
                    if len(page) == 1 and window.central_stack.currentWidget() is window.viewer
                    else None
                ),
            )
            fence = capture_gui_fence(window, stage)
            epoch = self._capture_epoch
            cancel = Event()
            self._capture_stage = stage
            self._capture_fence = fence
            worker = TaskWorker(
                attest_staged_finding, stage, cancel=cancel.is_set, generation=epoch
            )
            self._capture_cancel = cancel
            self._capture_worker = worker
            self._capture_task_id = worker.task_id
            worker.signals.succeeded.connect(self._capture_succeeded)
            worker.signals.failed.connect(self._capture_failed)
            worker.signals.finished.connect(self._capture_finished)
            analysis_thread_pool().start(worker)
            self.panel.set_status("Verifying candidate bytes and loaded native samples…")
        except (ValueError, KeyError, RuntimeError, AttributeError) as exc:
            self._error(f"Finding capture unavailable: {exc}")

    @Slot(str, object, int, object)
    def _capture_succeeded(
        self, task_id: str, _document: object, epoch: int, value: object
    ) -> None:
        if (
            self._closed
            or epoch != self._capture_epoch
            or task_id != self._capture_task_id
            or not isinstance(value, AttestedFinding)
        ):
            return
        try:
            stage = self._capture_stage
            fence = self._capture_fence
            if stage is None or fence is None or value.finding.id != stage.finding.id:
                raise ReviewValidationError("capture stage or revision was superseded")
            if value.bindings != stage.sources:
                raise ReviewValidationError("source bindings changed during attestation")
            assert_same_capture_context(fence, capture_gui_fence(self.window, stage))
            current = self.window.documents
            if not all(item.still_loaded_as(current) for item in value.bindings):
                raise ReviewValidationError("source generation changed during capture")
            self.library.add(value.finding, value.sources)
            self._skip_next_selection_restore = True
            self.panel.set_document(self.library.document, selected_id=value.finding.id)
            self.panel.set_status("Memo added. Select it later to revisit this ROI.")
        except (ValueError, KeyError, RuntimeError) as exc:
            self._error(f"Finding commit refused: {exc}")

    @Slot(str, object, int, object)
    def _capture_failed(self, task_id: str, _doc: object, epoch: int, err: object) -> None:
        if not self._closed and task_id == self._capture_task_id and epoch == self._capture_epoch:
            self._error(f"Source attestation unavailable: {getattr(err, 'message', err)}")

    @Slot(str)
    def _capture_finished(self, task_id: str) -> None:
        if task_id == self._capture_task_id:
            self._capture_task_id = None
            self._capture_worker = None
            self._capture_cancel = None
            self._capture_stage = None
            self._capture_fence = None

    @Slot(str, str, str, object)
    def edit(self, finding_id: str, title: str, note: str, tags: object) -> None:
        try:
            if not isinstance(tags, tuple):
                raise ReviewValidationError("tags are not a tuple")
            self.library.edit(finding_id, title=title, note=note, tags=tags)
            self._skip_next_selection_restore = True
            self.panel.set_document(self.library.document, selected_id=finding_id)
            self.panel.set_status("Memo updated")
        except (ValueError, KeyError) as exc:
            self._error(str(exc))

    @Slot(str)
    def delete(self, finding_id: str) -> None:
        self.cancel_capture()
        self.restore.cancel()
        try:
            self.library.delete(finding_id)
            self.panel.set_document(self.library.document)
            self.panel.set_status("Memo deleted")
        except KeyError as exc:
            self._error(str(exc))

    @Slot(str)
    def select_finding(self, finding_id: str) -> None:
        """Selecting a Memo is the one-click navigate/restore command.

        Original saved paths are used only as candidates. Every source is
        verified in the existing W09a worker before mutating the workspace.
        Missing or ambiguous files are left for explicit user correction.
        """
        if self._closed:
            return
        if self._skip_next_selection_restore:
            self._skip_next_selection_restore = False
            return
        self.cancel_capture()
        self.restore.change_finding(finding_id)
        self._auto_restore_id = None
        self._approved.clear()
        self.panel.set_resolutions({})
        try:
            finding = self.library.get(finding_id)
            by_key = {source.source_key: source for source in self.library.document.sources}
            missing: list[str] = []
            for key in finding.source_keys:
                source = by_key[key]
                saved = source.locator.local_path
                if saved is None:
                    missing.append(key)
                    continue
                path = Path(saved)
                if not path.is_file():
                    missing.append(key)
                    continue
                suffix = path.suffix.lower()
                profile: RawProfile | YuvProfile | None = None
                if suffix in (".raw", ".yuv"):
                    # A native profile must originate from a currently approved
                    # loaded source, not from historical untrusted JSON.
                    loaded = next(
                        (
                            document
                            for document in self.window.documents.values()
                            if document.source_path is not None
                            and document.source_path.resolve() == path.resolve()
                            and isinstance(document.raw_profile, RawProfile | YuvProfile)
                        ),
                        None,
                    )
                    if loaded is None:
                        missing.append(key)
                        continue
                    profile = loaded.raw_profile
                elif suffix not in ENCODED_IMAGE_EXTENSIONS:
                    missing.append(key)
                    continue
                self._approved[key] = ApprovedCandidate(key, path, profile, False)
            if missing:
                self.panel.show_missing_images(tuple(missing))
                self.panel.set_status(
                    "Some images need locating. Choose Locate image to reconnect; "
                    "your note remains available."
                )
                return
            self._auto_restore_id = finding_id
            self.verify()
            self.panel.set_status("Opening saved memo and ROI…")
        except (OSError, ValueError, KeyError) as exc:
            self.panel.set_status(f"Memo cannot be reopened: {exc}")

    def open_dialog(self) -> None:
        if (
            self.library.dirty
            and QMessageBox.question(
                self.panel,
                "Unsaved Review",
                "Discard unsaved Finding changes?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        chosen, _ = QFileDialog.getOpenFileName(
            self.panel,
            "Open Review",
            "",
            "Pixelscope Review (*.pxreview)",
        )
        if not chosen:
            return
        self.cancel_capture()
        self.restore.cancel()
        try:
            self.library.open(chosen)
            self.authority.review = self.library.document
            self._approved.clear()
            first = self.library.document.findings[0].id if self.library.document.findings else None
            self.panel.set_document(self.library.document, selected_id=first)
            if first is None:
                self.panel.set_status("Memo opened. No saved notes yet.")
        except (OSError, ValueError) as exc:
            self._error(f"Open failed; existing Review retained: {exc}")

    def save_dialog(self) -> None:
        path = self.library.path
        if path is None:
            filename, _ = QFileDialog.getSaveFileName(
                self.panel,
                "Save Review",
                "",
                "Pixelscope Review (*.pxreview)",
            )
            if not filename:
                return
            path = normalize_review_path(filename)
        overwrite = path.is_file()
        if overwrite and self.library.path != path:
            self._error("Destination exists; open the exact Review before overwriting")
            return
        if (
            overwrite
            and QMessageBox.question(
                self.panel,
                "Overwrite Review",
                "Replace this Review revision?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            protected = tuple(
                d.source_path for d in self.window.documents.values() if d.source_path is not None
            )
            result = self.library.save(
                path,
                overwrite=overwrite,
                protected_paths=protected,
            )
            if result.committed:
                self.panel.set_status(f"Saved {result.path.name} (atomic CAS)")
        except (ReviewConflictError, OSError, ValueError) as exc:
            self._error(f"Review save failed, existing destination retained: {exc}")

    @Slot(str)
    def choose_candidate(self, key: str) -> None:
        source = next((s for s in self.library.document.sources if s.source_key == key), None)
        if source is None:
            return
        filename, _ = QFileDialog.getOpenFileName(self.panel, "Choose Review source candidate")
        if not filename:
            return
        path = Path(filename).resolve()
        if not path.is_file():
            self._error("Candidate file is missing")
            return
        profile: RawProfile | YuvProfile | None = None
        dialog: RawOpenDialog | YuvOpenDialog | None = None
        if path.suffix.casefold() == ".raw":
            dialog = RawOpenDialog(self.panel)
            dialog.set_source_path(path)
        elif path.suffix.casefold() == ".yuv":
            dialog = YuvOpenDialog(self.panel)
            dialog.set_source_path(path)
        elif path.suffix.casefold() not in ENCODED_IMAGE_EXTENSIONS:
            self._error("Supported Memo sources: PNG, BMP, JPEG, RAW, YUV")
            return
        if dialog is not None:
            if dialog.exec() != dialog.DialogCode.Accepted:
                return
            profile = dialog.profile()
        try:
            saved = source.locator.local_path
            same = (
                saved is not None and str(Path(saved).resolve()).casefold() == str(path).casefold()
            )
            approved = (
                same
                or QMessageBox.question(
                    self.panel,
                    "Approve Relink",
                    f"Relink historical source {source.locator.basename} to {path.name}? "
                    "Digest and native profile will still be checked.",
                )
                == QMessageBox.StandardButton.Yes
            )
            if not approved:
                self.panel.set_status("Relink not approved; source remains unverified")
                return
            self._approved[key] = ApprovedCandidate(key, path, profile, not same)
            selected = self.panel.selected_finding_id
            if selected is not None:
                finding = self.library.get(selected)
                if all(key in self._approved for key in finding.source_keys):
                    self._auto_restore_id = selected
                    self.verify()
                    self.panel.set_status("Reconnecting image and opening saved ROI…")
                else:
                    self.panel.show_missing_images(
                        tuple(key for key in finding.source_keys if key not in self._approved)
                    )
        except (ValueError, TypeError) as exc:
            self._error(f"Native profile invalid: {exc}")

    def verify(self) -> None:
        finding_id = self.panel.selected_finding_id
        if finding_id is None:
            return
        try:
            epoch = self.restore.verify(finding_id, dict(self._approved))
            self.panel.set_status(f"Verifying Finding epoch {epoch} (background SHA/native decode)")
        except (ValueError, RuntimeError, KeyError) as exc:
            self._error(f"Cannot verify Finding: {exc}")

    @Slot(int, object)
    def _verified(self, epoch: int, results: object) -> None:
        if not self._closed and isinstance(results, dict) and epoch == self.restore.epoch:
            self.panel.set_resolutions(results)
            selected = self.panel.selected_finding_id
            if selected is not None and selected == self._auto_restore_id:
                finding = self.library.get(selected)
                if all(
                    results.get(key) is not None and results[key].may_bind_historical_finding
                    for key in finding.source_keys
                ):
                    self._auto_restore_id = None
                    self.activate(selected)
                    return
                self.panel.set_status(
                    "Saved image differs or is unavailable. Locate the correct image."
                )
            self._auto_restore_id = None

    @Slot(int, str)
    def _verification_failed(self, epoch: int, reason: str) -> None:
        if not self._closed and epoch == self.restore.epoch:
            self._auto_restore_id = None
            self.panel.set_status(f"Memo image could not be opened: {reason}")

    def activate(self, finding_id: str) -> None:
        self.restore.activate(finding_id)

    @Slot(object)
    def _restored(self, report: object) -> None:
        if isinstance(report, RestoreReport) and not self._closed:
            self.panel.set_status(
                f"Restore {report.status}: {report.reason}"
                + (" (PARTIAL POST-COMMIT)" if report.partial_state else "")
            )

    def on_owner_terminal(self, epoch: int) -> None:
        """Only an epoch-tagged, authoritative foreground/load/layout completion."""
        if not self._closed and epoch == self.restore.epoch:
            self.restore.owner_terminal_notification(epoch)

    def shutdown(self) -> None:
        if self._closed:
            return
        self.cancel_capture()
        self.cancel_export()
        self.restore.shutdown()
        self._auto_restore_id = None
        self._closed = True
        self.action.setEnabled(False)


def install_named_review(window: Any) -> NamedReviewCoordinator:
    existing = getattr(window, "named_review_coordinator", None)
    if isinstance(existing, NamedReviewCoordinator):
        return existing
    controller = NamedReviewCoordinator(window)
    window.named_review_coordinator = controller
    return controller
