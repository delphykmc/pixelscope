"""Historical P5 composition retained outside Base production ownership."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QComboBox

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.ui.iqa_client_install import IqaClientInstaller


class LegacyP5MainWindow(MainWindow):
    """MainWindow test/tooling adapter that explicitly injects the retired P5 client."""

    def __init__(
        self,
        *args: Any,
        iqa_result_pool: QThreadPool | None = None,
        **kwargs: Any,
    ) -> None:
        if kwargs.get("window_contributions") is not None:
            raise ValueError("LegacyP5MainWindow owns its IQA contribution")
        installer = IqaClientInstaller(iqa_result_pool)
        kwargs["window_contributions"] = (installer,)
        super().__init__(*args, **kwargs)
        self.legacy_p5_installer = installer


def compose_legacy_p5_presentation(window: LegacyP5MainWindow) -> QComboBox:
    """Install Base presentation plus the explicit historical P5 runtime."""

    return compose_main_window_presentation(
        window,
        runtime_contributions=(window.legacy_p5_installer,),
    )
