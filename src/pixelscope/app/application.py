from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtWidgets import QApplication, QComboBox

from pixelscope.app.main_window import MainWindow
from pixelscope.app.resources import load_application_icon
from pixelscope.app.settings import (
    ApplicationSettings,
    QSettingsAdapter,
    SettingsRepository,
)
from pixelscope.core.performance_settings import PerformanceSettings
from pixelscope.remote.iqa_transport_pool import ReusableIqaClientPool
from pixelscope.ui.analysis_export import install_analysis_export
from pixelscope.ui.beta_workspace_hardening import install_beta_workspace_hardening
from pixelscope.ui.design_tokens import apply_engineering_palette
from pixelscope.ui.difference_curation_lifecycle import install_difference_curation_lifecycle
from pixelscope.ui.display_gain import install_display_gain_control
from pixelscope.ui.display_gain_shortcuts import install_display_gain_shortcuts
from pixelscope.ui.dpi_command_row import install_dpi_safe_command_row
from pixelscope.ui.folder_display_tags import install_folder_display_tags
from pixelscope.ui.iqa_historical_results import install_historical_iqa_results
from pixelscope.ui.iqa_historical_results_lifecycle import (
    install_historical_iqa_results_lifecycle,
)
from pixelscope.ui.iqa_p5f_diagnostics import install_remote_iqa_diagnostics
from pixelscope.ui.iqa_p5f_lifecycle import install_remote_iqa_transport_lifecycle
from pixelscope.ui.iqa_preview_lifecycle import install_remote_iqa_preview_lifecycle
from pixelscope.ui.iqa_replay_debug import install_remote_iqa_replay_debug
from pixelscope.ui.iqa_request_debug import install_remote_iqa_request_debug
from pixelscope.ui.iqa_result_mapping import install_remote_iqa_result_mapping
from pixelscope.ui.iqa_result_retry import install_remote_iqa_result_retry
from pixelscope.ui.iqa_scene_inspection import install_iqa_scene_inspection
from pixelscope.ui.iqa_scene_inspection_lifecycle import install_iqa_scene_inspection_lifecycle
from pixelscope.ui.iqa_setup_presentation import polish_remote_iqa_setup
from pixelscope.ui.iqa_submission import install_remote_iqa
from pixelscope.ui.iqa_submission_lifecycle import install_remote_iqa_submission_lifecycle
from pixelscope.ui.multiview_reorder_stability import install_multiview_reorder_stability
from pixelscope.ui.presentation_controls import polish_presentation_controls
from pixelscope.ui.recent_entries import install_recent_entries
from pixelscope.ui.review_selection import install_review_selection
from pixelscope.ui.session import install_session
from pixelscope.ui.workflow_polish import install_workflow_polish
from pixelscope.workers.iqa_thread_pool import remote_iqa_thread_pool
from pixelscope.workers.thread_pools import analysis_thread_pool

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


def _compose_main_window_presentation(window: MainWindow) -> QComboBox:
    """Install the production presentation control composition in one authoritative order."""

    gain_control = install_display_gain_control(window)
    review_controller = install_review_selection(window)
    install_difference_curation_lifecycle(window, review_controller)
    install_session(window)
    install_recent_entries(window)
    install_analysis_export(window)

    # Production injects the P5-F result/file pool when constructing MainWindow.
    # The same dependency is forwarded to later result-side controllers here.
    result_pool = window.iqa_controller.pool
    transport_pool = ReusableIqaClientPool()
    _compose_remote_iqa(
        window,
        result_pool=result_pool,
        transport_pool=transport_pool,
    )
    polish_presentation_controls(window)
    install_workflow_polish(window, review_controller)
    install_multiview_reorder_stability(window)
    install_folder_display_tags(window)
    install_display_gain_shortcuts(window.central_stack, gain_control)
    install_beta_workspace_hardening(window)
    install_dpi_safe_command_row(window)
    return gain_control


def _compose_remote_iqa(
    window: MainWindow,
    *,
    result_pool: QThreadPool,
    transport_pool: ReusableIqaClientPool,
) -> None:
    """Install the existing Remote IQA controllers in their dependency order."""

    # P5-C owns submission/jobs and the transport lifetime. Result mapping must wrap
    # settings changes before the later P5-D and P5-E observers extend that chain.
    remote_iqa_controller = install_remote_iqa(
        window,
        client_factory=transport_pool.client,
    )
    window.__dict__["remote_iqa_transport_pool"] = transport_pool
    install_remote_iqa_transport_lifecycle(window, transport_pool)
    install_remote_iqa_diagnostics(window, transport_pool)
    install_remote_iqa_preview_lifecycle(window)
    install_remote_iqa_submission_lifecycle(window)
    install_remote_iqa_result_mapping(window)
    install_remote_iqa_result_retry(window)
    polish_remote_iqa_setup(remote_iqa_controller.workspace)
    install_remote_iqa_request_debug(window)
    install_remote_iqa_replay_debug(window)

    # P5-D owns the only native Inspect bridge and consumes the already-hardened
    # P5-C settings chain.
    install_iqa_scene_inspection(window, pool=result_pool)
    install_iqa_scene_inspection_lifecycle(window)

    # P5-E deliberately wraps the P5-D open path rather than bypassing its teardown.
    historical_iqa = install_historical_iqa_results(window, pool=result_pool)
    install_historical_iqa_results_lifecycle(window, historical_iqa)


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = create_application(arguments)
    repository, application_settings, performance_settings = load_startup_settings()
    # Preserve the pre-R2 aboutToQuit order: local background pools register before
    # the Remote IQA result/file pool, even though both now precede MainWindow.
    analysis_thread_pool()
    result_pool = remote_iqa_thread_pool()
    window = MainWindow(
        application_settings,
        performance_settings,
        repository,
        iqa_result_pool=result_pool,
    )
    _compose_main_window_presentation(window)
    window.setWindowIcon(app.windowIcon())
    window.show()
    return app.exec()
