from __future__ import annotations

from pathlib import Path


INSTALLER = '''\
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
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {text.count(old)}")
    return text.replace(old, new)


def main() -> None:
    Path('src/pixelscope/ui/iqa_client_install.py').write_text(INSTALLER, encoding='utf-8')

    application = Path('src/pixelscope/app/application.py')
    text = application.read_text(encoding='utf-8')
    text = replace_once(
        text,
        '    iqa_client = IqaClientInstaller.production()\n',
        '    iqa_client = IqaClientInstaller.production(application_settings.remote_iqa)\n',
        'production installer call',
    )
    application.write_text(text, encoding='utf-8')

    workspace = Path('src/pixelscope/ui/iqa_workspace.py')
    text = workspace.read_text(encoding='utf-8')
    text = replace_once(
        text,
        'from pixelscope.remote.iqa_public_contract import IqaResult\n',
        'from pixelscope.remote.iqa_public_contract import (\n'
        '    IqaResult,\n'
        '    IqaResultAccessPort,\n'
        '    IqaResultReference,\n'
        ')\n',
        'public contract import',
    )
    old_method = '''    def open_result(self, root: Path | str) -> int:
        path = Path(root)
        self._generation += 1
        generation = self._generation
        self._cancel_workers()
        self.workspace.show_loading(path)
        worker = TaskWorker(self._loader, path, generation=generation)
        worker.signals.succeeded.connect(self._result_loaded)
        worker.signals.failed.connect(self._load_failed)
        worker.signals.finished.connect(self._worker_finished)
        self._worker = worker
        self._pool.start(worker)
        return generation

'''
    new_method = old_method + '''    def open_result_reference(
        self,
        access: IqaResultAccessPort,
        reference: IqaResultReference,
    ) -> int:
        """Materialize and open a public provider result on the existing Client pool."""

        self._generation += 1
        generation = self._generation
        self._cancel_workers()
        self.workspace.status_label.setText("Opening published IQA result...")
        worker = TaskWorker(
            _load_public_result_reference,
            access,
            reference,
            generation=generation,
        )
        worker.signals.succeeded.connect(self._result_loaded)
        worker.signals.failed.connect(self._load_failed)
        worker.signals.finished.connect(self._worker_finished)
        self._worker = worker
        self._pool.start(worker)
        return generation

'''
    text = replace_once(text, old_method, new_method, 'open_result method')
    marker = '''    def _present_loaded_value(
        self,
        value: object,
    ) -> VersionedResultLoadOutcome:
'''
    text = replace_once(
        text,
        marker,
        marker + '        if isinstance(value, IqaResult):\n            return self.workspace.set_model(IqaExplorerModel(value))\n',
        'present result marker',
    )
    text = replace_once(
        text,
        '\ndef _load_workspace_result(root: Path | str) -> _WorkspaceLoadPayload:\n',
        '''
def _load_public_result_reference(
    access: IqaResultAccessPort,
    reference: IqaResultReference,
) -> IqaResult:
    source_outcome = access.materialize(reference)
    if not source_outcome.succeeded or source_outcome.source is None:
        raise RuntimeError("published IQA result is not available")
    open_outcome = access.open_result(source_outcome.source)
    if not open_outcome.succeeded or open_outcome.result is None:
        raise RuntimeError("published IQA result could not be opened")
    return open_outcome.result


def _load_workspace_result(root: Path | str) -> _WorkspaceLoadPayload:
''',
        'workspace loader marker',
    )
    workspace.write_text(text, encoding='utf-8')

    app_test = Path('tests/unit/test_application_composition.py')
    text = app_test.read_text(encoding='utf-8')
    first = text.index('def test_main_injects_result_pool_before_composition')
    text = text[:first] + '''def test_main_injects_iqa_client_after_local_pool_initialization(monkeypatch: Any) -> None:
    events: list[str] = []
    repository = object()
    remote_settings = object()
    application_settings = SimpleNamespace(remote_iqa=remote_settings)
    performance_settings = object()
    installer = object()
    icon = object()
    window = SimpleNamespace(
        setWindowIcon=lambda value: events.append(f"icon:{value is icon}"),
        show=lambda: events.append("show"),
    )
    app = SimpleNamespace(windowIcon=lambda: icon, exec=lambda: 17)

    def build_installer(settings_arg: object) -> object:
        assert settings_arg is remote_settings
        events.append("iqa_client")
        return installer

    def build_window(
        application_settings_arg: object,
        performance_settings_arg: object,
        repository_arg: object,
        *,
        window_contributions: tuple[object, ...],
    ) -> object:
        assert application_settings_arg is application_settings
        assert performance_settings_arg is performance_settings
        assert repository_arg is repository
        assert window_contributions == (installer,)
        events.append("window")
        return window

    def compose(window_arg: object, installer_arg: object) -> None:
        assert window_arg is window
        assert installer_arg is installer
        events.append("compose")

    monkeypatch.setattr(application_module, "create_application", lambda _args: app)
    monkeypatch.setattr(
        application_module,
        "load_startup_settings",
        lambda: (repository, application_settings, performance_settings),
    )
    monkeypatch.setattr(
        application_module,
        "analysis_thread_pool",
        lambda: events.append("analysis_pool"),
    )
    monkeypatch.setattr(
        application_module,
        "IqaClientInstaller",
        SimpleNamespace(production=build_installer),
    )
    monkeypatch.setattr(application_module, "MainWindow", build_window)
    monkeypatch.setattr(application_module, "_compose_main_window_presentation", compose)

    assert application_module.main([]) == 17
    assert events == [
        "analysis_pool",
        "iqa_client",
        "window",
        "compose",
        "icon:True",
        "show",
    ]


