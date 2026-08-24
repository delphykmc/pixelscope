from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pixelscope.app.application as application_module


def test_remote_iqa_composition_preserves_explicit_dependency_order(
    monkeypatch: Any,
) -> None:
    events: list[str] = []
    result_pool = object()
    result_controller = SimpleNamespace(_pool=result_pool)
    window = SimpleNamespace(iqa_controller=result_controller)

    def client_factory(_base_url: str) -> object:
        return object()

    transport_pool = SimpleNamespace(client=client_factory)
    remote_workspace = object()
    remote_controller = SimpleNamespace(workspace=remote_workspace)
    inspection_controller = SimpleNamespace(_pool=object())
    historical_controller = SimpleNamespace(_pool=object())

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

    def install_inspection(window_arg: object) -> object:
        assert window_arg is window
        events.append("inspection")
        return inspection_controller

    def install_historical(window_arg: object) -> object:
        assert window_arg is window
        events.append("historical")
        return historical_controller

    def install_historical_lifecycle(
        window_arg: object,
        controller_arg: object,
    ) -> None:
        assert window_arg is window
        assert controller_arg is historical_controller
        events.append("historical_lifecycle")

    monkeypatch.setattr(application_module, "install_remote_iqa", install_remote_iqa)
    monkeypatch.setattr(
        application_module,
        "install_remote_iqa_transport_lifecycle",
        install_transport_lifecycle,
    )
    monkeypatch.setattr(
        application_module,
        "install_remote_iqa_diagnostics",
        install_diagnostics,
    )
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
            application_module,
            attribute_name,
            install_window_step(event_name),
        )
    monkeypatch.setattr(application_module, "polish_remote_iqa_setup", polish_setup)
    monkeypatch.setattr(
        application_module,
        "install_iqa_scene_inspection",
        install_inspection,
    )
    monkeypatch.setattr(
        application_module,
        "install_historical_iqa_results",
        install_historical,
    )
    monkeypatch.setattr(
        application_module,
        "install_historical_iqa_results_lifecycle",
        install_historical_lifecycle,
    )

    application_module._compose_remote_iqa(
        window,  # type: ignore[arg-type]
        result_pool=result_pool,  # type: ignore[arg-type]
        transport_pool=transport_pool,  # type: ignore[arg-type]
    )

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
    assert result_controller._pool is result_pool
    assert inspection_controller._pool is result_pool
    assert historical_controller._pool is result_pool
