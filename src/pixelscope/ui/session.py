from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from pixelscope.core.comparison_set import Session, SessionDifference
from pixelscope.io.path_discovery import image_input_for_path
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.comparison_set import SessionController as _BaseSessionController
from pixelscope.ui.display_gain import display_gain_state


class SessionController(_BaseSessionController):
    """Transactional Session open adapted to the merged PR #33 Difference lifecycle."""

    def _connect_deferred_restore_signals(self) -> None:
        # Session restore is timer-driven so it cannot re-enter _render_selection()
        # from ImageViewer.document_changed.
        return

    def open_from_path(self, path: str | Path) -> tuple[int, tuple[Path, ...]]:
        session = self.repository.load(path)
        return self._restore(session)

    def _restore(self, session: Session) -> tuple[int, tuple[Path, ...]]:
        loadable = []
        missing: list[Path] = []
        for source in session.registered_sources:
            image_input = image_input_for_path(Path(source.path))
            if image_input is None:
                missing.append(Path(source.path))
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

        path_to_id: dict[str, str] = {}
        for source, image_input in loadable:
            document_id = self.window._register_input(image_input, resolve_raw_profile=False)
            if document_id is None:
                missing.append(Path(source.path))
                continue
            path_to_id[source.path.casefold()] = document_id
            if source.raw_profile is not None:
                self._apply_saved_raw_profile(
                    document_id,
                    RawProfile.parse_obj(source.raw_profile),
                )
        if not path_to_id:
            QMessageBox.warning(
                self.window,
                "Session sources unavailable",
                "None of the saved source paths could be registered. "
                "The workspace was not changed.",
            )
            return 0, tuple(dict.fromkeys(missing))

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
        active_id = self._saved_member_id(session.active_path, path_to_id)
        if selected_ids:
            active_id = active_id if active_id in selected_ids else selected_ids[0]
            self.window._current_index = selected_ids.index(active_id)
        else:
            active_id = None
            self.window._current_index = 0
        self.window._page_start = 0
        self.window._focus_document_id = None
        self.window._primary_page_slot = 0
        self.window._select_document_ids(selected_ids, preserve_view=True)

        if session.layout_mode != self.window._layout_mode:
            self.window.set_layout_mode(session.layout_mode)
        primary_id = self._saved_member_id(session.primary_path, path_to_id)
        page_ids = {doc.document_id for doc in self.window.current_comparison_documents()}
        if (
            primary_id is not None
            and primary_id in page_ids
            and self.window._layout_mode != "Single View"
        ):
            self.window._set_focus_document(primary_id)
        if active_id is not None and (active := self.window.documents.get(active_id)) is not None:
            self.window._set_active_document(active)

        display_gain_state().set_gain(session.display_gain)
        split_enabled = session.split_channels and len(selected_ids) == 1
        self.window.split_channels_action.setChecked(split_enabled)
        if bool(self.window._split_channels) != split_enabled:
            self.window._set_split_channels(split_enabled)

        self._pending_roi = session.roi
        self._pending_line = session.line
        self._pending_difference = session.difference
        self._pending_path_to_id = path_to_id
        self._request_difference_sources(session.difference, path_to_id)
        QTimer.singleShot(0, self._try_restore_deferred_state)
        return len(path_to_id), tuple(dict.fromkeys(missing))

    def _reset_active_difference(self) -> None:
        lifecycle = getattr(self.window, "difference_curation_lifecycle", None)
        reset = getattr(lifecycle, "_reset_active_difference", None)
        if callable(reset):
            reset()
            return
        self.window._difference_document = None
        self.window._difference_source_ids = None

    def _clear_picks(self) -> None:
        controller = getattr(self.window, "review_selection_controller", None)
        state = getattr(controller, "state", None)
        exit_state = getattr(state, "exit", None)
        if callable(exit_state):
            exit_state()
        sync = getattr(controller, "_sync_all", None)
        if callable(sync):
            sync()

    def _request_difference_sources(
        self,
        recipe: SessionDifference | None,
        path_to_id: dict[str, str],
    ) -> None:
        if recipe is None:
            return
        source_ids = (
            path_to_id.get(recipe.image_a_path.casefold()),
            path_to_id.get(recipe.image_b_path.casefold()),
        )
        if None in source_ids:
            self._skip_difference("Saved Difference sources are unavailable.")
            return
        for document_id in source_ids:
            document = self.window.documents.get(document_id)
            if document is not None:
                self.window._ensure_loaded(document)

    def _foreground_page_settled(self) -> bool:
        settled = True
        suppressed = self.window._raw_profile_prompt_suppressed
        for document in self.window.current_comparison_documents():
            if document.source is not None or document.loading_state == "error":
                continue
            if document.document_id in suppressed:
                continue
            if document.loading_state == "pending":
                self.window._ensure_loaded(document)
            settled = False
        return settled

    def _try_restore_deferred_state(self, *_args: object) -> None:
        if not self._foreground_page_settled():
            QTimer.singleShot(50, self._try_restore_deferred_state)
            return

        ready = [doc for doc in self.window.current_comparison_documents() if doc.source is not None]
        if ready:
            if self._pending_roi is not None:
                self.window._shared_roi_changed(self._pending_roi)
                self._pending_roi = None
            if self._pending_line is not None:
                self.window._shared_line_changed(self._pending_line)
                self._pending_line = None

        recipe = self._pending_difference
        if recipe is None:
            return
        if recipe.region == "Active ROI" and self._pending_roi is not None:
            QTimer.singleShot(50, self._try_restore_deferred_state)
            return
        a_id = self._pending_path_to_id.get(recipe.image_a_path.casefold())
        b_id = self._pending_path_to_id.get(recipe.image_b_path.casefold())
        if a_id is None or b_id is None:
            self._skip_difference("Saved Difference sources are unavailable.")
            return
        a = self.window.documents.get(a_id)
        b = self.window.documents.get(b_id)
        if a is None or b is None:
            self._skip_difference("Saved Difference sources are unavailable.")
            return
        if a.source is None or b.source is None:
            if a.loading_state == "error" or b.loading_state == "error":
                self._skip_difference("A saved Difference source failed to load.")
                return
            suppressed = self.window._raw_profile_prompt_suppressed
            if a_id in suppressed or b_id in suppressed:
                self._skip_difference("A saved Difference RAW source was not resolved.")
                return
            for document in (a, b):
                if document.source is None and document.loading_state == "pending":
                    self.window._ensure_loaded(document)
            QTimer.singleShot(50, self._try_restore_deferred_state)
            return

        panel = self.window.difference_panel
        panel.set_documents([a, b], (a_id, b_id), self.window._shared_roi)
        channel_index = panel.channel.findText(recipe.channel)
        mode_index = panel.mode.findText(recipe.mode)
        region_index = panel.region.findText(recipe.region)
        if channel_index < 0 or mode_index < 0 or region_index < 0:
            self._skip_difference("Saved Difference options are not available for this pair.")
            return
        if not panel.threshold.minimum() <= recipe.threshold <= panel.threshold.maximum():
            self._skip_difference("Saved Difference threshold is invalid for this pair.")
            return
        panel.a_selector.setCurrentIndex(panel.a_selector.findData(a_id))
        panel.b_selector.setCurrentIndex(panel.b_selector.findData(b_id))
        panel.channel.setCurrentIndex(channel_index)
        panel.mode.setCurrentIndex(mode_index)
        panel.region.setCurrentIndex(region_index)
        panel.threshold.setValue(recipe.threshold)
        panel.gain.setValue(recipe.gain)
        self._pending_difference = None
        # PR #33: Calculate, not Session restore, establishes active Difference binding.
        panel.calculate_difference()

    def _skip_difference(self, message: str) -> None:
        self._pending_difference = None
        self.window.statusBar().showMessage(f"{message} Difference was not restored.", 5000)


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
