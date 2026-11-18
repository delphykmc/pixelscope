"""Explicit chooser continuations after background directory validation."""
from __future__ import annotations

from collections.abc import Callable
from functools import partial, wraps
from typing import Any

from PySide6.QtWidgets import QMessageBox

from pixelscope.app.path_preparation import path_preparation
from pixelscope.io.dialog_directory import prepare_dialog_directory
from pixelscope.ui.lifecycle_hooks import WeakOwnerHook
from pixelscope.workers.task_worker import TaskError


def _window(owner: Any) -> Any:
    window = getattr(owner, "window", owner)
    # QWidget.window is a method; controller.window is a MainWindow property.
    return owner if callable(window) else window


def _invoke(owner: Any, directory: str, *, function: Callable[..., None]) -> None:
    window = _window(owner)
    previous = getattr(window, "_prepared_dialog_directory", None)
    window._prepared_dialog_directory = directory
    try:
        function(owner)
    finally:
        window._prepared_dialog_directory = previous


def _failed(owner: Any, error: TaskError) -> None:
    QMessageBox.warning(_window(owner), "Cannot prepare file dialog", error.message)


def prepared_dialog(
    *, export: bool = False
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Prepare configured locations before invoking the original GUI command.

    This is a definition-time decorator: no instance method replacement or stored
    bound-original cycle. Dispatch carries only strings to the worker; the original
    command runs later on the GUI thread through a weak owner continuation.
    """

    def decorate(function: Callable[..., None]) -> Callable[..., None]:
        @wraps(function)
        def command(owner: Any) -> None:
            window = _window(owner)
            if getattr(window, "_closing", False):
                return
            settings = window.application_settings
            configured = (
                settings.default_export_directory if export else settings.default_open_directory
            )
            last_used = window._last_directory
            preparation = getattr(window, "path_preparation_controller", None)
            if preparation is not None:
                preparation.cancel()
            if not configured.strip() and not last_used:
                function(owner)
                return
            controller = path_preparation(window)
            controller.submit(
                prepare_dialog_directory,
                (configured, last_used),
                WeakOwnerHook(owner, partial(_invoke, function=function)),
                WeakOwnerHook(owner, _failed),
            )

        return command

    return decorate
