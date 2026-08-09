from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from pixelscope.app.main_window import MainWindow
from pixelscope.app.resources import load_application_icon
from pixelscope.app.settings import (
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
)
from pixelscope.core.performance_settings import PerformanceSettings
from pixelscope.ui.design_tokens import apply_engineering_palette
from pixelscope.ui.display_gain import install_display_gain_control
from pixelscope.ui.display_gain_shortcuts import install_display_gain_shortcuts

LOGGER = logging.getLogger(__name__)
WINDOWS_APP_USER_MODEL_ID = "PixelScope.PixelScope"


def _set_windows_app_user_model_id() -> None:
    """Assign a stable Windows shell identity before QApplication creation."""

    if sys.platform != "win32":
        return

    try:
        import ctypes

        windll = ctypes.windll
        shell32 = windll.shell32
        setter = shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        result = int(setter(WINDOWS_APP_USER_MODEL_ID))
    except (AttributeError, OSError, TypeError, ValueError):
        LOGGER.warning("Unable to configure the PixelScope Windows AppUserModelID")
        return

    if result != 0:
        LOGGER.warning("Windows rejected the PixelScope AppUserModelID: HRESULT=%s", result)


def _configure_application(app: QApplication) -> None:
    app.setApplicationName("PixelScope")
    app.setOrganizationName("PixelScope")
    icon = load_application_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    apply_engineering_palette(app)


def create_application(arguments: Sequence[str] | None = None) -> QApplication:
    """Return the process QApplication, creating it when required."""

    _set_windows_app_user_model_id()
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        _configure_application(existing)
        return existing
    app = QApplication(list(arguments) if arguments is not None else sys.argv)
    _configure_application(app)
    return app


def load_startup_settings() -> tuple[SettingsRepository, ApplicationSettings, PerformanceSettings]:
    """Load and validate persisted preferences, then freeze the runtime snapshot."""

    repository = SettingsRepository(QSettingsAdapter(QSettings()))
    application_settings = repository.load()
    return repository, application_settings, application_settings.performance_settings()


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = create_application(arguments)
    repository, application_settings, performance_settings = load_startup_settings()
    window = MainWindow(application_settings, performance_settings, repository)
    gain_control = install_display_gain_control(window)
    install_display_gain_shortcuts(window.central_stack, gain_control)
    window.setWindowIcon(app.windowIcon())
    window.show()
    return app.exec()
