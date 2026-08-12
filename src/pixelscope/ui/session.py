from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from pixelscope.core.comparison_set import Session, SessionDifference, SessionSource
from pixelscope.io.path_discovery import ImageInput, image_input_for_path
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.comparison_set import SessionController as _BaseSessionController
from pixelscope.ui.display_gain import display_gain_state


class SessionController(_BaseSessionController):
    """Transactional Session restore layered on the legacy P4-B bridge."""

    def open_from_path(self, path: str | Path) -> tuple[int, tuple[Path, ...]]:
        session = self.repository.load(path)
        original_ensure_loaded = self.window._ensure_loaded
        ensured_ids: set[str] = set()

        def ensure_loaded_once(document: Any) -> None:
            document_id = str(document.document_id)
            if document_id in ensured_ids:
                return
            ensured_ids.add(document_id)
            original_ensure_loaded(document)

        self.window._ensure_loaded = ensure_loaded_once
        try:
            loaded, missing = self._restore_session(session)
        finally:
            self.window._ensure_loaded = original_ensure_loaded

        if loaded > 0:
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

        # Stage incoming registrations before deleting anything from the current workspace.
        # _register_input() is registration-only here: it does not select or foreground-load.
        path_to_id: dict[str, str] = {}
        for source, image_input in loadable:
            document_id = self.window._register_input(
                image_input,
                resolve_raw_profile=False,
            )
            if document_id is None:
                continue
            path_to_id[source.path.casefold()] = document_id
            if source.raw_profile is not None:
                profile = RawProfile.parse_obj(source.raw_profile)
                self._apply_saved_raw_profile(document_id, profile)

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
        return len(path_to_id), tuple(missing)

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

    def _try_restore_deferred_state(self, *_args: object) -> None:
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
            return
        if recipe.region == "Active ROI" and self._pending_roi is not None:
            return

        a_id = self._pending_path_to_id.get(recipe.image_a_path.casefold())
        b_id = self._pending_path_to_id.get(recipe.image_b_path.casefold())
        if a_id is None or b_id is None:
            self._skip_difference_restore("Saved Difference sources are unavailable.")
            return
        a = self.window.documents.get(a_id)
        b = self.window.documents.get(b_id)
        if a is None or b is None or a.source is None or b.source is None:
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
        panel.calculate_difference()

    def _skip_difference_restore(self, message: str) -> None:
        self._pending_difference = None
        self.window._difference_document = None
        self.window._difference_source_ids = None
        self.window.statusBar().showMessage(f"{message} Difference was not restored.", 5000)


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
