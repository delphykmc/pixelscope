from __future__ import annotations

import weakref
from typing import Any

from pixelscope.ui.analysis_export import AnalysisExportController
from pixelscope.ui.presentation_controls import _CommandRowMetricRefresh
from pixelscope.ui.session import SessionController, _LegacyComparisonSetControllerFacade


class NonOwningSessionController(SessionController):
    """Session controller whose MainWindow edge is non-owning."""

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None:
            raise RuntimeError("Session owner was destroyed")
        return window

    @window.setter
    def window(self, value: Any) -> None:
        self._window_ref = weakref.ref(value)


class NonOwningAnalysisExportController(AnalysisExportController):
    """Analysis export adapter whose MainWindow edge is non-owning."""

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None:
            raise RuntimeError("analysis export owner was destroyed")
        return window

    @window.setter
    def window(self, value: Any) -> None:
        self._window_ref = weakref.ref(value)


def install_session(window: Any) -> SessionController:
    """Install canonical Session authority without a Session -> MainWindow return edge."""

    existing = getattr(window, "session_controller", None)
    if isinstance(existing, SessionController):
        return existing
    controller = NonOwningSessionController(window)
    window.session_controller = controller
    window.comparison_set_controller = _LegacyComparisonSetControllerFacade(controller)
    return controller


def install_analysis_export(window: Any) -> AnalysisExportController:
    """Install analysis export without an AnalysisExportController -> MainWindow edge."""

    existing = getattr(window, "analysis_export_controller", None)
    if isinstance(existing, AnalysisExportController):
        return existing
    controller = NonOwningAnalysisExportController(window)
    window.analysis_export_controller = controller
    return controller


def release_command_row_metric_window(window: Any) -> None:
    """Release the bootstrap-only MainWindow edge after metric filters are installed."""

    owner = getattr(window, "_command_row_metric_refresh", None)
    if isinstance(owner, _CommandRowMetricRefresh) and getattr(owner, "_window", None) is window:
        # _CommandRowMetricRefresh uses MainWindow only while __init__ builds the
        # watched-widget set. Refresh/eventFilter paths rely on the retained widgets,
        # so keeping this return edge afterward only makes the composed window cyclic.
        owner._window = None
