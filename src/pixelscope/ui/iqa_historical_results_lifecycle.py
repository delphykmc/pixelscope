"""P5-E lifecycle hardening for historical Result intent and live settings."""

from __future__ import annotations

from pathlib import Path
from types import MethodType
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction

from pixelscope.remote.iqa_history import IqaResultIdentity, IqaResultLocator
from pixelscope.ui.iqa_historical_results import HistoricalIqaResultsController


class HistoricalIqaResultsLifecycle(QObject):
    """Keep P5-E feature-local work subordinate to the newest Result-open intent."""

    def __init__(self, controller: HistoricalIqaResultsController, parent: QObject) -> None:
        super().__init__(parent)
        self.controller = controller
        self.window = controller.window
        dynamic_controller: Any = controller
        self.remote_controller = dynamic_controller.remote_controller
        self._original_start_open = dynamic_controller._start_open
        self._original_remote_settings_changed = self.remote_controller.settings_changed

        def start_open(
            _controller: Any,
            root: Path,
            *,
            locator: IqaResultLocator | None = None,
            expected: IqaResultIdentity | None = None,
            mapping_revision: int | None = None,
            from_recent: bool = False,
        ) -> int:
            self._invalidate_resolver()
            return int(
                self._original_start_open(
                    root,
                    locator=locator,
                    expected=expected,
                    mapping_revision=mapping_revision,
                    from_recent=from_recent,
                )
            )

        def remote_settings_changed(_remote_controller: Any) -> None:
            self._original_remote_settings_changed()
            if self.controller._active:
                self.controller.provenance.refresh_settings(
                    self.window.application_settings.remote_iqa
                )

        dynamic_controller._start_open = MethodType(start_open, dynamic_controller)
        self.remote_controller.settings_changed = MethodType(
            remote_settings_changed,
            self.remote_controller,
        )
        self._reorder_file_open_group()

    def _invalidate_resolver(self) -> None:
        """Invalidate before cancellation so stale callbacks fail the generation guard."""

        self.controller._resolve_generation += 1
        self.controller._cancel_resolver()

    def _reorder_file_open_group(self) -> None:
        """Keep direct opens together, followed by the four matching Recent menus."""

        recent = getattr(self.window, "recent_entries_controller", None)
        if recent is None:
            return

        images_action = self.window.action_map.get("Open Images...")
        folder_action = self.window.action_map.get("Open Folder...")
        session_action = recent.session_controller.open_action
        iqa_action = self.window.action_map.get("Open IQA Result...")
        separator = recent.session_controller.separator_action
        ordered_actions = (
            images_action,
            folder_action,
            session_action,
            iqa_action,
            recent.images_menu.menuAction(),
            recent.folders_menu.menuAction(),
            recent.sessions_menu.menuAction(),
            self.controller.recent_menu.menuAction(),
        )
        if not all(isinstance(action, QAction) for action in ordered_actions):
            return
        if not isinstance(separator, QAction):
            return

        for action in ordered_actions:
            self.controller.file_menu.removeAction(action)
        for action in ordered_actions:
            self.controller.file_menu.insertAction(separator, action)


def install_historical_iqa_results_lifecycle(
    window: Any,
    controller: HistoricalIqaResultsController,
) -> HistoricalIqaResultsLifecycle:
    """Install after P5-E and after the P5-D settings-change wrapper."""

    existing = getattr(window, "historical_iqa_results_lifecycle", None)
    if isinstance(existing, HistoricalIqaResultsLifecycle):
        return existing
    lifecycle = HistoricalIqaResultsLifecycle(controller, window)
    window.historical_iqa_results_lifecycle = lifecycle
    return lifecycle