def test_remote_iqa_composition_preserves_explicit_dependency_order(
    monkeypatch: Any,
) -> None:
    import pixelscope.ui.iqa_client_install as client_install_module

    events: list[str] = []
    result_pool = object()
    result_controller = SimpleNamespace(pool=result_pool)
    window = SimpleNamespace(iqa_controller=result_controller)
    installer = client_install_module.IqaClientInstaller(result_pool)  # type: ignore[arg-type]
    installer.controller = result_controller  # type: ignore[assignment]

    def client_factory(_base_url: str) -> object:
        return object()

    transport_pool = SimpleNamespace(client=client_factory)
    remote_workspace = object()
    remote_controller = SimpleNamespace(workspace=remote_workspace)
    inspection_controller = SimpleNamespace(pool=result_pool)
    historical_controller = SimpleNamespace(pool=result_pool)

    def install_remote_iqa(window_arg: object, *, client_factory: object) -> object:
        assert window_arg is window
        assert client_factory is transport_pool.client
        events.append("remote")
        return remote_controller

    def install_transport_lifecycle(window_arg: object, pool_arg: object) -> None:
        assert window_arg is window
        assert pool_arg is transport_pool
        assert window.remote_iqa_transport_pool is transport_pool
        events.append("transport_lifecycle")

    def install_diagnostics(window_arg: object, pool_arg: object) -> None:
        assert window_arg is window
        assert pool_arg is transport_pool
        events.append("diagnostics")

    def install_window_step(name: str) -> Any:
        def install(window_arg: object) -> None:
            assert window_arg is window
            events.append(name)

        return install

    def polish_setup(workspace_arg: object) -> None:
        assert workspace_arg is remote_workspace
        events.append("setup_presentation")

    def install_inspection(window_arg: object, *, pool: object) -> object:
        assert window_arg is window
        assert pool is result_pool
        events.append("inspection")
        return inspection_controller

    def install_historical(window_arg: object, *, pool: object) -> object:
        assert window_arg is window
        assert pool is result_pool
        events.append("historical")
        return historical_controller

    def install_historical_lifecycle(window_arg: object, controller_arg: object) -> None:
        assert window_arg is window
        assert controller_arg is historical_controller
        events.append("historical_lifecycle")

    monkeypatch.setattr(client_install_module, "ReusableIqaClientPool", lambda: transport_pool)
    monkeypatch.setattr(client_install_module, "install_remote_iqa", install_remote_iqa)
    monkeypatch.setattr(
        client_install_module,
        "install_remote_iqa_transport_lifecycle",
        install_transport_lifecycle,
    )
    monkeypatch.setattr(client_install_module, "install_remote_iqa_diagnostics", install_diagnostics)
    window_steps = {
        "install_remote_iqa_preview_lifecycle": "preview_lifecycle",
        "install_remote_iqa_submission_lifecycle": "submission_lifecycle",
        "install_remote_iqa_result_mapping": "result_mapping",
        "install_remote_iqa_result_retry": "result_retry",
        "install_remote_iqa_request_debug": "request_debug",
        "install_remote_iqa_replay_debug": "replay_debug",
        "install_iqa_scene_inspection_lifecycle": "inspection_lifecycle",
    }
    for attribute_name, event_name in window_steps.items():
        monkeypatch.setattr(
            client_install_module,
            attribute_name,
            install_window_step(event_name),
        )
    monkeypatch.setattr(client_install_module, "polish_remote_iqa_setup", polish_setup)
    monkeypatch.setattr(client_install_module, "install_iqa_scene_inspection", install_inspection)
    monkeypatch.setattr(
        client_install_module,
        "install_historical_iqa_results",
        install_historical,
    )
    monkeypatch.setattr(
        client_install_module,
        "install_historical_iqa_results_lifecycle",
        install_historical_lifecycle,
    )

    installer.install_runtime(window)  # type: ignore[arg-type]

    assert events == [
        "remote",
        "transport_lifecycle",
        "diagnostics",
        "preview_lifecycle",
        "submission_lifecycle",
        "result_mapping",
        "result_retry",
        "setup_presentation",
        "request_debug",
        "replay_debug",
        "inspection",
        "inspection_lifecycle",
        "historical",
        "historical_lifecycle",
    ]
    assert window.remote_iqa_transport_pool is transport_pool
    assert result_controller.pool is result_pool
    assert inspection_controller.pool is result_pool
    assert historical_controller.pool is result_pool
