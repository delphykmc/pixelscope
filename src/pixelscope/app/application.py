from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from pixelscope.app.main_window import MainWindow


def create_application(arguments: Sequence[str] | None = None) -> QApplication:
    """Return the process QApplication, creating it when required."""

    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    app = QApplication(list(arguments) if arguments is not None else sys.argv)
    app.setApplicationName("PixelScope")
    app.setOrganizationName("PixelScope")
    return app


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = create_application(arguments)
    window = MainWindow()
    window.show()
    return app.exec()
