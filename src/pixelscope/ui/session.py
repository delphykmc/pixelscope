from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QProgressBar, QVBoxLayout

from pixelscope.core.comparison_set import Session, SessionDifference, SessionSource
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.io.path_discovery import ImageInput, image_input_for_path
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.comparison_set import SessionController as _BaseSessionController
from pixelscope.ui.display_gain import display_gain_state, is_display_gain_capable


class _SessionRestoreDialog(QDialog):
    """Application-modal progress surface without a nested event loop."""

    def __init__(self, parent: Any) -> None:
        super().__init__(parent)
        self.setObjectName("SessionRestoreDialog")
        self.setWindowTitle("Restoring Session")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(420)

        self.stage = QLabel("Preparing Session…", self)
        self.stage.setObjectName("SessionRestoreStage")
        stage_font = self.stage.font()
        stage_font.setBold(True)
        self.stage.setFont(stage_font)

        self.detail = QLabel("", self)
        self.detail.setObjectName("SessionRestoreDetail")
        self.detail.setWordWrap(True)

        self.progress = QProgressBar(self)
        self.progress.setObjectName("SessionRestoreProgress")
        self.progress.setTextVisible(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        layout.addWidget(self.stage)
        layout.addWidget(self.detail)
        layout.addWidget(self.progress)

    def set_busy(self, stage: str, detail: str = "") -> None:
        self.stage.setText(stage)
        self.detail.setText(detail)
        self.progress.setRange(0, 0)
        self.progress.setFormat("")

    def set_progress(self, stage: str, current: int, total: int, detail: str = "") -> None:
        bounded_total = max(1, total)
        self.stage.setText(stage)
        self.detail.setText(detail)
        self.progress.setRange(0, bounded_total)
        self.progress.setValue(min(max(0, current), bounded_total))
        self.progress.setFormat(f"%v / {total}")

    def reject(self) -> None:
        """Session restore has no partial-rollback Cancel contract in v1."""

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.property("restoreComplete") is True:
            super().closeEvent(event)
            return
        event.ignore()

    def finish(self) -> None:
        self.setProperty("restoreComplete", True)
        self.close()


class SessionController(_BaseSessionController):
    """Transactional Session restore layered on the legacy P4-B bridge."""

    _POLL_INTERVAL_MS = 50
    _DISPLAY_SETTLE_MAX_POLLS = 200

    def __init__(
        self,
        window: Any,
        repository: ComparisonSetRepository | None = None,
    ) -> None:
        self._restore_dialog: _SessionRestoreDialog | None = None
        self._restore_difference_target: tuple[str, str] | None = None
        self._restore_display_poll_count = 0
        super().__init__(window, repository)

    def _connect_deferred_restore_signals(self) -> None:
        """Keep Session restore out of viewer render callbacks.

        The P4-B bridge connects viewer ``document_changed`` signals to deferred
        restoration. For Session restore that is unsafe because ``set_document()``
        emits synchronously while MainWindow is still inside ``_render_selection()``.
        Timer-driven polling below observes the same readiness state only after the
        current Qt call stack has returned, preventing ROI/Line/Difference restore
        from re-entering a foreground render.
        """

    def _begin_restore_feedback(self) -> None:
        previous = self._restore_dialog
        if previous is not None:
            previous.finish()
        dialog = _SessionRestoreDialog(self.window)
        self._restore_dialog = dialog
        dialog.set_busy("Preparing Session…", "Validating saved workspace state")
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _set_restore_busy(self, stage: str, detail: str = "") -> None:
        dialog = self._restore_dialog
        if dialog is not None:
            dialog.set_busy(stage, detail)

    def _set_restore_progress(
        self,
        stage: str,
        current: int,
        total: int,
        detail: str = "",
    ) -> None:
        dialog = self._restore_dialog
        if dialog is not None:
            dialog.set_progress(stage, current, total, detail)

    def _finish_restore_feedback(self, *, delay_ms: int = 120) -> None:
        dialog = self._restore_dialog
        if dialog is None:
            return
        dialog.set_progress("Session restored", 1, 1, "Ready")

        def finish() -> None:
            if self._restore_dialog is not dialog:
                return
            dialog.finish()
            self._restore_dialog = None
            self._restore_difference_target = None

        QTimer.singleShot(delay_ms, finish)

    def _abort_restore_feedback(self) -> None:
        dialog = self._restore_dialog
        if dialog is None:
            return
        dialog.finish()
        self._restore_dialog = None
        self._restore_difference_target = None

    def open_from_path(self, path: str | Path) -> tuple[int, tuple[Path, ...]]:
        session = self.repository.load(path)
        self._begin_restore_feedback()
        try:
            loaded, missing = self._restore_session(session)
        except Exception:
            self._abort_restore_feedback()
            raise
        if loaded == 0:
            self._abort_restore_feedback()
            return loaded, missing
        self._restore_saved_active(session)
        return loaded, missing

    def _restore_session(self, session: Session) -> tuple[int, tuple[Path, ...]]:
        loadable: list[tuple[SessionSource, ImageInput]] = []
        missing: list[Path] = []
        for source in session.registered_sources:
            source_path = Path(source.path)
            image_input = image_input_for_path(source_path)
            if image_input is None:
                missing.append(source_path)
            else:
                loadable.append((source, image_input))

        if not loadable:
            QMessageBox.warning(
                self.window,
                "Session sources unavailable",
                "None of the saved Registered source paths are currently loadable. "
                "The workspace was not changed.",
            )
            return 0, tuple(missing)

        self._set_restore_progress(
            "Registering sources",
            0,
            len(loadable),
            "Reconstructing the saved Registered workspace",
        )

        # Stage incoming registrations before deleting anything from the current workspace.
        # _register_input() is registration-only here: it does not select or foreground-load.
        path_to_id: dict[str, str] = {}
        for index, (source, image_input) in enumerate(loadable, start=1):
            document_id = self.window._register_input(
                image_input,
                resolve_raw_profile=False,
            )
            if document_id is None:
                missing.append(Path(source.path))
            else:
                path_to_id[source.path.casefold()] = document_id
                if source.raw_profile is not None:
                    profile = RawProfile.parse_obj(source.raw_profile)
                    self._apply_saved_raw_profile(document_id, profile)
            self._set_restore_progress(
                "Registering sources",
                index,
                len(loadable),
                image_input.path.name,
            )

        if not path_to_id:
            QMessageBox.warning(
                self.window,
                "Session sources unavailable",
                "None of the saved source paths could be registered. "
                "The workspace was not changed.",
            )
            return 0, tuple(missing)

        # Commit the Registered-workspace replacement only after at least one incoming
        # source has a stable registered identity.
        desired_paths = set(path_to_id)
        remove_ids = [
            document_id
            for document_id, document in self.window.documents.items()
            if document.source_path is None
            or str(document.source_path.resolve(strict=False)).casefold() not in desired_paths
        ]
        if remove_ids:
            self.window._remove_document_ids(remove_ids)
        self.window._update_empty_workspace_state()

        selected_ids = [
            path_to_id[path.casefold()]
            for path in session.selected_paths
            if path.casefold() in path_to_id
        ]
        active_id = self._saved_member_id(session.active_path, path_to_id)
        if selected_ids:
            active_id = active_id if active_id in selected_ids else selected_ids[0]
            self.window._current_index = selected_ids.index(active_id)
            self.window._page_start = 0
        else:
            active_id = None
            self.window._current_index = 0
            self.window._page_start = 0

        self.window._difference_document = None
        self.window._difference_source_ids = None
        self.window._focus_document_id = None
        self.window._primary_page_slot = 0
        self.window._select_document_ids(selected_ids, preserve_view=True)

        if session.layout_mode != self.window._layout_mode:
            self.window.set_layout_mode(session.layout_mode)

        primary_id = self._saved_member_id(session.primary_path, path_to_id)
        current_page_ids = {
            document.document_id for document in self.window.current_comparison_documents()
        }
        if (
            primary_id is not None
            and primary_id in current_page_ids
            and self.window._layout_mode != "Single View"
        ):
            self.window._set_focus_document(primary_id)

        if active_id is not None:
            active_document = self.window.documents.get(active_id)
            if active_document is not None:
                self.window._set_active_document(active_document)

        display_gain_state().set_gain(session.display_gain)
        split_enabled = session.split_channels and len(selected_ids) == 1
        self.window.split_channels_action.setChecked(split_enabled)
        if bool(self.window._split_channels) != split_enabled:
            self.window._set_split_channels(split_enabled)

        self._pending_roi = session.roi
        self._pending_line = session.line
        self._pending_difference = session.difference
        self._pending_path_to_id = path_to_id
        self._establish_difference_dependency(session.difference, path_to_id)
        QTimer.singleShot(0, self._try_restore_deferred_state)
        return len(path_to_id), tuple(dict.fromkeys(missing))

    def _restore_saved_active(self, session: Session) -> None:
        if session.active_path is None:
            return
        active_key = session.active_path.casefold()
        active_document = next(
            (
                document
                for document in self.window.selected_documents
                if document.source_path is not None
                and str(document.source_path.resolve(strict=False)).casefold() == active_key
            ),
            None,
        )
        if active_document is not None:
            self.window._set_active_document(active_document)

    def _establish_difference_dependency(
        self,
        recipe: SessionDifference | None,
        path_to_id: dict[str, str],
    ) -> None:
        if recipe is None:
            return
        a_id = path_to_id.get(recipe.image_a_path.casefold())
        b_id = path_to_id.get(recipe.image_b_path.casefold())
        if a_id is None or b_id is None:
            self._pending_difference = None
            self.window.statusBar().showMessage(
                "Saved Difference sources are unavailable; Difference was not restored.",
                5000,
            )
            return

        self.window._difference_source_ids = (a_id, b_id)
        for document_id in (a_id, b_id):
            document = self.window.documents.get(document_id)
            if document is not None:
                self.window._ensure_loaded(document)

    def _foreground_page_settled(self) -> bool:
        """Keep Session foreground loads live until the Current Page reaches a terminal state."""

        settled = True
        suppressed = self.window._raw_profile_prompt_suppressed
        page = self.window.current_comparison_documents()
        completed = 0
        for document in page:
            if (
                document.source is not None
                or document.loading_state == "error"
                or document.document_id in suppressed
            ):
                completed += 1
                continue
            if document.loading_state == "pending":
                # Native _ensure_loaded() is already state-idempotent. Reissuing only
                # pending work lets Session recover if a render/navigation transition
                # cancelled a foreground worker during restore.
                self.window._ensure_loaded(document)
            if document.source is None and document.loading_state != "error":
                settled = False

        if page:
            self._set_restore_progress(
                "Loading selected images",
                completed,
                len(page),
                "Preparing the Current Comparison Page",
            )
        return settled

    def _try_restore_deferred_state(self, *_args: object) -> None:
        # This method is reached only from QTimer callbacks in the Session controller.
        # Never invoke it from viewer.document_changed: those signals are synchronous
        # inside MainWindow._render_selection() and would re-enter presentation state.
        if not self._foreground_page_settled():
            QTimer.singleShot(self._POLL_INTERVAL_MS, self._try_restore_deferred_state)
            return

        self._set_restore_busy(
            "Restoring ROI and Line Profile",
            "Applying saved analysis selections",
        )
        if self._pending_roi is not None or self._pending_line is not None:
            ready = [
                document
                for document in self.window.current_comparison_documents()
                if document.source is not None
            ]
            if ready:
                if self._pending_roi is not None:
                    self.window._shared_roi_changed(self._pending_roi)
                    self._pending_roi = None
                if self._pending_line is not None:
                    self.window._shared_line_changed(self._pending_line)
                    self._pending_line = None

        recipe = self._pending_difference
        if recipe is None:
            self._begin_finalize_stage()
            return
        if recipe.region == "Active ROI" and self._pending_roi is not None:
            QTimer.singleShot(self._POLL_INTERVAL_MS, self._try_restore_deferred_state)
            return

        a_id = self._pending_path_to_id.get(recipe.image_a_path.casefold())
        b_id = self._pending_path_to_id.get(recipe.image_b_path.casefold())
        if a_id is None or b_id is None:
            self._skip_difference_restore("Saved Difference sources are unavailable.")
            return
        a = self.window.documents.get(a_id)
        b = self.window.documents.get(b_id)
        if a is None or b is None:
            self._skip_difference_restore("Saved Difference sources are unavailable.")
            return
        if a.source is None or b.source is None:
            if a.loading_state == "error" or b.loading_state == "error":
                self._skip_difference_restore("A saved Difference source failed to load.")
                return
            suppressed = self.window._raw_profile_prompt_suppressed
            if a_id in suppressed or b_id in suppressed:
                self._skip_difference_restore(
                    "A saved Difference RAW source was not resolved."
                )
                return
            self._set_restore_busy(
                "Loading Difference sources",
                "Preparing the saved Difference pair",
            )
            for document in (a, b):
                if document.source is None and document.loading_state == "pending":
                    self.window._ensure_loaded(document)
            QTimer.singleShot(self._POLL_INTERVAL_MS, self._try_restore_deferred_state)
            return

        panel = self.window.difference_panel
        panel.set_documents([a, b], (a_id, b_id), self.window._shared_roi)

        channel_index = panel.channel.findText(recipe.channel)
        if channel_index < 0:
            self._skip_difference_restore(
                f"Saved Difference channel {recipe.channel!r} is not available for this pair."
            )
            return
        mode_index = panel.mode.findText(recipe.mode)
        region_index = panel.region.findText(recipe.region)
        if mode_index < 0 or region_index < 0:
            self._skip_difference_restore("Saved Difference options are no longer available.")
            return
        if not panel.threshold.minimum() <= recipe.threshold <= panel.threshold.maximum():
            self._skip_difference_restore(
                "Saved Difference threshold is not valid for the reconstructed pair."
            )
            return

        panel.a_selector.setCurrentIndex(panel.a_selector.findData(a_id))
        panel.b_selector.setCurrentIndex(panel.b_selector.findData(b_id))
        panel.channel.setCurrentIndex(channel_index)
        panel.mode.setCurrentIndex(mode_index)
        panel.region.setCurrentIndex(region_index)
        panel.threshold.setValue(recipe.threshold)
        panel.gain.setValue(recipe.gain)
        self._pending_difference = None
        self._restore_difference_target = (a_id, b_id)
        self._set_restore_busy(
            "Recalculating Difference",
            f"{a.display_name} vs {b.display_name}",
        )
        panel.calculate_difference()
        if panel._worker is None:
            # Focused tests may replace calculate_difference with a synchronous observer.
            self._begin_finalize_stage()
            return
        QTimer.singleShot(self._POLL_INTERVAL_MS, self._poll_difference_restore)

    def _poll_difference_restore(self) -> None:
        target = self._restore_difference_target
        difference = self.window._difference_document
        source_ids = self.window._difference_source_ids
        if target is not None and difference is not None and source_ids == target:
            self._begin_finalize_stage()
            return

        panel = self.window.difference_panel
        if panel._worker is None:
            if panel.status.text() == "Calculation failed":
                self._skip_difference_restore("Saved Difference calculation failed.")
            else:
                self._begin_finalize_stage()
            return
        QTimer.singleShot(self._POLL_INTERVAL_MS, self._poll_difference_restore)

    def _begin_finalize_stage(self) -> None:
        self._restore_display_poll_count = 0
        self._set_restore_busy(
            "Applying display state",
            "Finalizing layout, Active/Primary state, and Display Gain",
        )
        QTimer.singleShot(0, self._poll_display_state)

    def _display_state_settled(self) -> bool:
        # Hidden test windows intentionally do not launch viewer-only display workers.
        if not self.window.isVisible():
            return True
        gain = display_gain_state().gain
        if gain == 1.0:
            return True

        current = self.window.central_stack.currentWidget()
        if current is self.window.viewer:
            viewers = [self.window.viewer]
        elif current is self.window.multi_compare_view:
            viewers = list(self.window.multi_compare_view.occupied_viewers)
        else:
            viewers = []

        for viewer in viewers:
            document = viewer.presented_document
            if not is_display_gain_capable(document):
                continue
            if viewer._display_preview_worker is not None or viewer._displayed_gain != gain:
                return False
        return True

    def _poll_display_state(self) -> None:
        if self._display_state_settled():
            self._finish_restore_feedback()
            return
        self._restore_display_poll_count += 1
        if self._restore_display_poll_count >= self._DISPLAY_SETTLE_MAX_POLLS:
            self.window.statusBar().showMessage(
                "Session restored; Display Gain preview is still updating.",
                5000,
            )
            self._finish_restore_feedback()
            return
        QTimer.singleShot(self._POLL_INTERVAL_MS, self._poll_display_state)

    def _skip_difference_restore(self, message: str) -> None:
        self._pending_difference = None
        self._restore_difference_target = None
        self.window._difference_document = None
        self.window._difference_source_ids = None
        self.window.statusBar().showMessage(f"{message} Difference was not restored.", 5000)
        self._begin_finalize_stage()


class _ComparisonSetControllerFacade:
    """Preserve P4-B internal API semantics while product/runtime ownership moves to Session."""

    def __init__(self, controller: SessionController) -> None:
        self._controller = controller

    def __getattr__(self, name: str) -> Any:
        return getattr(self._controller, name)

    def open_from_path(self, path: str | Path) -> tuple[int, tuple[Path, ...]]:
        loaded, missing = self._controller.open_from_path(path)
        if loaded == 0:
            return 0, missing
        return len(self._controller.window.selected_documents), missing


def install_session(window: Any) -> SessionController:
    existing = getattr(window, "session_controller", None)
    if isinstance(existing, SessionController):
        return existing
    controller = SessionController(window)
    window.session_controller = controller
    window.comparison_set_controller = _ComparisonSetControllerFacade(controller)
    return controller
