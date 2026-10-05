"""Stage-1 IQA Client installer for the Base-owned window contribution seam.

The installer owns IQA-specific widget/controller/actions and the existing Remote-IQA
composition order. Compatibility attributes are attached to ``MainWindow`` so mature
P5/UI tests and installers can keep their current access paths during the first SUB handoff.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QFileDialog, QMainWindow

from pixelscope.app.window_contribution import MenuActionFactory
from pixelscope.remote.iqa_transport_pool import ReusableIqaClientPool
from pixelscope.ui.composition_lifetime import install_remote_iqa
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
from pixelscope.ui.iqa_submission_lifecycle import install_remote_iqa_submission_lifecycle
from pixelscope.ui.iqa_workspace import IqaWorkspaceController, IqaWorkspaceWidget
from pixelscope.workers.iqa_thread_pool import remote_iqa_thread_pool


class IqaClientInstaller:
    """Explicit Stage-1 IQA Client contribution selected by application composition."""

    def __init__(self, result_pool: QThreadPool | None = None) -> None:
        self._result_pool = result_pool
        self.workspace: IqaWorkspaceWidget | None = None
        self.controller: IqaWorkspaceController | None = None
        self.dock: QDockWidget | None = None
        self.action: QAction | None = None
        self._window: Any | None = None

    @classmethod
    def production(cls) -> "IqaClientInstaller":
        """Create the production client after Base local-pool initialization."""

        return cls(remote_iqa_thread_pool())

    @property
    def result_pool(self) -> QThreadPool:
        if self.controller is None:
            raise RuntimeError("IQA Client contribution is not prepared")
        return self.controller.pool

    def prepare(self, window: QMainWindow) -> None:
        workspace = IqaWorkspaceWidget()
        controller = IqaWorkspaceController(workspace, window, pool=self._result_pool)
        self.workspace = workspace
        self.controller = controller
        self._window = window
        # Stage-1 compatibility surface. Ownership is the installer, not MainWindow.
        window.__dict__["iqa_workspace"] = workspace
        window.__dict__["iqa_controller"] = controller
        window.__dict__["open_iqa_result"] = self.open_result
        window.__dict__["_toggle_iqa"] = self.toggle_workspace

    def install_dock(self, window: QMainWindow) -> None:
        if self.workspace is None:
            raise RuntimeError("IQA Client contribution must be prepared before dock install")
        dock = QDockWidget("IQA", window)
        dock.setObjectName("iqaWorkspaceDock")
        dock.setWidget(self.workspace)
        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.hide()
        self.dock = dock
        window.__dict__["iqa_dock"] = dock
        register = getattr(window, "register_contributed_dock")
        register(dock)

    def install_actions(
        self,
        window: QMainWindow,
        menu_name: str,
        add_action: MenuActionFactory,
    ) -> None:
        if menu_name == "File":
            add_action("File", "Open IQA Result...", self.open_result, None)
            return
        if menu_name != "View":
            return
        if self.dock is None:
            raise RuntimeError("IQA Client dock must exist before actions are installed")
        action = add_action("View", "Show IQA Workspace", self.toggle_workspace, None)
        action.setCheckable(True)
        self.dock.visibilityChanged.connect(action.setChecked)  # type: ignore[attr-defined]
        self.action = action
        window.__dict__["iqa_workspace_action"] = action

    def open_result(self) -> None:
        window = self._require_window()
        root = QFileDialog.getExistingDirectory(
            window,
            "Open IQA Result",
            window._open_dialog_directory(),
        )
        if not root:
            return
        if self.dock is None or self.controller is None:
            raise RuntimeError("IQA Client contribution is incomplete")
        self.dock.show()
        self.dock.raise_()
        self.controller.open_result(Path(root))
        window.statusBar().showMessage(f"Opening IQA result · {Path(root).name}")

    def toggle_workspace(self) -> None:
        if self.dock is None or self.action is None:
            return
        visible = self.action.isChecked()
        self.dock.setVisible(visible)
        if visible:
            self.dock.raise_()

    def install_runtime(self, window: QMainWindow) -> None:
        """Install the existing Remote-IQA chain in its characterized dependency order."""

        result_pool = self.result_pool
        transport_pool = ReusableIqaClientPool()
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

        install_iqa_scene_inspection(window, pool=result_pool)
        install_iqa_scene_inspection_lifecycle(window)

        historical_iqa = install_historical_iqa_results(window, pool=result_pool)
        install_historical_iqa_results_lifecycle(window, historical_iqa)

    def shutdown(self) -> None:
        if self.controller is not None:
            self.controller.shutdown()

    def _require_window(self) -> Any:
        if self._window is None:
            raise RuntimeError("IQA Client contribution is not prepared")
        return self._window
