"""Legacy Remote-IQA lifetime composition retained during Issue #121 Slice 6."""

from __future__ import annotations

import weakref
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEvent, QObject

from pixelscope.remote.iqa_client import IqaJobClient
from pixelscope.ui.iqa_remote_settings import install_remote_iqa_settings_dialog
from pixelscope.ui.iqa_submission import RemoteIqaController, RemoteIqaWorkspace


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
