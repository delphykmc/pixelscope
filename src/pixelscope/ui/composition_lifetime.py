from __future__ import annotations

import weakref
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEvent, QObject

from pixelscope.remote.iqa_client import IqaJobClient
from pixelscope.ui.analysis_export import AnalysisExportController
from pixelscope.ui.iqa_remote_settings import install_remote_iqa_settings_dialog
from pixelscope.ui.iqa_submission import RemoteIqaController, RemoteIqaWorkspace
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


class NonOwningRemoteIqaController(RemoteIqaController):
    """Remote IQA controller whose MainWindow edge is non-owning."""

    @property
    def window(self) -> Any:
        window = self._window_ref()
        if window is None:
            raise RuntimeError("Remote IQA owner was destroyed")
        return window

    @window.setter
    def window(self, value: Any) -> None:
        self._window_ref = weakref.ref(value)


class _NonOwningRemoteIqaCloseFilter(QObject):
    """Window-owned close filter that does not retain its Remote IQA controller."""

    def __init__(self, controller: RemoteIqaController, parent: QObject) -> None:
        super().__init__(parent)
        self._controller_ref = weakref.ref(controller)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() is QEvent.Type.Close:
            controller = self._controller_ref()
            if controller is not None:
                controller.shutdown()
        return super().eventFilter(watched, event)


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


def install_remote_iqa(
    window: Any,
    *,
    client_factory: Callable[[str], IqaJobClient] | None = None,
) -> RemoteIqaController:
    """Install Remote IQA without controller/filter return edges to MainWindow."""

    install_remote_iqa_settings_dialog(window)
    existing_results = window.iqa_workspace
    shell = RemoteIqaWorkspace(existing_results)
    window.iqa_dock.setWidget(shell)
    controller = NonOwningRemoteIqaController(
        window,
        shell,
        window.iqa_controller,
        client_factory=client_factory,
    )
    window.remote_iqa_workspace = shell
    window.remote_iqa_controller = controller
    close_filter = _NonOwningRemoteIqaCloseFilter(controller, window)
    window.installEventFilter(close_filter)
    window._remote_iqa_close_filter = close_filter
    return controller


def release_command_row_metric_window(window: Any) -> None:
    """Release the bootstrap-only MainWindow edge after metric filters are installed."""

    owner = getattr(window, "_command_row_metric_refresh", None)
    if isinstance(owner, _CommandRowMetricRefresh) and getattr(owner, "_window", None) is window:
        # _CommandRowMetricRefresh uses MainWindow only while __init__ builds the
        # watched-widget set. Refresh/eventFilter paths rely on the retained widgets,
        # so keeping this return edge afterward only makes the composed window cyclic.
        owner._window = None
