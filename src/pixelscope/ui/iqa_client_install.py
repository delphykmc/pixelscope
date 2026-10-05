"""Stage-1 IQA Client installer for the Base-owned window contribution seam.

The installer owns IQA-specific widget/controller/actions and the existing Remote-IQA
composition order. Public provider/result ports are explicit Client dependencies; the
legacy P5 composition remains a compatibility path during the first SUB handoff.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from weakref import ReferenceType, ref

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QFileDialog, QMainWindow

from pixelscope.app.window_contribution import MenuActionFactory
from pixelscope.remote.iqa_client import IqaJobClient
from pixelscope.remote.iqa_public_adapter import (
    P5IqaExecutionAdapter,
    P5IqaReferenceRegistry,
    P5IqaResultAccessAdapter,
)
from pixelscope.remote.iqa_public_contract import (
    IqaExecutionPort,
    IqaResultAccessPort,
    IqaResultReference,
)
from pixelscope.remote.iqa_settings import RemoteIqaSettings
from pixelscope.remote.iqa_submission import (
    IqaJobCreated,
    IqaJobRequest,
    IqaJobStatus,
)
from pixelscope.remote.iqa_submission import IqaResultReference as P5IqaResultReference
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


class _PooledIqaJobClient(IqaJobClient):
    """Adapt the existing lazy reusable transport pool to one public P5 adapter client."""

    def __init__(self, pool: ReusableIqaClientPool, base_url: str) -> None:
        self._pool = pool
        self._base_url = base_url

    def create_job(self, request: IqaJobRequest) -> IqaJobCreated:
        client = self._pool.client(self._base_url)
        try:
            return client.create_job(request)
        finally:
            client.close()

    def get_status(self, job_id: str) -> IqaJobStatus:
        client = self._pool.client(self._base_url)
        try:
            return client.get_status(job_id)
        finally:
            client.close()

    def get_result(self, job_id: str) -> P5IqaResultReference:
        client = self._pool.client(self._base_url)
        try:
            return client.get_result(job_id)
        finally:
            client.close()

    def cancel_job(self, job_id: str) -> IqaJobStatus:
        client = self._pool.client(self._base_url)
        try:
            return client.cancel_job(job_id)
        finally:
            client.close()


class IqaClientInstaller:
    """Explicit Stage-1 IQA Client contribution selected by application composition."""

    def __init__(
        self,
        result_pool: QThreadPool | None = None,
        *,
        execution_port: IqaExecutionPort | None = None,
        result_access_port: IqaResultAccessPort | None = None,
        transport_pool: ReusableIqaClientPool | None = None,
        install_legacy_runtime: bool = True,
    ) -> None:
        if (execution_port is None) != (result_access_port is None):
            raise ValueError("execution and result-access ports must be supplied together")
        self._result_pool = result_pool
        self._execution_port = execution_port
        self._result_access_port = result_access_port
        self._transport_pool = transport_pool
        self._install_legacy_runtime = install_legacy_runtime
        self._window_ref: ReferenceType[QMainWindow] | None = None
        self.workspace: IqaWorkspaceWidget | None = None
        self.controller: IqaWorkspaceController | None = None
        self.dock: QDockWidget | None = None
        self.action: QAction | None = None

    @classmethod
    def production(cls, settings: RemoteIqaSettings) -> IqaClientInstaller:
        """Create the default P5-backed public ports after Base local-pool initialization."""

        result_pool = remote_iqa_thread_pool()
        transport_pool = ReusableIqaClientPool()
        registry = P5IqaReferenceRegistry()
        execution_port = P5IqaExecutionAdapter(
            _PooledIqaJobClient(transport_pool, settings.server_base_url),
            settings,
            registry,
        )
        result_access_port = P5IqaResultAccessAdapter(settings, registry)
        return cls(
            result_pool,
            execution_port=execution_port,
            result_access_port=result_access_port,
            transport_pool=transport_pool,
        )

    @classmethod
    def from_ports(
        cls,
        execution_port: IqaExecutionPort,
        result_access_port: IqaResultAccessPort,
        *,
        result_pool: QThreadPool | None = None,
    ) -> IqaClientInstaller:
        """Compose the Client against any public provider without the legacy P5 runtime."""

        return cls(
            result_pool,
            execution_port=execution_port,
            result_access_port=result_access_port,
            install_legacy_runtime=False,
        )

    @property
    def execution_port(self) -> IqaExecutionPort:
        if self._execution_port is None:
            raise RuntimeError("IQA Client execution port is not configured")
        return self._execution_port

    @property
    def result_access_port(self) -> IqaResultAccessPort:
        if self._result_access_port is None:
            raise RuntimeError("IQA Client result-access port is not configured")
        return self._result_access_port

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
        self._window_ref = ref(window)
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
        cast(Any, window).register_contributed_dock(dock)

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

    def open_published_result(self, reference: IqaResultReference) -> int:
        """Open one provider-published result through the Client-owned worker/controller path."""

        if self.dock is None or self.controller is None:
            raise RuntimeError("IQA Client contribution is incomplete")
        self.dock.show()
        self.dock.raise_()
        return self.controller.open_result_reference(self.result_access_port, reference)

    def toggle_workspace(self) -> None:
        if self.dock is None or self.action is None:
            return
        visible = self.action.isChecked()
        self.dock.setVisible(visible)
        if visible:
            self.dock.raise_()

    def install_runtime(self, window: QMainWindow) -> None:
        """Install the characterized P5 compatibility chain when selected by composition."""

        if not self._install_legacy_runtime:
            return
        result_pool = self.result_pool
        transport_pool = self._transport_pool
        if transport_pool is None:
            transport_pool = ReusableIqaClientPool()
            self._transport_pool = transport_pool
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
        self._window_ref = None

    def _require_window(self) -> Any:
        window = self._window_ref() if self._window_ref is not None else None
        if window is None:
            raise RuntimeError("IQA Client contribution is not prepared")
        return window
