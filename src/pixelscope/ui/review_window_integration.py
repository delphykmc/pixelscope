"""W09b opt-in GUI composition. Installer is called by the Base orchestrator.

No runtime method monkey-patching, alternative source registry or Session
handler. Terminal foreground/layout events must be forwarded by the owner
through on_owner_terminal; never retry via sleeps or polling.
"""
from __future__ import annotations

import weakref
import zipfile
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
)

from pixelscope.core.review_record import (
    ReviewDifferenceIntentV1,
    ReviewValidationError,
)
from pixelscope.core.review_workflow import ReviewLibrary
from pixelscope.core.roi import RoiBounds
from pixelscope.io.memo_archive import (
    MemoArchive,
    load_memo_archive,
    memo_thumbnails,
)
from pixelscope.io.memo_folder import metadata_path, save_folder_memo
from pixelscope.io.memo_report import suggested_memo_name
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.review_native_decoder import ENCODED_IMAGE_EXTENSIONS
from pixelscope.io.review_repository import ReviewRepository
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.ui.display_gain import display_gain_state
from pixelscope.ui.memo_report_images import annotate_memo_crop
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar
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
from pixelscope.workers.task_worker import TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool


@dataclass(frozen=True)
class MemoSaveResult:
    revision: str
    report_path: Path
    cleanup_warning: str = ""


def _memo_io(
    operation: str,
    path: Path,
    archive: MemoArchive | None,
    revision: str | None,
) -> object:
    """Worker-only file operations; no coordinator or QObject is retained."""
    if operation == "open":
        if path.suffix.lower() == ".pxreview":
            document, _ = ReviewRepository().load_with_revision(path)
            loaded, version = MemoArchive(document, {}), None
        else:
            loaded, version = load_memo_archive(path)
        return (
            loaded,
            version,
            memo_thumbnails(loaded.crops),
            (path.suffix.lower() == ".pxmemo" and not zipfile.is_zipfile(path)),
        )
    if archive is None:
        raise ValueError("No Memo to save")
    if operation == "save":
        saved = save_folder_memo(path, archive, revision, annotate_memo_crop)
        return MemoSaveResult(saved.revision, path.parent, saved.cleanup_warning)
    raise ValueError("Unknown Memo operation")


