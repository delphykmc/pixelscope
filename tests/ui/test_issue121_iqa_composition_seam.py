from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QDockWidget

from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_public_contract import IqaJobReference
from pixelscope.remote.iqa_public_fixture import (
    FixtureIqaProvider,
    IqaFixtureProfile,
)
from pixelscope.ui import iqa_client_install as client_install
from pixelscope.ui.iqa_client_install import IqaClientInstaller

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def test_base_window_can_construct_without_iqa_client(qtbot: object) -> None:
    window = MainWindow(window_contributions=())
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert not hasattr(window, "iqa_workspace")
    assert not hasattr(window, "iqa_controller")
    assert not hasattr(window, "iqa_dock")
    assert not hasattr(window, "iqa_workspace_action")
    assert all(dock.objectName() != "iqaWorkspaceDock" for dock in window.findChildren(QDockWidget))

    window.close()


def test_explicit_iqa_client_owns_compatibility_surface(qtbot: object) -> None:
    installer = IqaClientInstaller()
    window = MainWindow(window_contributions=(installer,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.iqa_workspace is installer.workspace
    assert window.iqa_controller is installer.controller
    assert window.iqa_dock is installer.dock
    assert window.iqa_workspace_action is installer.action
    assert window.action_map["Open IQA Result..."] is not None
    assert window.action_map["Show IQA Workspace"] is installer.action
    assert installer.dock is not None
    assert installer.dock.widget() is installer.workspace
    iqa_docks = [
        dock for dock in window.findChildren(QDockWidget) if dock.objectName() == "iqaWorkspaceDock"
    ]
    assert iqa_docks == [installer.dock]

    window.close()


def test_public_provider_injection_drives_client_execution_workflow(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path, IqaFixtureProfile.MINIMAL)
    installer = IqaClientInstaller.from_ports(provider, provider)
    window = MainWindow(window_contributions=(installer,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    path_a = tmp_path / "a.png"
    path_b = tmp_path / "b.png"
    path_a.write_bytes(b"fixture-a")
    path_b.write_bytes(b"fixture-b")
    documents = (
        SimpleNamespace(source_path=path_a, document_id="a", generation=1),
        SimpleNamespace(source_path=path_b, document_id="b", generation=1),
    )
    monkeypatch.setattr(window, "current_comparison_documents", lambda: list(documents))

    installer.install_runtime(window)
    shell = window.remote_iqa_workspace
    execution_controller = window.remote_iqa_controller

    assert installer.execution_controller is execution_controller
    assert installer.execution_port is provider
    assert installer.result_access_port is provider
    assert shell.current_submit.isEnabled()

    shell.current_submit.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: shell.jobs_tree.topLevelItemCount() == 1,
        timeout=5000,
    )
    item = shell.jobs_tree.topLevelItem(0)
    assert item.text(2) == "queued"

    job_reference = IqaJobReference("fixture-job-0001")
    provider.advance(job_reference)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: item.text(2) == "running",
        timeout=5000,
    )
    provider.advance(job_reference)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: item.text(2) == "completed" and shell.open_button.isEnabled(),
        timeout=5000,
    )

    shell.open_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: installer.workspace is not None and installer.workspace.model is not None,
        timeout=5000,
    )

    assert installer.workspace is not None
    assert installer.workspace.model is not None
    assert installer.workspace.model.result.result_id == "fixture-minimal"

    window.close()


def test_public_provider_injection_uses_client_cancel_action(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    provider = FixtureIqaProvider(tmp_path, IqaFixtureProfile.MINIMAL)
    installer = IqaClientInstaller.from_ports(provider, provider)
    window = MainWindow(window_contributions=(installer,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    path_a = tmp_path / "a.png"
    path_b = tmp_path / "b.png"
    documents = (
        SimpleNamespace(source_path=path_a, document_id="a", generation=1),
        SimpleNamespace(source_path=path_b, document_id="b", generation=1),
    )
    monkeypatch.setattr(window, "current_comparison_documents", lambda: list(documents))

    installer.install_runtime(window)
    shell = window.remote_iqa_workspace
    shell.current_submit.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: shell.jobs_tree.topLevelItemCount() == 1 and shell.cancel_button.isEnabled(),
        timeout=5000,
    )

    item = shell.jobs_tree.topLevelItem(0)
    shell.cancel_button.click()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: item.text(2) == "cancelled",
        timeout=5000,
    )
    assert not shell.cancel_button.isEnabled()
    assert not shell.open_button.isEnabled()

    window.close()


def test_iqa_runtime_installer_preserves_characterized_p5_order(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = IqaClientInstaller()
    window = MainWindow(window_contributions=(installer,))
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    calls: list[str] = []
    transport_pool = SimpleNamespace(client=lambda: None)
    remote_workspace = object()
    remote_controller = SimpleNamespace(workspace=remote_workspace)
    historical_controller = object()

    monkeypatch.setattr(
        client_install,
        "ReusableIqaClientPool",
        lambda: transport_pool,
    )
    monkeypatch.setattr(
        client_install,
        "install_remote_iqa",
        lambda _window, *, client_factory: (calls.append("remote_iqa") or remote_controller),
    )

    def record(name: str):
        def callback(*_args: object, **_kwargs: object) -> None:
            calls.append(name)

        return callback

    monkeypatch.setattr(
        client_install,
        "install_remote_iqa_transport_lifecycle",
        record("transport_lifecycle"),
    )
    monkeypatch.setattr(
        client_install,
        "install_remote_iqa_diagnostics",
        record("diagnostics"),
    )
    monkeypatch.setattr(
        client_install,
        "install_remote_iqa_preview_lifecycle",
        record("preview_lifecycle"),
    )
    monkeypatch.setattr(
        client_install,
        "install_remote_iqa_submission_lifecycle",
        record("submission_lifecycle"),
    )
    monkeypatch.setattr(
        client_install,
        "install_remote_iqa_result_mapping",
        record("result_mapping"),
    )
    monkeypatch.setattr(
        client_install,
        "install_remote_iqa_result_retry",
        record("result_retry"),
    )
    monkeypatch.setattr(
        client_install,
        "polish_remote_iqa_setup",
        record("setup_polish"),
    )
    monkeypatch.setattr(
        client_install,
        "install_remote_iqa_request_debug",
        record("request_debug"),
    )
    monkeypatch.setattr(
        client_install,
        "install_remote_iqa_replay_debug",
        record("replay_debug"),
    )
    monkeypatch.setattr(
        client_install,
        "install_iqa_scene_inspection",
        record("scene_inspection"),
    )
    monkeypatch.setattr(
        client_install,
        "install_iqa_scene_inspection_lifecycle",
        record("scene_inspection_lifecycle"),
    )

    def install_history(*_args: object, **_kwargs: object) -> object:
        calls.append("historical_results")
        return historical_controller

    monkeypatch.setattr(client_install, "install_historical_iqa_results", install_history)
    monkeypatch.setattr(
        client_install,
        "install_historical_iqa_results_lifecycle",
        record("historical_lifecycle"),
    )

    installer.install_runtime(window)

    assert calls == [
        "remote_iqa",
        "transport_lifecycle",
        "diagnostics",
        "preview_lifecycle",
        "submission_lifecycle",
        "result_mapping",
        "result_retry",
        "setup_polish",
        "request_debug",
        "replay_debug",
        "scene_inspection",
        "scene_inspection_lifecycle",
        "historical_results",
        "historical_lifecycle",
    ]
    assert window.__dict__["remote_iqa_transport_pool"] is transport_pool

    window.close()
