"""Base-owned application bootstrap and presentation composition.

This module deliberately contains no IQA implementation selection. Concrete extensions
are selected by explicit composition roots and may optionally contribute a runtime phase.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QComboBox

from pixelscope.app.main_window import MainWindow
from pixelscope.app.raw_input_compatibility import install_raw_input_compatibility
from pixelscope.app.registration_controller import install_large_folder_registration
from pixelscope.app.resources import load_application_icon
from pixelscope.app.settings import (
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
)
from pixelscope.app.window_contribution import RuntimeWindowContribution
from pixelscope.app.yuv_difference_semantics import install_native_yuv_difference
from pixelscope.app.yuv_input_semantics import install_native_yuv_semantics
from pixelscope.app.yuv_runtime_contracts import install_native_yuv_runtime_contracts
from pixelscope.core.performance_settings import PerformanceSettings
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening
from pixelscope.ui.composition_lifetime import (
    install_analysis_export,
    install_session,
    release_command_row_metric_window,
)
from pixelscope.ui.design_tokens import apply_engineering_palette
from pixelscope.ui.difference_curation_lifecycle import install_difference_curation_lifecycle
from pixelscope.ui.display_gain import install_display_gain_control
from pixelscope.ui.display_gain_shortcuts import install_display_gain_shortcuts
from pixelscope.ui.folder_display_tags import install_folder_display_tags
from pixelscope.ui.issue77_ui_design_followup import install_issue77_ui_design_followup
from pixelscope.ui.multiview_reorder_stability import install_multiview_reorder_stability
from pixelscope.ui.presentation_controls import polish_presentation_controls
from pixelscope.ui.quick_compare import install_quick_compare_workflow
from pixelscope.ui.recent_entries import install_recent_entries
from pixelscope.ui.review_selection import install_review_selection
from pixelscope.ui.user_guide_help import install_user_guide_help
from pixelscope.ui.workflow_polish import install_workflow_polish

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


def compose_main_window_presentation(
    window: MainWindow,
    runtime_contributions: Sequence[RuntimeWindowContribution] = (),
) -> QComboBox:
    """Install Base presentation plus explicitly selected extension runtime phases."""

    gain_control = install_display_gain_control(window)
    review_controller = install_review_selection(window)
    install_difference_curation_lifecycle(window, review_controller)
    install_session(window)
    install_recent_entries(window)
    install_analysis_export(window)
    install_user_guide_help(window)

    for contribution in runtime_contributions:
        contribution.install_runtime(window)

    polish_presentation_controls(window)
    release_command_row_metric_window(window)
    install_workflow_polish(window, review_controller)
    install_multiview_reorder_stability(window)
    install_raw_input_compatibility(window)
    install_native_yuv_semantics(window)
    install_native_yuv_difference(window)
    install_native_yuv_runtime_contracts(window)
    install_folder_display_tags(window)
    install_display_gain_shortcuts(window.central_stack, gain_control)
    install_beta_workspace_hardening(window)
    install_large_folder_registration(window)
    install_quick_compare_workflow(window)
    install_issue77_ui_design_followup(window)
    return gain_control
