from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from pixelscope.core.comparison_set import Session
from pixelscope.io.path_discovery import image_input_for_path
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.comparison_set import SessionController as _BaseSessionController
from pixelscope.ui.display_gain import display_gain_state, is_display_gain_capable
from pixelscope.ui.session_restore_overlay import SessionRestoreOverlay

LOGGER = logging.getLogger(__name__)


class SessionController(_BaseSessionController):
    """Transactional Session open adapted to the merged PR #33 Difference lifecycle."""

    def _connect_deferred_restore_signals(self) -> None:
        # One window-owned timer keeps restore out of synchronous viewer callbacks,
        # coalesces retries, and dies automatically with the MainWindow.
        self._restore_timer = QTimer(self.window)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(  # type: ignore[attr-defined]
            self._try_restore_deferred_state
        )
        self._restore_overlay = SessionRestoreOverlay(self.window)
        self._pending_primary_id: str | None = None
        self._pending_active_id: str | None = None
        self._pending_display_gain: float | None = None
        self._pending_split_channels: bool | None = None
        self._display_restore_applied = False
        self._difference_restore_in_flight = False
        self.window.difference_panel.result_ready.connect(
            self._difference_restore_completed
        )

    def _schedule_restore(self, delay_ms: int) -> None:
        if getattr(self.window, "_closing", False):
            return
        self._restore_timer.start(max(0, delay_ms))

    def _progress_begin(self, detail: str) -> None:
        try:
            self._restore_overlay.begin(detail)
        except Exception:  # noqa: BLE001 - progress is a best-effort observer
            LOGGER.warning("Unable to show Session restore progress", exc_info=True)

    def _progress_update(self, step: int, fraction: float, detail: str) -> None:
        try:
            self._restore_overlay.update_progress(step, fraction, detail)
        except Exception:  # noqa: BLE001 - progress cannot break canonical restore
            LOGGER.warning("Unable to update Session restore progress", exc_info=True)

    def _progress_finish(self, detail: str = "Session restored") -> None:
        try:
            self._restore_overlay.finish(detail)
        except Exception:  # noqa: BLE001 - progress cannot break canonical restore
            LOGGER.warning("Unable to finish Session restore progress", exc_info=True)

    def _progress_abort(self) -> None:
        try:
            self._restore_overlay.abort()
        except Exception:  # noqa: BLE001 - progress cannot change restore failure
            LOGGER.warning("Unable to close Session restore progress", exc_info=True)

    def open_from_path(self, path: str | Path) -> tuple[int, tuple[Path, ...]]:
        target = Path(path)
        self._progress_begin(f"Reading and validating {target.name}")
        try:
            session = self.repository.load(target)
        except Exception:
            self._progress_abort()
            raise
        self._progress_update(1, 1.0, "Session validated")
        return self._restore(session)

    def _restore(self, session: Session) -> tuple[int, tuple[Path, ...]]:
        self._restore_timer.stop()
        self._pending_primary_id = None
        self._pending_active_id = None
        self._pending_display_gain = None
        self._pending_split_channels = None
        self._display_restore_applied = False
        self._difference_restore_in_flight = False

        loadable = []
        missing: list[Path] = []
        source_count = len(session.registered_sources)
        self._progress_update(2, 0.0, f"Checking source paths · 0 / {source_count}")
        for index, source in enumerate(session.registered_sources, start=1):
            image_input = image_input_for_path(Path(source.path))
            if image_input is None:
                missing.append(Path(source.path))
            else:
                loadable.append((source, image_input))
            self._progress_update(
                2,
                0.5 * index / max(1, source_count),
                f"Checking source paths · {index} / {source_count}",
            )
        if not loadable:
            self._progress_update(2, 1.0, "No saved source is currently available")
            self._progress_abort()
            QMessageBox.warning(
                self.window,
                "Session sources unavailable",
                "None of the saved Registered source paths are currently loadable. "
                "The workspace was not changed.",
            )
            return 0, tuple(missing)

        path_to_id: dict[str, str] = {}
        loadable_count = len(loadable)
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
                    self._apply_saved_raw_profile(
                        document_id,
                        RawProfile.parse_obj(source.raw_profile),
                    )
            self._progress_update(
                2,
                0.5 + 0.5 * index / max(1, loadable_count),
                f"Registered {len(path_to_id)} / {loadable_count} available source(s)",
            )
        if not path_to_id:
            self._progress_abort()
            QMessageBox.warning(
                self.window,
                "Session sources unavailable",
                "None of the saved source paths could be registered. "
                "The workspace was not changed.",
            )
            return 0, tuple(dict.fromkeys(missing))
        self._progress_update(
            2,
            1.0,
            f"Registered {len(path_to_id)} source(s)",
        )

        self._progress_update(3, 0.0, "Restoring Selected, page, and layout")
        self._reset_active_difference()
        self._clear_picks()
        desired = set(path_to_id)
        remove_ids = [
            document_id
            for document_id, document in self.window.documents.items()
            if document.source_path is None
            or str(document.source_path.resolve(strict=False)).casefold() not in desired
        ]
        if remove_ids:
            self.window._remove_document_ids(remove_ids)
        self.window._update_empty_workspace_state()

        selected_ids = [
            path_to_id[path.casefold()]
            for path in session.selected_paths
            if path.casefold() in path_to_id
        ]
        page_anchor_id = self._saved_member_id(session.page_anchor_path, path_to_id)
        active_id = self._saved_member_id(session.active_path, path_to_id)
        if selected_ids:
            if page_anchor_id not in selected_ids:
                page_anchor_id = active_id if active_id in selected_ids else selected_ids[0]
            assert page_anchor_id is not None
            self.window._current_index = selected_ids.index(page_anchor_id)
        else:
            page_anchor_id = None
            active_id = None
            self.window._current_index = 0
        self.window._page_start = 0
        self.window._focus_document_id = None
        self.window._primary_page_slot = 0
        self.window._select_document_ids(selected_ids, preserve_view=True)

        if session.layout_mode != self.window._layout_mode:
            self.window.set_layout_mode(session.layout_mode)

        page_ids = {
            document.document_id
            for document in self.window.current_comparison_documents()
        }
        primary_id = self._saved_member_id(session.primary_path, path_to_id)
        self._pending_primary_id = (
            primary_id
            if primary_id is not None
            and primary_id in page_ids
            and self.window._layout_mode != "Single View"
            else None
        )
        self._pending_active_id = active_id if active_id in page_ids else None
        self._pending_display_gain = session.display_gain
        self._pending_split_channels = session.split_channels
        self._pending_roi = session.roi
        self._pending_line = session.line
        self._pending_difference = session.difference
        self._pending_path_to_id = path_to_id

        # Primary/Active are durable workspace state, not deferred analysis state.
        # Establish them before open_from_path() returns so the canonical P4-B
        # synchronous contract remains intact. Async display/Difference work may
        # transiently disturb presentation, so Step 8 re-applies them as the final
        # presentation commit.
        self._restore_saved_source_presentation()

        page_total = max(1, (len(selected_ids) + 5) // 6)
        page_number = self.window._page_start // 6 + 1 if selected_ids else 0
        page_detail = (
            f"Selected {len(selected_ids)} · Comparison Page {page_number} / {page_total}"
            if selected_ids
            else "No saved Selected images"
        )
        self._progress_update(3, 1.0, page_detail)
        current_count = len(self.window.current_comparison_documents())
        self._progress_update(
            4,
            0.0,
            f"0 / {current_count} images ready" if current_count else "No images to load",
        )
        self._schedule_restore(0)
        return len(path_to_id), tuple(dict.fromkeys(missing))

    def _reset_active_difference(self) -> None:
        lifecycle = getattr(self.window, "difference_curation_lifecycle", None)
        reset = getattr(lifecycle, "_reset_active_difference", None)
        if callable(reset):
            reset()
            return
        self.window._difference_document = None
        self.window._difference_source_ids = None
        action = getattr(self.window, "diff_action", None)
        if action is not None:
            action.blockSignals(True)
            action.setChecked(False)
            action.setEnabled(False)
            action.blockSignals(False)

    def _clear_picks(self) -> None:
        controller = getattr(self.window, "review_selection_controller", None)
        state = getattr(controller, "state", None)
        exit_state = getattr(state, "exit", None)
        if callable(exit_state):
            exit_state()
        sync = getattr(controller, "_sync_all", None)
        if callable(sync):
            sync()

    def _restore_saved_source_presentation(self) -> None:
        primary_id = self._pending_primary_id
        if primary_id is not None:
            page_ids = {
                document.document_id
                for document in self.window.current_comparison_documents()
            }
            if primary_id in page_ids and self.window._layout_mode != "Single View":
                self.window._set_focus_document(primary_id)

        active_id = self._pending_active_id
        if active_id is None:
            return
        document = self.window.documents.get(active_id)
        if document is not None:
            self.window._set_active_document(document)

    def _clear_pending_source_presentation(self) -> None:
        self._pending_primary_id = None
        self._pending_active_id = None

    def _foreground_page_progress(self) -> tuple[bool, list[Any]]:
        page = self.window.current_comparison_documents()
        if not page:
            self._progress_update(4, 1.0, "No images to load")
            return True, []

        ready: list[Any] = []
        terminal_count = 0
        unavailable_count = 0
        suppressed = self.window._raw_profile_prompt_suppressed
        for document in page:
            if document.source is not None:
                ready.append(document)
                terminal_count += 1
                continue
            if document.loading_state == "error" or document.document_id in suppressed:
                terminal_count += 1
                unavailable_count += 1
                continue
            if document.loading_state == "pending":
                self.window._ensure_loaded(document)

        detail = f"{len(ready)} / {len(page)} images ready"
        if unavailable_count:
            detail += f" · {unavailable_count} unavailable"
        self._progress_update(4, terminal_count / len(page), detail)
        return terminal_count == len(page), ready

    def _apply_display_restore(self) -> None:
        if self._display_restore_applied:
            return
        gain = self._pending_display_gain if self._pending_display_gain is not None else 1.0
        split_saved = bool(self._pending_split_channels)
        self._progress_update(5, 0.0, "Applying Display Gain and Split Channels")
        display_gain_state().set_gain(gain)
        split_enabled = split_saved and len(self.window.selected_documents) == 1
        self.window.split_channels_action.setChecked(split_enabled)
        if bool(self.window._split_channels) != split_enabled:
            self.window._set_split_channels(split_enabled)
        self._display_restore_applied = True
        self._pending_display_gain = None
        self._pending_split_channels = None

    def _display_preview_progress(self) -> tuple[bool, str, float]:
        gain = display_gain_state().gain
        if self.window.central_stack.currentWidget() is self.window.multi_compare_view:
            viewers = self.window.multi_compare_view.occupied_viewers
        else:
            viewers = [self.window.viewer]
        applicable = []
        pending = 0
        for viewer in viewers:
            document = viewer.presented_document
            if document is None or not is_display_gain_capable(document):
                continue
            applicable.append(viewer)
            if gain != 1.0 and getattr(viewer, "_display_preview_worker", None) is not None:
                pending += 1
        if not applicable or gain == 1.0:
            return True, f"Display Gain {gain:g}× applied", 1.0
        completed = len(applicable) - pending
        detail = f"Display Gain {gain:g}× · {completed} / {len(applicable)} previews ready"
        return pending == 0, detail, completed / len(applicable)

    def _restore_analysis_state(self, ready: list[Any]) -> bool:
        has_roi = self._pending_roi is not None
        has_line = self._pending_line is not None
        if not ready:
            had_analysis = has_roi or has_line
            self._pending_roi = None
            self._pending_line = None
            detail = (
                "Saved ROI/Line skipped · restored page has no usable image"
                if had_analysis
                else "No saved ROI or Line"
            )
            self._progress_update(6, 1.0, detail)
            return False

        intents = int(has_roi) + int(has_line)
        if intents == 0:
            self._progress_update(6, 1.0, "No saved ROI or Line")
            return True

        completed = 0
        self._progress_update(6, 0.0, "Restoring saved analysis overlays")
        if self._pending_roi is not None:
            self.window._shared_roi_changed(self._pending_roi)
            self._pending_roi = None
            completed += 1
            self._progress_update(6, completed / intents, "ROI restored")
        if self._pending_line is not None:
            self.window._shared_line_changed(self._pending_line)
            self._pending_line = None
            completed += 1
            self._progress_update(6, completed / intents, "Line restored")
        return True

    def _try_restore_deferred_state(self, *_args: object) -> None:
        if getattr(self.window, "_closing", False):
            self._pending_roi = None
            self._pending_line = None
            self._pending_difference = None
            self._pending_display_gain = None
            self._pending_split_channels = None
            self._clear_pending_source_presentation()
            self._difference_restore_in_flight = False
            self._progress_abort()
            return

        if self._difference_restore_in_flight:
            panel = self.window.difference_panel
            worker = getattr(panel, "_worker", None)
            preview_worker = getattr(panel, "_preview_worker", None)
            self._progress_update(7, 0.65, panel.status.text() or "Rebuilding Difference")
            if worker is None and preview_worker is None:
                self._difference_restore_in_flight = False
                self.window.statusBar().showMessage(
                    "Saved Difference could not be rebuilt.",
                    5000,
                )
                self._progress_update(7, 1.0, "Difference was not restored")
                self._finalize_restore("Session restored · Difference skipped")
                return
            self._schedule_restore(50)
            return

        settled, ready = self._foreground_page_progress()
        if not settled:
            self._schedule_restore(50)
            return
        self._progress_update(4, 1.0, self._current_page_ready_detail(ready))

        self._apply_display_restore()
        display_settled, display_detail, display_fraction = self._display_preview_progress()
        self._progress_update(5, display_fraction, display_detail)
        if not display_settled:
            self._schedule_restore(50)
            return
        self._progress_update(5, 1.0, display_detail)

        analysis_available = self._restore_analysis_state(ready)
        recipe = self._pending_difference
        if recipe is None:
            self._progress_update(7, 1.0, "No saved Difference recipe")
            self._finalize_restore()
            return
        if not analysis_available and recipe.region == "Active ROI":
            self._skip_difference("Saved Active ROI is unavailable on the restored page.")
            return
        if recipe.region == "Active ROI" and self.window._shared_roi is None:
            self._skip_difference("Saved Active ROI is unavailable on the restored page.")
            return

        self._progress_update(7, 0.0, "Preparing saved Difference pair")
        a_id = self._pending_path_to_id.get(recipe.image_a_path.casefold())
        b_id = self._pending_path_to_id.get(recipe.image_b_path.casefold())
        if a_id is None or b_id is None:
            self._skip_difference("Saved Difference sources are unavailable.")
            return

        current_page = self.window.current_comparison_documents()
        page_ids = {document.document_id for document in current_page}
        if a_id not in page_ids or b_id not in page_ids:
            self._skip_difference(
                "Saved Difference pair is not part of the restored Comparison Page."
            )
            return

        a = self.window.documents.get(a_id)
        b = self.window.documents.get(b_id)
        if a is None or b is None:
            self._skip_difference("Saved Difference sources are unavailable.")
            return
        if a.source is None or b.source is None:
            if a.loading_state == "error" or b.loading_state == "error":
                self._skip_difference("A saved Difference source failed to load.")
            else:
                self._skip_difference("A saved Difference source is unavailable.")
            return

        panel = self.window.difference_panel
        panel.set_documents(current_page, (a_id, b_id), self.window._shared_roi)
        a_index = panel.a_selector.findData(a_id)
        b_index = panel.b_selector.findData(b_id)
        if a_index < 0 or b_index < 0:
            self._skip_difference("Saved Difference pair is unavailable on the restored page.")
            return

        channel_index = panel.channel.findText(recipe.channel)
        mode_index = panel.mode.findText(recipe.mode)
        region_index = panel.region.findText(recipe.region)
        if channel_index < 0 or mode_index < 0 or region_index < 0:
            self._skip_difference(
                "Saved Difference options are not available for this pair."
            )
            return
        if not panel.threshold.minimum() <= recipe.threshold <= panel.threshold.maximum():
            self._skip_difference(
                "Saved Difference threshold is invalid for this pair."
            )
            return

        panel.a_selector.setCurrentIndex(a_index)
        panel.b_selector.setCurrentIndex(b_index)
        panel.channel.setCurrentIndex(channel_index)
        panel.mode.setCurrentIndex(mode_index)
        panel.region.setCurrentIndex(region_index)
        panel.threshold.setValue(recipe.threshold)
        panel.gain.setValue(recipe.gain)
        self._pending_difference = None
        self._difference_restore_in_flight = True
        self._progress_update(7, 0.5, "Calculating saved Difference")
        # PR #33: Calculate, not Session restore, establishes active Difference binding.
        panel.calculate_difference()
        if self._difference_restore_in_flight:
            self._schedule_restore(50)

    def _current_page_ready_detail(self, ready: list[Any]) -> str:
        total = len(self.window.current_comparison_documents())
        if total == 0:
            return "No images to load"
        unavailable = total - len(ready)
        detail = f"{len(ready)} / {total} images ready"
        if unavailable:
            detail += f" · {unavailable} unavailable"
        return detail

    def _difference_restore_completed(self, *_args: object) -> None:
        if not self._difference_restore_in_flight:
            return
        self._difference_restore_in_flight = False
        self._restore_timer.stop()
        self._progress_update(7, 1.0, "Difference rebuilt")
        self._finalize_restore()

    def _finalize_restore(self, detail: str = "Session restored") -> None:
        self._progress_update(8, 0.0, "Restoring saved Primary and Active")
        self._restore_saved_source_presentation()
        self._clear_pending_source_presentation()
        self._progress_update(8, 1.0, detail)
        self._progress_finish(detail)

    def _skip_difference(self, message: str) -> None:
        self._pending_difference = None
        self._difference_restore_in_flight = False
        self.window.statusBar().showMessage(
            f"{message} Difference was not restored.",
            5000,
        )
        self._progress_update(7, 1.0, f"{message} Difference skipped")
        self._finalize_restore("Session restored · Difference skipped")


class _ComparisonSetControllerFacade:
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
