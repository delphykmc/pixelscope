"""P5-E lifecycle hardening for historical Result intent and live settings."""

from __future__ import annotations

from pathlib import Path
from types import MethodType
from typing import Any

from PySide6.QtCore import QObject

from pixelscope.remote.iqa_history import IqaResultIdentity, IqaResultLocator
from pixelscope.ui.iqa_historical_results import HistoricalIqaResultsController


class HistoricalIqaResultsLifecycle(QObject):
    """Keep P5-E feature-local work subordinate to the newest Result-open intent."""

    def __init__(self, controller: HistoricalIqaResultsController, parent: QObject) -> None:
        super().__init__(parent)
        self.controller = controller
        self.window = controller.window
        self.remote_controller = controller.remote_controller
        self._original_start_open = controller._start_open
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

        controller._start_open = MethodType(start_open, controller)
        self.remote_controller.settings_changed = MethodType(
            remote_settings_changed,
            self.remote_controller,
        )

    def _invalidate_resolver(self) -> None:
        """Invalidate before cancellation so stale callbacks fail the generation guard."""

        self.controller._resolve_generation += 1
        self.controller._cancel_resolver()


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
