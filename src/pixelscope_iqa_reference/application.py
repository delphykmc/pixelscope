"""Explicit source-level launcher for PixelScope + MAIN reference IQA."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from pixelscope.app.bootstrap import (
    compose_main_window_presentation,
    create_application,
    load_startup_settings,
)
from pixelscope.app.main_window import MainWindow
from pixelscope.workers.thread_pools import analysis_thread_pool
from pixelscope_iqa_reference.extension import ReferenceIqaExtension


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = create_application(arguments)
    repository, application_settings, performance_settings = load_startup_settings()
    analysis_thread_pool()
    extension = ReferenceIqaExtension()
    window = MainWindow(
        application_settings,
        performance_settings,
        repository,
        window_contributions=(extension,),
    )
    compose_main_window_presentation(window)
    window.setWindowIcon(app.windowIcon())
    window.show()
    return app.exec()
