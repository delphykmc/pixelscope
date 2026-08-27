from __future__ import annotations

import json

from scripts import diagnose_remote_iqa as diagnostics


def _check(name: str, status: str) -> diagnostics.DiagnosticCheck:
    return diagnostics.DiagnosticCheck(name, status, "safe")


def _runtime(
    *,
    import_source: str = "current_repo",
    candidate_count: int = 1,
    current_first: bool | None = True,
) -> diagnostics.RuntimeEnvironment:
    return diagnostics.RuntimeEnvironment(
        python_version="3.10.0",
        cwd_is_repo_root=True,
        virtual_env_set=True,
        python_under_virtual_env=True,
        pythonpath_set=True,
        pixelscope_import_source=import_source,
        pixelscope_candidate_count=candidate_count,
        current_repo_candidate_first=current_first,
        editable_install=False,
        editable_target=None,
    )


def test_target_metadata_redacts_host_but_preserves_comparison_fingerprint() -> None:
    first, parsed_first = diagnostics._parse_target(
        "http://secret.internal.example:8001",
        "argument",
    )
    second, parsed_second = diagnostics._parse_target(
        "http://secret.internal.example:8001",
        "argument",
    )

    assert parsed_first is not None
    assert parsed_second is not None
    assert first.scheme == "http"
    assert first.host_present
    assert first.host_kind == "hostname"
    assert first.port == 8001
    assert first.target_fingerprint == second.target_fingerprint
    assert "secret.internal.example" not in json.dumps(first.__dict__)


def test_proxy_environment_reports_presence_without_values(monkeypatch) -> None:
    monkeypatch.setenv(
        "HTTP_PROXY",
        "http://user:password@secret-proxy.internal:8080",
    )
    monkeypatch.setenv("NO_PROXY", "secret-target.internal")

    proxy = diagnostics._proxy_environment()
    serialized = json.dumps(proxy.__dict__)

    assert proxy.any_proxy_set
    assert proxy.no_proxy_set
    assert proxy.variables_set["HTTP_PROXY"]
    assert proxy.variables_set["NO_PROXY"]
    assert "password" not in serialized
    assert "secret-proxy.internal" not in serialized
    assert "secret-target.internal" not in serialized


def test_network_interpretation_identifies_environment_proxy_interference() -> None:
    interpretation = diagnostics._interpret_network(
        True,
        _check("http_environment", "FAIL"),
        _check("http_direct", "PASS"),
        _check("production_client", "FAIL"),
    )

    assert interpretation == "proxy_or_environment_interference"


def test_network_interpretation_identifies_bypassed_proxy_interference() -> None:
    interpretation = diagnostics._interpret_network(
        True,
        _check("http_environment", "FAIL"),
        _check("http_direct", "PASS"),
        _check("production_client", "PASS"),
    )

    assert interpretation == "proxy_or_environment_interference_bypassed"


def test_network_interpretation_identifies_proxy_requirement() -> None:
    interpretation = diagnostics._interpret_network(
        True,
        _check("http_environment", "PASS"),
        _check("http_direct", "FAIL"),
        _check("production_client", "PASS"),
    )

    assert interpretation == "proxy_or_environment_required"


def test_runtime_checks_warn_for_duplicate_package_candidates_when_current_is_first() -> None:
    checks = diagnostics._runtime_checks(
        _runtime(candidate_count=2, current_first=True),
    )
    shadowing = next(check for check in checks if check.name == "pixelscope_path_shadowing")

    assert shadowing.status == "WARN"
    assert "current repo first" in (shadowing.detail or "")


def _patch_reachable_runtime(monkeypatch, *, environment_status: str = "PASS") -> None:
    monkeypatch.setattr(diagnostics, "_runtime_environment", _runtime)

    def dns_probe(_host: str, _port: int):
        return (
            1,
            ("IPv4",),
            diagnostics.DiagnosticCheck("dns_resolution", "PASS", "addresses=1"),
        )

    def tcp_probe(_host: str, _port: int, _timeout: float):
        return True, diagnostics.DiagnosticCheck("tcp_connect", "PASS", "connected")

    def http_probe(_url: str, _timeout: float, *, trust_env: bool):
        return diagnostics.DiagnosticCheck(
            "http_environment" if trust_env else "http_direct",
            environment_status if trust_env else "PASS",
            "timeout" if trust_env and environment_status == "FAIL" else "HTTP 404",
        )

    def production_probe(_url: str, _timeout: float):
        return diagnostics.DiagnosticCheck("production_client", "PASS", "HTTP 404"), False

    monkeypatch.setattr(diagnostics, "_dns_probe", dns_probe)
    monkeypatch.setattr(diagnostics, "_tcp_probe", tcp_probe)
    monkeypatch.setattr(diagnostics, "_http_probe", http_probe)
    monkeypatch.setattr(diagnostics, "_production_client_probe", production_probe)


def test_run_diagnostics_never_emits_raw_server_or_proxy_values(monkeypatch) -> None:
    secret_server = "http://very-secret-iqa.internal:8001"
    secret_proxy = "http://user:password@very-secret-proxy.internal:8080"
    monkeypatch.setenv("HTTP_PROXY", secret_proxy)
    _patch_reachable_runtime(monkeypatch)

    report = diagnostics.run_diagnostics(secret_server, 1.0)
    serialized = json.dumps(report, default=lambda value: value.__dict__)

    assert report.passed
    assert report.blocking_failures == ()
    assert report.network is not None
    assert report.network.production_client_trust_env is False
    assert report.network.interpretation == "transport_reachable"
    assert "very-secret-iqa.internal" not in serialized
    assert "very-secret-proxy.internal" not in serialized
    assert "password" not in serialized


def test_environment_proxy_failure_is_warning_when_production_direct_transport_passes(
    monkeypatch,
) -> None:
    _patch_reachable_runtime(monkeypatch, environment_status="FAIL")

    report = diagnostics.run_diagnostics("http://secret.internal.example:8001", 1.0)

    assert report.passed
    assert report.blocking_failures == ()
    assert report.network is not None
    assert report.network.http_with_environment.status == "FAIL"
    assert report.network.http_direct.status == "PASS"
    assert report.network.production_client.status == "PASS"
    assert report.network.production_client_trust_env is False
    assert report.network.interpretation == "proxy_or_environment_interference_bypassed"


def test_wrong_import_source_remains_a_readiness_blocker(monkeypatch) -> None:
    _patch_reachable_runtime(monkeypatch)
    monkeypatch.setattr(
        diagnostics,
        "_runtime_environment",
        lambda: _runtime(import_source="external_path", current_first=False),
    )

    report = diagnostics.run_diagnostics("http://secret.internal.example:8001", 1.0)

    assert not report.passed
    assert "pixelscope_import_source" in report.blocking_failures