class NamedReviewCoordinator:
    """Current-context ROI notes; MainWindow owns all source/view changes."""

    def __init__(self, window: Any) -> None:
        self._window_ref = weakref.ref(window)
        self.library = ReviewLibrary()
        self._folder_mode = False
        self.panel = ReviewPanel()
        self.dock = QDockWidget("Memo", window)
        self.dock.setObjectName("namedReviewDock")
        self.dock.setWidget(self.panel)
        self.panel.setAutoFillBackground(True)
        self.dock.setAutoFillBackground(True)
        self.dock.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._dock_title = PlotsDockTitleBar(
            self.dock, title="Memo", geometry_setting="ui/memo_floating_geometry"
        )
        self.dock.setTitleBarWidget(self._dock_title)
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
        self._crops: dict[tuple[str, str], bytes] = {}
        self._overlay_bindings: dict[str, tuple[str, int]] = {}
        self._thumbnails: dict[tuple[str, str], bytes] = {}
        self._io_worker: TaskWorker | None = None
        self._io_task_id: str | None = None
        self._io_operation = ""
        self._io_path: Path | None = None
        self._io_snapshot: MemoArchive | None = None
        self._closed = False
        self._pending_statistics = False
        self._pending_roi = False
        self._restoring_memo = False
        self._source_context = (
            tuple(window._selection_order)
            + ("page",)
            + tuple(d.document_id for d in window.current_comparison_documents())
        )
        self.action = QAction("Memo", window)
        self.action.setToolTip("Show or hide image inspection notes")
        self.action.setCheckable(True)
        self.action.setShortcut("Ctrl+Shift+M")
        self.action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
        window.addAction(self.action)
        self.dock.addAction(self.action)
        self.action.triggered.connect(self._toggle_visibility)  # type: ignore[attr-defined]
        self.dock.visibilityChanged.connect(self._dock_visibility_changed)  # type: ignore[attr-defined]
        # Keep the W05/W06 critical toolbar footprint unchanged at 960/1400px.
        view_menu = window._menu_map["View"]
        # Use the strongly owned canonical menu; transient QMenu wrappers from
        # QAction.menu() may have lost their native object during Qt composition.
        view_menu.addAction(self.action)

        self.panel.add_requested.connect(self._new_roi)
        self.panel.edit_requested.connect(self.edit)
        self.panel.delete_requested.connect(self.delete)
        self.panel.open_requested.connect(self.open_dialog)
        self.panel.save_requested.connect(self.save_dialog)
        self.panel.finding_changed.connect(self.select_finding)
        self.restore.verification_completed.connect(self._verified)
        self.restore.verification_failed.connect(self._verification_failed)
        self.restore.restore_completed.connect(self._restored)
        self.panel.set_document(self.library.document)
        self.panel.set_dirty(False)
        window.memo_roi_changed.connect(self._new_roi)
        window.memo_sources_changed.connect(self._sources_changed)
        window.comparison_analysis_panel.analysis_settled.connect(self._resume_statistics)
        self.panel.include_statistics.toggled.connect(self._resume_statistics)  # type: ignore[attr-defined]
        # Memo is an optional View dock, not a second workspace layout mode.

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None or window._closing or self._closed:
            raise RuntimeError("Named Finding owner closed")
        return window

    def _sources_changed(self, *_event: object) -> None:
        if self._closed:
            return
        window = self.window
        current = (
            tuple(window._selection_order)
            + ("page",)
            + tuple(d.document_id for d in window.current_comparison_documents())
        )
        if current == self._source_context:
            return
        self._source_context = current
        if (
            self._restoring_memo
            and self.restore.phase in ("committing", "pending")
            and self.authority.matches_committed_selection(tuple(window._selection_order))
        ):
            return
        self._restoring_memo = False
        self.cancel_capture()
        self._pending_roi = False
        self.restore.cancel()
        self.library.reset()
        self._folder_mode = False
        self._approved.clear()
        self._auto_restore_id = None
        self._skip_next_selection_restore = False
        self.authority.review = self.library.document
        self._crops.clear()
        self._overlay_bindings.clear()
        self._thumbnails.clear()
        self.panel.set_document(self.library.document)
        self._clear_editor()
        self.panel.set_dirty(False)
        self.panel.set_status("Images changed — a new ROI memo list")
        self.refresh_overlays()

    def refresh_overlays(self) -> None:
        if self._closed:
            return
        window = self._window_ref()
        if window is None:
            return
        selected = self.panel.selected_finding_id
        for viewer in (window.viewer, *window.multi_compare_view.viewers):
            document = viewer.document
            key = next(
                (
                    key
                    for key, (document_id, generation) in self._overlay_bindings.items()
                    if document is not None
                    and document.document_id == document_id
                    and document.generation == generation
                    and window.documents.get(document_id) is document
                ),
                None,
            )
            regions = []
            if key is not None:
                for ordinal, finding in enumerate(self.library.document.findings, 1):
                    if key in finding.source_keys and finding.roi_ref is not None:
                        title = finding.title.replace("\n", " ")[:48]
                        label = f"ROI {ordinal}"
                        if title and title != label:
                            label += f" · {title}"
                        regions.append((label, RoiBounds(*finding.roi_ref), finding.id == selected))
            viewer.set_memo_regions(tuple(regions))

    def _clear_editor(self) -> None:
        self.panel.findings.blockSignals(True)
        self.panel.findings.setCurrentRow(-1)
        self.panel.findings.blockSignals(False)
        self.panel.title_edit.clear()
        self.panel.note_edit.clear()
        self.panel._tags = ()
        self.panel.evidence_label.setText("Draw an ROI or select an ROI from the list")
        self.panel._set_selection_enabled(False)
        self.panel.show_saved_crops({})

    def _new_roi(self) -> None:
        if self._closed:
            return
        if self._io_worker is not None and self._io_operation == "open":
            return
        if self._io_worker is not None or not self.dock.isVisible():
            self._pending_roi = True
            self.cancel_capture()
            self._clear_editor()
            return
        self._pending_roi = False
        if self.window._shared_roi is None:
            self.panel.set_status("Draw an ROI to add a note")
            return
        self.restore.cancel()
        self._restoring_memo = False
        self._clear_editor()
        self.panel.set_dirty(True)
        self.add()

    def show(self) -> None:
        """Expose the notes dock without silently changing the workspace layout."""
        if self._closed:
            return
        self.dock.show()
        self.dock.raise_()
        if self._pending_roi or (
            not self.library.document.findings and self.window._shared_roi is not None
        ):
            self._new_roi()

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

    def _error(self, message: str) -> None:
        self.panel.set_status(message)

    def cancel_capture(self) -> None:
        self._pending_statistics = False
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
        selected = self.panel.selected_finding_id is not None
        self.panel.title_edit.setEnabled(selected)
        self.panel.note_edit.setEnabled(selected)

    def _wait_for_statistics(self, message: str) -> None:
        self._pending_statistics = True
        self.panel.title_edit.setEnabled(False)
        self.panel.note_edit.setEnabled(False)
        self.panel.set_status(message)

    def _resume_statistics(self, *_event: object) -> None:
        if self._pending_statistics and not self._closed and self._io_worker is None:
            self.add()

    @Slot()
    def add(self) -> None:
        if self._closed:
            return
        self.cancel_capture()
        try:
            window = self.window
            title, note, tags = self.panel.metadata()
            if not title:
                title = f"ROI {len(self.library.document.findings) + 1}"
            if window._shared_roi is None:
                self.panel.set_status("Draw an ROI, then add a memo")
                return
            page = tuple(window.current_comparison_documents())
            if not page:
                raise ReviewValidationError("No comparison sources are selected")
            single = window.central_stack.currentWidget() is window.viewer
            if single:
                visible = window.viewer.document
                if visible is None or visible not in page:
                    raise ReviewValidationError("Show an original image before adding a memo")
                # A single canvas records the image actually being inspected.
                # Keep logical Selected and its Primary slot unchanged.
                page = (visible,)
                if self.panel.include_statistics.isChecked() and len(window.selected_documents) > 1:
                    self._wait_for_statistics(
                        "For ROI Statistics, use Multi View or select only this image; "
                        "uncheck Statistics to record this visible image now"
                    )
                    return
            panel = window.comparison_analysis_panel
            keys = {d.document_id: panel.source_key_for_document(d.document_id) for d in page}
            panel.bind_review_source_keys(keys)
            primary = page[0] if single else window._primary_document_for_page(list(page))
            if primary is None:
                raise ReviewValidationError("Primary source is not available")
            pair = window.difference_panel.selected_documents()
            if pair is not None and all(d.document_id in keys for d in pair):
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
                analysis_panel=panel if self.panel.include_statistics.isChecked() else None,
                # Editable local Memo bookmarks need their exact source paths.
                # Portable HTML exports must explicitly strip these private paths.
                persist_local_paths=True,
                single_viewer=(window.viewer if single else None),
            )
            if self.panel.include_statistics.isChecked() and not any(
                capture.status == "captured" for capture in stage.finding.analysis
            ):
                self._wait_for_statistics("Waiting for ROI Statistics… uncheck to keep images only")
                return
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
            self.panel.title_edit.setEnabled(False)
            self.panel.note_edit.setEnabled(False)
            worker.signals.succeeded.connect(self._capture_succeeded)
            worker.signals.failed.connect(self._capture_failed)
            worker.signals.finished.connect(self._capture_finished)
            analysis_thread_pool().start(worker)
            self.panel.set_status("Capturing ROI images…")
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
            if {key for key, _ in value.crops} != set(value.finding.source_keys):
                raise ReviewValidationError("Ready image previews are required for every ROI crop")
            if any(c.status == "captured" for c in stage.finding.analysis) and not any(
                c.status == "captured" for c in value.finding.analysis
            ):
                raise ReviewValidationError("ROI Statistics changed; retry after Statistics settle")
            title, note, _tags = self.panel.metadata()
            finding = replace(value.finding, title=title or value.finding.title, note=note)
            self.library.add(finding, value.sources)
            self._overlay_bindings.update(
                {item.key: (item.document.document_id, item.generation) for item in value.bindings}
            )
            self.authority.review = self.library.document
            self._crops.update({(value.finding.id, key): data for key, data in value.crops})
            self._thumbnails.update(
                {(value.finding.id, key): data for key, data in value.thumbnails}
            )
            self._skip_next_selection_restore = True
            self.panel.set_document(self.library.document, selected_id=value.finding.id)
            self._show_evidence(value.finding.id)
            self.panel.set_dirty(self.library.dirty)
            self.refresh_overlays()
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
            selected = self.panel.selected_finding_id is not None
            self.panel.title_edit.setEnabled(selected)
            self.panel.note_edit.setEnabled(selected)
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
            self.library.edit(finding_id, title=title or "ROI", note=note, tags=tags)
            self.panel._document = self.library.document
            ordinal = next(
                i for i, f in enumerate(self.library.document.findings) if f.id == finding_id
            )
            item = self.panel.findings.item(ordinal)
            if item is not None:
                item.setText(f"ROI {ordinal + 1} · {title or 'ROI'}")
            self.panel.set_dirty(self.library.dirty)
            self.refresh_overlays()
            self.panel.set_status("Memo updated")
        except (ValueError, KeyError) as exc:
            self._error(str(exc))

    @Slot(str)
    def delete(self, finding_id: str) -> None:
        self.cancel_capture()
        self.restore.cancel()
        try:
            self.library.delete(finding_id)
            self._crops = {key: data for key, data in self._crops.items() if key[0] != finding_id}
            self._thumbnails = {
                key: data for key, data in self._thumbnails.items() if key[0] != finding_id
            }
            self.panel.set_document(self.library.document)
            self._clear_editor()
            self.panel.set_dirty(self.library.dirty)
            self.refresh_overlays()
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
        self._show_evidence(finding_id)
        self.refresh_overlays()
        if self._skip_next_selection_restore:
            self._skip_next_selection_restore = False
            return
        self.cancel_capture()
        self.restore.change_finding(finding_id)
        finding = self.library.get(finding_id)
        window = self.window
        bound = [self._overlay_bindings.get(key) for key in finding.source_keys]
        page = tuple(window.current_comparison_documents())
        if (
            not window._channel_split_active
            and all(pair is not None for pair in bound)
            and tuple(d.document_id for d in page) == tuple(pair[0] for pair in bound if pair)
            and all(
                pair is not None
                and d.generation == pair[1]
                and d.source is not None
                and d.loading_state == "ready"
                for d, pair in zip(page, bound, strict=True)
            )
            and finding.roi_ref is not None
            and window._apply_shared_roi(RoiBounds(*finding.roi_ref), allow_channel_split=False)
        ):
            self.restore.accept_live_selection(finding_id)
            self._restoring_memo = False
            self.panel.set_status("ROI selected — using loaded images")
            self.refresh_overlays()
            return
        self._restoring_memo = True
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
                self._restoring_memo = False
                self.panel.show_missing_images(tuple(missing))
                self.panel.set_status(
                    "Original image unavailable. Saved crops and notes remain readable. "
                    "Open the originals through File if needed."
                )
                return
            self._auto_restore_id = finding_id
            self.verify()
            self.panel.set_status("Opening saved memo and ROI…")
        except (OSError, ValueError, KeyError) as exc:
            self._restoring_memo = False
            self.panel.set_status(f"Memo cannot be reopened: {exc}")

    def open_dialog(self) -> None:
        if self._io_worker is not None:
            self.panel.set_status("Wait for the current Memo file operation")
            return
        chosen, _ = QFileDialog.getOpenFileName(
            self.panel,
            "Open Memo",
            "",
            "PixelScope Memo (*.pxmemo *.pxreview)",
        )
        if not chosen:
            return
        self.cancel_capture()
        self.restore.cancel()
        self._pending_roi = False
        self._start_io("open", Path(chosen).absolute())

    def save_dialog(self) -> None:
        if (
            self._io_worker is not None
            or self._capture_worker is not None
            or self._pending_statistics
        ):
            self.panel.set_status("Wait for the current Memo operation before saving")
            return
        path = self.library.path
        if path is None or path.suffix.lower() != ".pxmemo":
            filename, _ = QFileDialog.getSaveFileName(
                self.panel,
                "Save Memo folder",
                suggested_memo_name(MemoArchive(self.library.document, self._crops)),
                "PixelScope Memo (*.pxmemo)",
            )
            if not filename:
                return
            path = Path(filename).absolute()
            if path.suffix.lower() != ".pxmemo":
                path = path.with_suffix(".pxmemo")
        if not (self._folder_mode and self.library.path == path):
            if self.library.path == path:
                path = path.parent / path.stem / path.name
            else:
                path = metadata_path(path)
        if path.exists() and self.library.path != path:
            self._error("Destination exists; choose another filename or open that Memo first")
            return
        protected = {
            d.source_path.resolve()
            for d in self.window.documents.values()
            if d.source_path is not None
        }
        if path.resolve() in protected:
            self._error("A Memo cannot replace an original image")
            return
        self._start_io("save", path)

    def _show_evidence(self, finding_id: str) -> None:
        self.panel.show_saved_crops(
            {key: data for (fid, key), data in self._thumbnails.items() if fid == finding_id}
        )

    def _start_io(self, operation: str, path: Path) -> None:
        if self._closed or self._io_worker is not None:
            return
        snapshot = MemoArchive(self.library.document, self._crops)
        revision = self.library.revision if self.library.path == path else None
        worker = TaskWorker(_memo_io, operation, path, snapshot, revision)
        self._io_worker = worker
        self._io_task_id = worker.task_id
        self._io_operation = operation
        self._io_path = path
        self._io_snapshot = snapshot
        # Avoid changing notebooks or note content during a file operation. Show
        # the existing evidence while all disk/PNG/HTML work runs off the GUI.
        self.panel.setEnabled(False)
        worker.signals.succeeded.connect(self._io_succeeded)
        worker.signals.failed.connect(self._io_failed)
        worker.signals.finished.connect(self._io_finished)
        analysis_thread_pool().start(worker)
        self.panel.set_status(
            {
                "open": "Opening saved Memo…",
                "save": "Saving notes and ROI images…",
            }[operation]
        )

    @Slot(str, object, int, object)
    def _io_succeeded(self, task_id: str, _doc: object, _epoch: int, result: object) -> None:
        if self._closed or task_id != self._io_task_id:
            return
        path = self._io_path
        snapshot = self._io_snapshot
        if path is None or snapshot is None:
            return
        if self.library.document.document_id != snapshot.review.document_id:
            return  # A later file selection reset this in-memory working context.
        if self._io_operation == "open" and isinstance(result, tuple):
            archive, revision, thumbnails, folder_mode = result
            if not isinstance(archive, MemoArchive):
                return
            self.library.document = archive.review
            self._folder_mode = folder_mode
            self.library.path = path
            self.library.revision = revision
            self.library.dirty = False
            self._crops = dict(archive.crops)
            self._overlay_bindings.clear()
            self.refresh_overlays()
            self._thumbnails = thumbnails
            self.authority.review = archive.review
            self._approved.clear()
            first = archive.review.findings[0].id if archive.review.findings else None
            self.panel.set_document(archive.review, selected_id=first)
            if first is None:
                self.panel.set_status("Memo opened. No saved notes yet.")
        elif self._io_operation == "save" and isinstance(result, MemoSaveResult):
            self._folder_mode = True
            self.library.path = path
            self.library.revision = result.revision
            self.library.dirty = self.library.document is not snapshot.review
            self.panel.show_saved_report(path, result.report_path / "index.html")
            if result.cleanup_warning:
                self.panel.set_status(f"Saved {path.name}. {result.cleanup_warning}")
        self.panel.set_dirty(self.library.dirty, saved=self.library.path is not None)

    @Slot(str, object, int, object)
    def _io_failed(self, task_id: str, _doc: object, _epoch: int, error: object) -> None:
        if not self._closed and task_id == self._io_task_id:
            self.panel.set_status(
                f"Memo {self._io_operation} failed; existing notebook retained: "
                f"{getattr(error, 'message', error)}"
            )

    @Slot(str)
    def _io_finished(self, task_id: str) -> None:
        if task_id == self._io_task_id:
            self._io_worker = None
            self._io_task_id = None
            self._io_snapshot = None
            if not self._closed:
                self.panel.setEnabled(True)
                if self._pending_roi and self.dock.isVisible():
                    self._new_roi()

    def confirm_close(self) -> bool:
        if self._io_worker is not None:
            self.panel.set_status("Wait for the current Memo file operation before closing")
            return False
        return True  # Unwritten ROI notes are temporary for this working context.

    def verify(self) -> None:
        finding_id = self.panel.selected_finding_id
        if finding_id is None:
            return
        try:
            self.restore.verify(finding_id, dict(self._approved))
            self.panel.set_status("Opening the saved ROI…")
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
                    "Original image differs or is unavailable; "
                    "stored ROI evidence remains readable."
                )
            self._auto_restore_id = None
            self._restoring_memo = False

    @Slot(int, str)
    def _verification_failed(self, epoch: int, reason: str) -> None:
        if not self._closed and epoch == self.restore.epoch:
            self._auto_restore_id = None
            self._restoring_memo = False
            self.panel.set_status(f"Memo image could not be opened: {reason}")

    def activate(self, finding_id: str) -> None:
        self._restoring_memo = True
        report = self.restore.activate(finding_id)
        if report.status != "pending":
            self._restoring_memo = False

    @Slot(object)
    def _restored(self, report: object) -> None:
        if isinstance(report, RestoreReport) and not self._closed:
            self._restoring_memo = False
            if report.status == "applied":
                self._overlay_bindings.update(self.authority.memo_overlay_bindings())
            self.refresh_overlays()
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
        self._dock_title.quiesce_pending_callbacks()
        self.restore.shutdown()
        if self._io_worker is not None:
            self._io_worker.cancel()
        self._io_task_id = None
        self._auto_restore_id = None
        self._overlay_bindings.clear()
        self.refresh_overlays()
        self._closed = True
        self.action.setEnabled(False)


def install_named_review(window: Any) -> NamedReviewCoordinator:
    existing = getattr(window, "named_review_coordinator", None)
    if isinstance(existing, NamedReviewCoordinator):
        return existing
    controller = NamedReviewCoordinator(window)
    window.named_review_coordinator = controller
    return controller
