from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QComboBox

from pixelscope.app.bootstrap import (
    compose_main_window_presentation,
    create_application,
    load_startup_settings,
)
from pixelscope.app.main_window import MainWindow
from pixelscope.ui.iqa_client_install import IqaClientInstaller
from pixelscope.workers.thread_pools import analysis_thread_pool


def remote_iqa_thread_pool() -> QThreadPool:
    """Temporary Stage-1 tooling shim for the pre-Slice-4 application import path."""

    from pixelscope.workers.iqa_thread_pool import remote_iqa_thread_pool as create_pool

    return create_pool()


def _resolve_iqa_client(
    window: MainWindow,
    explicit: IqaClientInstaller | None,
) -> IqaClientInstaller:
    """Resolve the explicit legacy production client or direct-window compatibility shim."""

    if explicit is not None:
        return explicit
    for contribution in window._window_contributions:
        if isinstance(contribution, IqaClientInstaller):
            return contribution
    raise RuntimeError("Legacy production composition requires an IQA Client contribution")


def _compose_main_window_presentation(
    window: MainWindow,
    iqa_client: IqaClientInstaller | None = None,
) -> QComboBox:
    """Compatibility wrapper preserving the current P5 production runtime order."""

    resolved = _resolve_iqa_client(window, iqa_client)
    return compose_main_window_presentation(window, runtime_contributions=(resolved,))


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = create_application(arguments)
    repository, application_settings, performance_settings = load_startup_settings()
    analysis_thread_pool()
    iqa_client = IqaClientInstaller.production(application_settings.remote_iqa)
    window = MainWindow(
        application_settings,
        performance_settings,
        repository,
        window_contributions=(iqa_client,),
    )
    _compose_main_window_presentation(window, iqa_client)
    window.setWindowIcon(app.windowIcon())
    window.show()
    return app.exec()
