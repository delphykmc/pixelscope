from __future__ import annotations

import json

from scripts.diagnose_remote_iqa import (
    DiagnosticCheck,
    RuntimeEnvironment,
    _interpret_network,
    _parse_target,
    _proxy_environment,
    _runtime_checks,
    run_diagnostics,
)


def _check(name: str, status: str) -> DiagnosticCheck:
    return DiagnosticCheck(name, status, "safe")


def test_target_metadata_redacts_host_but_preserves_comparison_fingerprint() -> None:
    first, parsed_first = _parse_target(
        "http://secret.internal.example:8001",
        "argument",
    )
    second, parsed_second = _parse_target(
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

    proxy = _proxy_environment()
    serialized = json.dumps(proxy.__dict__)

    assert proxy.any_proxy_set
    assert proxy.no_proxy_set
    assert proxy.variables_set["HTTP_PROXY"]
    assert proxy.variables_set["NO_PROXY"]
    assert "password" not in serialized
    assert "secret-proxy.internal" not in serialized
    assert "secret-target.internal" not in serialized


def test_network_interpretation_identifies_environment_proxy_interference() -> None:
    interpretation = _interpret_network(
        True,
        _check("http_environment", "FAIL"),
        _check("http_direct", "PASS"),
        _check("production_client", "FAIL"),
    )

    assert interpretation == "proxy_or_environment_interference"


def test_network_interpretation_identifies_bypassed_proxy_interference() -> None:
    interpretation = _interpret_network(
        True,
        _check("http_environment", "FAIL"),
        _check("http_direct", "PASS"),
        _check("production_client", "PASS"),
    )

    assert interpretation == "proxy_or_environment_interference_bypassed"


def test_network_interpretation_identifies_proxy_requirement() -> None:
    interpretation = _interpret_network(
        True,
        _check("http_environment", "PASS"),
        _check("http_direct", "FAIL"),
        _check("production_client", "PASS"),
    )

    assert interpretation == "proxy_or_environment_required"


def test_runtime_checks_warn_for_duplicate_package_candidates_when_current_is_first() -> None:
    runtime = RuntimeEnvironment(
        python_version="3.10.0",
        cwd_is_repo_root=True,
        virtual_env_set=True,
        python_under_virtual_env=True,
        pythonpath_set=True,
        pixelscope_import_source="current_repo",
        pixelscope_candidate_count=2,
        current_repo_candidate_first=True,
        editable_install=True,
        editable_target="external_repo",
    )

    checks = _runtime_checks(runtime)
    shadowing = next(check for check in checks if check.name == "pixelscope_path_shadowing")

    assert shadowing.status == "WARN"
    assert "current repo first" in (shadowing.detail or "")


def _patch_reachable_runtime(monkeypatch, *, environment_status: str = "PASS") -> None:
    monkeypatch.setattr(
        "scripts.diagnose_remote_iqa._runtime_environment",
        lambda: RuntimeEnvironment(
            python_version="3.10.0",
            cwd_is_repo_root=True,
            virtual_env_set=True,
            python_under_virtual_env=True,
            pythonpath_set=True,
            pixelscope_import_source="current_repo",
            pixelscope_candidate_count=1,
            current_repo_candidate_first=True,
            editable_install=False,
            editable_target=None,
        ),
    )
    monkeypatch.setattr(
        "scripts.diagnose_remote_iqa._dns_probe",
        lambda _host, _port: (
            1,
            ("IPv4",),
            DiagnosticCheck("dns_resolution", "PASS", "addresses=1"),
        ),
    )
    monkeypatch.setattr(
        "scripts.diagnose_remote_iqa._tcp_probe",
        lambda _host, _port, _timeout: (
            True,
            DiagnosticCheck("tcp_connect", "PASS", "connected"),
        ),
    )
    monkeypatch.setattr(
        "scripts.diagnose_remote_iqa._http_probe",
        lambda _url, _timeout, *, trust_env: DiagnosticCheck(
            "http_environment" if trust_env else "http_direct",
            environment_status if trust_env else "PASS",
            "timeout" if trust_env and environment_status == "FAIL" else "HTTP 404",
        ),
    )
    monkeypatch.setattr(
        "scripts.diagnose_remote_iqa._production_client_probe",
        lambda _url, _timeout: (
            DiagnosticCheck("production_client", "PASS", "HTTP 404"),
            False,
        ),
    )


def test_run_diagnostics_never_emits_raw_server_or_proxy_values(monkeypatch) -> None:
    secret_server = "http://very-secret-iqa.internal:8001"
    secret_proxy = "http://user:password@very-secret-proxy.internal:8080"
    monkeypatch.setenv("HTTP_PROXY", secret_proxy)
    _patch_reachable_runtime(monkeypatch)

    report = run_diagnostics(secret_server, 1.0)
    serialized = json.dumps(report, default=lambda value: value.__dict__)

    assert report.passed
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

    report = run_diagnostics("http://secret.internal.example:8001", 1.0)

    assert report.passed
    assert report.network is not None
    assert report.network.http_with_environment.status == "FAIL"
    assert report.network.http_direct.status == "PASS"
    assert report.network.production_client.status == "PASS"
    assert report.network.production_client_trust_env is False
    assert report.network.interpretation == "proxy_or_environment_interference_bypassed"
