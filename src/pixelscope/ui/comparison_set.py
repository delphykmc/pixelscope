from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

from pixelscope.core.comparison_set import (
    ComparisonSetError,
    Session,
    SessionDifference,
    SessionSource,
)
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.io.path_discovery import ImageInput, image_input_for_path
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.design_tokens import menu_style
from pixelscope.ui.display_gain import display_gain_state

LOGGER = logging.getLogger(__name__)
SESSION_FILTER = "PixelScope Session (*.pixelscope)"


class SessionController:
    """Bridge durable Session artifacts to existing MainWindow runtime authorities."""

    def __init__(
        self,
        window: Any,
        repository: ComparisonSetRepository | None = None,
    ) -> None:
        self.window = window
        self.repository = repository or ComparisonSetRepository()
        self._recent_entry_callback: Callable[[Path], None] | None = None
        self._pending_roi: object | None = None
        self._pending_line: object | None = None
        self._pending_difference: SessionDifference | None = None
        self._pending_path_to_id: dict[str, str] = {}

        self.open_action = QAction("Open Session...", window)
        self.save_action = QAction("Save Session...", window)
        self.open_action.setToolTip("Open a saved PixelScope workspace session")
        self.save_action.setToolTip(
            "Save Registered files, Selected workspace state, ROI/Line and regenerable "
            "presentation intent. Runtime caches and workers are not saved."
        )
        self.open_action.triggered.connect(self.open_dialog)  # type: ignore[attr-defined]
        self.save_action.triggered.connect(self.save_dialog)  # type: ignore[attr-defined]
        self._install_file_menu_actions()
        self._connect_deferred_restore_signals()

    def set_recent_entry_callback(
        self,
        callback: Callable[[Path], None] | None,
    ) -> None:
        self._recent_entry_callback = callback

    def _notify_recent_entry(self, path: Path) -> None:
        if self._recent_entry_callback is None:
            return
        try:
            self._recent_entry_callback(path.resolve(strict=False))
        except Exception:  # noqa: BLE001 - optional observer cannot break Session workflows
            LOGGER.warning("Unable to update Recent Session history", exc_info=True)

    def _connect_deferred_restore_signals(self) -> None:
        for viewer in [self.window.viewer, *self.window.multi_compare_view.viewers]:
            viewer.document_changed.connect(self._try_restore_deferred_state)

    def _file_menu(self) -> QMenu:
        menu_bar = self.window.menuBar()
        for action in menu_bar.actions():
            if action.text().replace("&", "") == "File":
                return self._replace_file_menu(action)
        raise RuntimeError("Session commands require the File menu")

    def _replace_file_menu(self, stale_action: QAction) -> QMenu:
        menu_bar = self.window.menuBar()
        top_level_actions = menu_bar.actions()
        stale_index = top_level_actions.index(stale_action)
        insert_before = (
            top_level_actions[stale_index + 1] if stale_index + 1 < len(top_level_actions) else None
        )

        replacement = QMenu("&File", menu_bar)
        replacement.setStyleSheet(menu_style())
        self._file_menu_ref = replacement

        action_map = self.window.action_map
        for name in (
            "Open Images...",
            "Open Folder...",
            "Open IQA Result...",
        ):
            action = action_map.get(name)
            if isinstance(action, QAction):
                replacement.addAction(action)
        replacement.addSeparator()
        export_action = action_map.get("Export Statistics CSV...")
        if isinstance(export_action, QAction):
            replacement.addAction(export_action)
        replacement.addSeparator()
        exit_action = action_map.get("Exit")
        if isinstance(exit_action, QAction):
            replacement.addAction(exit_action)

        menu_bar.removeAction(stale_action)
        if insert_before is None:
            menu_bar.addMenu(replacement)
        else:
            menu_bar.insertMenu(insert_before, replacement)
        return replacement

    def _install_file_menu_actions(self) -> None:
        menu = self._file_menu()
        actions = menu.actions()
        first_separator = next((action for action in actions if action.isSeparator()), None)
        if first_separator is None:
            menu.addAction(self.open_action)
            menu.addSeparator()
            menu.addAction(self.save_action)
            return
        menu.insertAction(first_separator, self.open_action)
        menu.insertAction(first_separator, self.save_action)
        self.separator_action = first_separator

    def _dialog_directory(self) -> str:
        getter = getattr(self.window, "_open_dialog_directory", None)
        return str(getter()) if callable(getter) else ""

    def save_dialog(self) -> None:
        if not self._persistent_registered_documents():
            self.window.statusBar().showMessage("No Registered images to save", 3000)
            return
        path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Save Session",
            self._dialog_directory(),
            SESSION_FILTER,
        )
        if not path:
            return
        target = Path(path)
        if target.suffix.casefold() != ".pixelscope":
            target = target.with_suffix(".pixelscope")
        try:
            self.save_to_path(target)
        except (OSError, ComparisonSetError) as exc:
            QMessageBox.warning(self.window, "Cannot save Session", str(exc))
            return
        remember = getattr(self.window, "_remember_directory", None)
        if callable(remember):
            remember(target.parent)
        self._notify_recent_entry(target)
        self.window.statusBar().showMessage(f"Saved Session · {target.name}", 4000)

    def save_to_path(self, path: str | Path) -> Session:
        registered = self._persistent_registered_documents()
        if not registered:
            raise ComparisonSetError("no persistent Registered images to save")

        registered_sources: list[SessionSource] = []
        for document in registered:
            assert document.source_path is not None
            profile = self.window._raw_profiles.get(document.document_id)
            if profile is None and isinstance(document.raw_profile, RawProfile):
                profile = document.raw_profile
            raw_payload = profile.dict() if isinstance(profile, RawProfile) else None
            registered_sources.append(SessionSource(str(document.source_path), raw_payload))

        selected = [
            document
            for document in self.window.selected_documents
            if document.source_path is not None
        ]
        selected_paths = tuple(str(document.source_path) for document in selected)
        selected_ids = {document.document_id for document in selected}
        active_path = self._path_for_runtime_id(self.window._active_document_id, selected_ids)
        current_page = [
            document
            for document in self.window.current_comparison_documents()
            if document.source_path is not None
        ]
        current_page_ids = {document.document_id for document in current_page}
        page_anchor_path = str(current_page[0].source_path) if current_page else None
        primary_path = (
            self._path_for_runtime_id(self.window._focus_document_id, current_page_ids)
            if self.window._layout_mode != "Single View"
            else None
        )
        session = Session(
            registered_sources=tuple(registered_sources),
            selected_paths=selected_paths,
            page_anchor_path=page_anchor_path,
            active_path=active_path,
            primary_path=primary_path,
            layout_mode=self.window._layout_mode,
            roi=self.window._shared_roi,
            line=self.window._shared_line,
            display_gain=display_gain_state().gain,
            split_channels=bool(self.window._split_channels),
            difference=self._capture_difference(current_page_ids),
        )
        self.repository.save(path, session)
        return session

    def _persistent_registered_documents(self) -> list[Any]:
        return [
            document
            for document in self.window.documents.values()
            if document.source_path is not None
        ]

    def _capture_difference(self, current_page_ids: set[str]) -> SessionDifference | None:
        if self.window._difference_document is None or self.window._difference_source_ids is None:
            return None
        a_id, b_id = self.window._difference_source_ids
        if a_id not in current_page_ids or b_id not in current_page_ids:
            return None
        a = self.window.documents.get(a_id)
        b = self.window.documents.get(b_id)
        if a is None or b is None or a.source_path is None or b.source_path is None:
            return None
        panel = self.window.difference_panel
        return SessionDifference(
            image_a_path=str(a.source_path),
            image_b_path=str(b.source_path),
            channel=panel.channel.currentText() or "All",
            mode=panel.mode.currentText() or "Absolute",
            threshold=float(panel.threshold.value()),
            gain=int(panel.gain.value()),
            region=panel.region.currentText() or "Full image",
        )

    def _path_for_runtime_id(
        self,
        document_id: str | None,
        allowed_ids: set[str],
    ) -> str | None:
        if document_id is None or document_id not in allowed_ids:
            return None
        document = self.window.documents.get(document_id)
        return (
            str(document.source_path)
            if document is not None and document.source_path is not None
            else None
        )

    def open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open Session",
            self._dialog_directory(),
            SESSION_FILTER,
        )
        if not path:
            return
        try:
            loaded, missing = self.open_from_path(path)
        except (OSError, ComparisonSetError) as exc:
            QMessageBox.warning(self.window, "Cannot open Session", str(exc))
            return
        if loaded == 0:
            return
        target = Path(path)
        remember = getattr(self.window, "_remember_directory", None)
        if callable(remember):
            remember(target.parent)
        self._notify_recent_entry(target)
        self.show_open_feedback(target, loaded, missing)

    def show_open_feedback(
        self,
        path: str | Path,
        loaded: int,
        missing: tuple[Path, ...],
    ) -> None:
        target = Path(path)
        if missing:
            preview = "\n".join(str(item) for item in missing[:5])
            suffix = f"\n… and {len(missing) - 5} more" if len(missing) > 5 else ""
            QMessageBox.warning(
                self.window,
                "Session opened with missing sources",
                f"Restored {loaded} Registered source(s); "
                f"{len(missing)} source(s) were unavailable.\n\n{preview}{suffix}",
            )
        self.window.statusBar().showMessage(
            f"Opened Session · {target.name} · {loaded} Registered source(s)",
            4000,
        )

    def open_from_path(self, path: str | Path) -> tuple[int, tuple[Path, ...]]:
        session = self.repository.load(path)

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

        desired_paths = {source.path.casefold() for source, _input in loadable}
        remove_ids = [
            document_id
            for document_id, document in self.window.documents.items()
            if document.source_path is None
            or str(document.source_path.resolve(strict=False)).casefold() not in desired_paths
        ]
        if remove_ids:
            self.window._remove_document_ids(remove_ids)

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
        self.window._update_empty_workspace_state()
        if not path_to_id:
            QMessageBox.warning(
                self.window,
                "Session sources unavailable",
                "None of the saved source paths could be registered.",
            )
            return 0, tuple(missing)

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
        self.window._set_split_channels(split_enabled)

        self._pending_roi = session.roi
        self._pending_line = session.line
        self._pending_difference = session.difference
        self._pending_path_to_id = path_to_id
        QTimer.singleShot(0, self._try_restore_deferred_state)
        return len(path_to_id), tuple(missing)

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

        if self._pending_difference is None:
            return
        recipe = self._pending_difference
        a_id = self._pending_path_to_id.get(recipe.image_a_path.casefold())
        b_id = self._pending_path_to_id.get(recipe.image_b_path.casefold())
        if a_id is None or b_id is None:
            self._pending_difference = None
            return
        a = self.window.documents.get(a_id)
        b = self.window.documents.get(b_id)
        if a is None or b is None or a.source is None or b.source is None:
            return

        panel = self.window.difference_panel
        panel.set_documents(
            self.window.current_comparison_documents(),
            (a_id, b_id),
            self.window._shared_roi,
        )
        a_index = panel.a_selector.findData(a_id)
        b_index = panel.b_selector.findData(b_id)
        if a_index < 0 or b_index < 0:
            return
        panel.a_selector.setCurrentIndex(a_index)
        panel.b_selector.setCurrentIndex(b_index)
        channel_index = panel.channel.findText(recipe.channel)
        if channel_index >= 0:
            panel.channel.setCurrentIndex(channel_index)
        mode_index = panel.mode.findText(recipe.mode)
        if mode_index >= 0:
            panel.mode.setCurrentIndex(mode_index)
        region_index = panel.region.findText(recipe.region)
        if region_index >= 0:
            panel.region.setCurrentIndex(region_index)
        panel.threshold.setValue(recipe.threshold)
        panel.gain.setValue(recipe.gain)
        self._pending_difference = None
        panel.calculate_difference()

    @staticmethod
    def _saved_member_id(
        path: str | None,
        path_to_id: dict[str, str],
    ) -> str | None:
        return None if path is None else path_to_id.get(path.casefold())

    def _apply_saved_raw_profile(self, document_id: str, profile: RawProfile) -> None:
        document = self.window.documents[document_id]
        previous = self.window._raw_profiles.get(document_id)
        if previous is not None and previous == profile:
            return
        if document.source is not None and previous != profile:
            self.window._raw_profiles[document_id] = profile
            self.window._mark_raw_for_reload(document_id, profile)
            return
        self.window._raw_profiles[document_id] = profile
        document.raw_profile = profile
        document.channel_layout = profile.channel_layout
        document.bit_depth = profile.bit_depth
        self.window._raw_profile_prompt_suppressed.discard(document_id)
        self.window._update_document_item(document)


ComparisonSetController = SessionController


def install_comparison_set(window: Any) -> SessionController:
    existing = getattr(window, "session_controller", None)
    if isinstance(existing, SessionController):
        return existing
    controller = SessionController(window)
    window.session_controller = controller
    window.comparison_set_controller = controller
    return controller