'''
    app_test.write_text(text, encoding='utf-8')

    lifecycle = Path('tests/unit/test_qt_lifecycle_architecture.py')
    text = lifecycle.read_text(encoding='utf-8')
    module_anchor = '    "src/pixelscope/ui/composition_lifetime.py",\n'
    text = replace_once(
        text,
        module_anchor,
        module_anchor + '    "src/pixelscope/ui/iqa_client_install.py",\n',
        'lifecycle module anchor',
    )
    rank_anchor = '''    "src/pixelscope/ui/composition_lifetime.py": {
        ("window", "window"),
        ("controller", "controller"),
    },
'''
    text = replace_once(
        text,
        rank_anchor,
        rank_anchor
        + '''    "src/pixelscope/ui/iqa_client_install.py": {
        ("_window", "window"),
        ("window", "window"),
    },
''',
        'rank owner anchor',
    )
    start = text.index('def test_production_composition_uses_final_rank4_non_owning_adapters')
    end = text.index('def test_non_owning_hooks_do_not_retain_their_owner', start)
    replacement = '''def test_production_composition_uses_final_rank4_non_owning_adapters() -> None:
    application_path = "src/pixelscope/app/application.py"
    client_path = "src/pixelscope/ui/iqa_client_install.py"
    application_tree = ast.parse(
        (REPOSITORY_ROOT / application_path).read_text(encoding="utf-8"),
        filename=application_path,
    )
    client_tree = ast.parse(
        (REPOSITORY_ROOT / client_path).read_text(encoding="utf-8"),
        filename=client_path,
    )

    application_hardened: set[str] = set()
    client_hardened: set[str] = set()
    legacy_imports: list[str] = []
    for tree, hardened in (
        (application_tree, application_hardened),
        (client_tree, client_hardened),
    ):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            imported = {alias.name for alias in node.names}
            if node.module == "pixelscope.ui.composition_lifetime":
                hardened.update(imported)
            if node.module in {
                "pixelscope.ui.analysis_export",
                "pixelscope.ui.iqa_submission",
                "pixelscope.ui.session",
            }:
                legacy_imports.extend(
                    name
                    for name in imported
                    if name in {
                        "install_analysis_export",
                        "install_remote_iqa",
                        "install_session",
                    }
                )

    assert {
        "install_analysis_export",
        "install_session",
        "release_command_row_metric_window",
    } <= application_hardened
    assert "install_remote_iqa" in client_hardened
    assert legacy_imports == []

    release_calls = [
        node
        for node in ast.walk(application_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "release_command_row_metric_window"
    ]
    assert len(release_calls) == 1


'''
    lifecycle.write_text(text[:start] + replacement + text[end:], encoding='utf-8')

    ui_test = Path('tests/ui/test_issue121_iqa_composition_seam.py')
    text = ui_test.read_text(encoding='utf-8')
    text = replace_once(
        text,
        'from pixelscope.app.main_window import MainWindow\n',
        'from pixelscope.app.main_window import MainWindow\n'
        'from pixelscope.remote.iqa_public_contract import (\n'
        '    IqaSubmissionIntent,\n'
        '    IqaSubmissionScene,\n'
        '    IqaSubmissionSource,\n'
        '    IqaVariant,\n'
        ')\n'
        'from pixelscope.remote.iqa_public_fixture import (\n'
        '    FixtureIqaProvider,\n'
        '    IqaFixtureProfile,\n'
        ')\n',
        'UI import anchor',
    )
    insert_at = text.index('\ndef test_iqa_runtime_installer_preserves_characterized_p5_order')
    public_test = '''

def test_public_provider_injection_drives_client_workspace(
    qtbot: object,
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path, IqaFixtureProfile.MINIMAL)
    installer = IqaClientInstaller.from_ports(provider, provider)
    window = MainWindow(window_contributions=(installer,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    variants = (IqaVariant("a", "A"), IqaVariant("b", "B"))
    intent = IqaSubmissionIntent(
        "comparison",
        variants,
        (
            IqaSubmissionScene(
                "scene-1",
                (
                    IqaSubmissionSource("a", tmp_path / "a.png"),
                    IqaSubmissionSource("b", tmp_path / "b.png"),
                ),
            ),
        ),
    )
    job = installer.execution_port.submit(intent)
    provider.advance(job)
    provider.advance(job)
    result_reference = installer.execution_port.get_result_reference(job)

    installer.open_published_result(result_reference)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: installer.workspace is not None and installer.workspace.model is not None,
        timeout=5000,
    )

    assert installer.execution_port is provider
    assert installer.result_access_port is provider
    assert installer.workspace is not None
    assert installer.workspace.model is not None
    assert installer.workspace.model.result.result_id == "fixture-minimal"
    assert not hasattr(window, "remote_iqa_controller")

    window.close()
'''
    text = text[:insert_at] + public_test + text[insert_at:]
    if 'from pathlib import Path\n' not in text:
        text = text.replace(
            'from __future__ import annotations\n\n',
            'from __future__ import annotations\n\nfrom pathlib import Path\n',
        )
    ui_test.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
