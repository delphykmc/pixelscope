from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QDockWidget

from pixelscope.app.main_window import MainWindow
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
    assert all(
        dock.objectName() != "iqaWorkspaceDock" for dock in window.findChildren(QDockWidget)
    )

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
        dock
        for dock in window.findChildren(QDockWidget)
        if dock.objectName() == "iqaWorkspaceDock"
    ]
    assert iqa_docks == [installer.dock]

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
        lambda _window, *, client_factory: (
            calls.append("remote_iqa") or remote_controller
        ),
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
