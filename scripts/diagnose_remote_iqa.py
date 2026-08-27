from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import ipaddress
import json
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import httpx

from pixelscope.remote import iqa_client
from pixelscope.remote.iqa_client import HttpIqaJobClient, IqaClientError, IqaClientErrorKind

DIAGNOSTIC_JOB_ID = "pixelscope-diagnostic-missing-job"
DIAGNOSTIC_PATH = f"/v1/iqa/jobs/{DIAGNOSTIC_JOB_ID}"
PROXY_ENV_NAMES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    status: str
    detail: str | None = None
    duration_ms: float | None = None


@dataclass(frozen=True)
class RuntimeEnvironment:
    python_version: str
    cwd_is_repo_root: bool
    virtual_env_set: bool
    python_under_virtual_env: bool | None
    pythonpath_set: bool
    pixelscope_import_source: str
    pixelscope_candidate_count: int
    current_repo_candidate_first: bool | None
    editable_install: bool | None
    editable_target: str | None


@dataclass(frozen=True)
class TargetMetadata:
    source: str
    scheme: str | None
    host_present: bool
    host_kind: str | None
    port: int | None
    target_fingerprint: str | None


@dataclass(frozen=True)
class ProxyEnvironment:
    variables_set: dict[str, bool]
    any_proxy_set: bool
    no_proxy_set: bool


@dataclass(frozen=True)
class NetworkObservation:
    dns_address_count: int | None
    dns_families: tuple[str, ...]
    tcp_reachable: bool | None
    http_with_environment: DiagnosticCheck
    http_direct: DiagnosticCheck
    production_client: DiagnosticCheck
    interpretation: str


@dataclass(frozen=True)
class RemoteIqaDiagnosticReport:
    runtime: RuntimeEnvironment
    target: TargetMetadata
    proxy: ProxyEnvironment
    checks: tuple[DiagnosticCheck, ...]
    network: NetworkObservation | None

    @property
    def passed(self) -> bool:
        return all(check.status != "FAIL" for check in self.checks)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolved(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _classify_module_path(module_path: Path, repo_src: Path) -> str:
    module = module_path.resolve()
    current_src = repo_src.resolve()
    if _is_under(module, current_src):
        return "current_repo"
    if "site-packages" in {part.casefold() for part in module.parts}:
        return "site_packages"
    return "external_path"


def _package_candidates(repo_src: Path) -> tuple[int, bool | None]:
    candidates: list[Path] = []
    current_index: int | None = None
    current_src = repo_src.resolve()
    for entry in sys.path:
        if not entry:
            entry_path = Path.cwd()
        else:
            try:
                entry_path = Path(entry).expanduser().resolve()
            except OSError:
                continue
        if not (entry_path / "pixelscope").is_dir():
            continue
        index = len(candidates)
        candidates.append(entry_path)
        if entry_path == current_src and current_index is None:
            current_index = index
    if current_index is None:
        return len(candidates), None
    return len(candidates), current_index == 0


def _editable_install_target(repo_root: Path) -> tuple[bool | None, str | None]:
    try:
        distribution = importlib.metadata.distribution("pixelscope")
        raw = distribution.read_text("direct_url.json")
    except importlib.metadata.PackageNotFoundError:
        return False, None
    if raw is None:
        return False, None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, "unknown"
    directory_info = data.get("dir_info")
    if not isinstance(directory_info, dict) or directory_info.get("editable") is not True:
        return False, None
    url = data.get("url")
    if not isinstance(url, str):
        return True, "unknown"
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return True, "non_file"
    decoded = url2pathname(unquote(parsed.path))
    if parsed.netloc:
        decoded = f"//{parsed.netloc}{decoded}"
    try:
        target = Path(decoded).resolve()
    except OSError:
        return True, "unknown"
    return True, "current_repo" if target == repo_root.resolve() else "external_repo"


def _python_under_virtual_env() -> bool | None:
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if not virtual_env:
        return None
    try:
        return _is_under(Path(sys.executable).resolve(), _resolved(virtual_env))
    except OSError:
        return None


def _runtime_environment() -> RuntimeEnvironment:
    repo_root = _repo_root()
    repo_src = repo_root / "src"
    module_file = getattr(iqa_client, "__file__", None)
    import_source = (
        _classify_module_path(Path(module_file), repo_src)
        if isinstance(module_file, str)
        else "unknown"
    )
    candidate_count, current_first = _package_candidates(repo_src)
    editable, editable_target = _editable_install_target(repo_root)
    try:
        cwd_is_repo_root = Path.cwd().resolve() == repo_root.resolve()
    except OSError:
        cwd_is_repo_root = False
    return RuntimeEnvironment(
        python_version=(
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        ),
        cwd_is_repo_root=cwd_is_repo_root,
        virtual_env_set=bool(os.environ.get("VIRTUAL_ENV")),
        python_under_virtual_env=_python_under_virtual_env(),
        pythonpath_set=bool(os.environ.get("PYTHONPATH")),
        pixelscope_import_source=import_source,
        pixelscope_candidate_count=candidate_count,
        current_repo_candidate_first=current_first,
        editable_install=editable,
        editable_target=editable_target,
    )


def _proxy_environment() -> ProxyEnvironment:
    flags = {name: bool(os.environ.get(name)) for name in PROXY_ENV_NAMES}
    proxy_names = {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    }
    no_proxy_names = {"NO_PROXY", "no_proxy"}
    return ProxyEnvironment(
        variables_set=flags,
        any_proxy_set=any(flags[name] for name in proxy_names),
        no_proxy_set=any(flags[name] for name in no_proxy_names),
    )


def _host_kind(host: str) -> str:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return "hostname"
    return "ipv4" if address.version == 4 else "ipv6"


def _parse_target(
    value: str | None,
    source: str,
) -> tuple[TargetMetadata, httpx.URL | None]:
    if not value:
        return TargetMetadata(source, None, False, None, None, None), None
    try:
        parsed = httpx.URL(value)
    except (httpx.InvalidURL, TypeError, ValueError):
        return TargetMetadata(source, None, False, None, None, None), None
    scheme = str(parsed.scheme)
    host = parsed.host
    if scheme not in {"http", "https"} or not host:
        metadata = TargetMetadata(
            source,
            scheme or None,
            bool(host),
            None,
            parsed.port,
            None,
        )
        return metadata, None
    port = parsed.port or (443 if scheme == "https" else 80)
    fingerprint_input = f"{scheme}://{host.casefold()}:{port}"
    fingerprint = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:12]
    return (
        TargetMetadata(source, scheme, True, _host_kind(host), port, fingerprint),
        parsed,
    )


def _duration_ms(started: float) -> float:
    return round(max(0.0, (time.monotonic() - started) * 1000.0), 2)


def _dns_probe(
    host: str,
    port: int,
) -> tuple[int | None, tuple[str, ...], DiagnosticCheck]:
    started = time.monotonic()
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        check = DiagnosticCheck(
            "dns_resolution",
            "FAIL",
            "gaierror",
            _duration_ms(started),
        )
        return None, (), check
    except OSError:
        check = DiagnosticCheck(
            "dns_resolution",
            "FAIL",
            "oserror",
            _duration_ms(started),
        )
        return None, (), check
    families: set[str] = set()
    for family, *_rest in addresses:
        if family == socket.AF_INET:
            families.add("IPv4")
        elif family == socket.AF_INET6:
            families.add("IPv6")
        else:
            families.add("other")
    check = DiagnosticCheck(
        "dns_resolution",
        "PASS",
        f"addresses={len(addresses)}",
        _duration_ms(started),
    )
    return len(addresses), tuple(sorted(families)), check


def _tcp_probe(
    host: str,
    port: int,
    timeout_seconds: float,
) -> tuple[bool, DiagnosticCheck]:
    started = time.monotonic()
    try:
        connection = socket.create_connection((host, port), timeout=timeout_seconds)
    except TimeoutError:
        check = DiagnosticCheck("tcp_connect", "FAIL", "timeout", _duration_ms(started))
        return False, check
    except OSError as exc:
        check = DiagnosticCheck(
            "tcp_connect",
            "FAIL",
            exc.__class__.__name__,
            _duration_ms(started),
        )
        return False, check
    connection.close()
    return True, DiagnosticCheck(
        "tcp_connect",
        "PASS",
        "connected",
        _duration_ms(started),
    )


def _http_probe(
    base_url: str,
    timeout_seconds: float,
    *,
    trust_env: bool,
) -> DiagnosticCheck:
    started = time.monotonic()
    name = "http_environment" if trust_env else "http_direct"
    try:
        with httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout_seconds),
            verify=True,
            trust_env=trust_env,
        ) as client:
            response = client.get(DIAGNOSTIC_PATH)
    except httpx.TimeoutException:
        return DiagnosticCheck(name, "FAIL", "timeout", _duration_ms(started))
    except httpx.ProxyError:
        return DiagnosticCheck(name, "FAIL", "proxy_error", _duration_ms(started))
    except httpx.ConnectError:
        return DiagnosticCheck(name, "FAIL", "connect_error", _duration_ms(started))
    except httpx.HTTPError as exc:
        return DiagnosticCheck(
            name,
            "FAIL",
            exc.__class__.__name__,
            _duration_ms(started),
        )
    status = "WARN" if response.status_code >= 500 else "PASS"
    return DiagnosticCheck(
        name,
        status,
        f"HTTP {response.status_code}",
        _duration_ms(started),
    )


def _production_client_probe(
    base_url: str,
    timeout_seconds: float,
) -> DiagnosticCheck:
    started = time.monotonic()
    client = HttpIqaJobClient(base_url, timeout_seconds=timeout_seconds)
    try:
        status = client.get_status(DIAGNOSTIC_JOB_ID)
    except IqaClientError as error:
        if error.kind is IqaClientErrorKind.HTTP:
            detail = (
                f"HTTP {error.status_code}"
                if error.status_code is not None
                else "http_error"
            )
            return DiagnosticCheck(
                "production_client",
                "PASS",
                detail,
                _duration_ms(started),
            )
        if error.kind is IqaClientErrorKind.PROTOCOL:
            return DiagnosticCheck(
                "production_client",
                "WARN",
                "protocol_response_received",
                _duration_ms(started),
            )
        return DiagnosticCheck(
            "production_client",
            "FAIL",
            error.kind.value,
            _duration_ms(started),
        )
    finally:
        client.close()
    return DiagnosticCheck(
        "production_client",
        "WARN",
        f"diagnostic_job_unexpectedly_exists:{status.state.value}",
        _duration_ms(started),
    )


def _interpret_network(
    tcp_reachable: bool,
    http_environment: DiagnosticCheck,
    http_direct: DiagnosticCheck,
    production_client: DiagnosticCheck,
) -> str:
    env_ok = http_environment.status != "FAIL"
    direct_ok = http_direct.status != "FAIL"
    production_ok = production_client.status != "FAIL"
    if not tcp_reachable:
        return "tcp_unreachable"
    if direct_ok and not env_ok:
        return "proxy_or_environment_interference"
    if env_ok and not direct_ok:
        return "proxy_or_environment_required"
    if env_ok and direct_ok and not production_ok:
        return "production_client_difference"
    if not env_ok and not direct_ok:
        return "http_layer_failure"
    return "transport_reachable"


def _runtime_checks(runtime: RuntimeEnvironment) -> list[DiagnosticCheck]:
    checks = [
        DiagnosticCheck(
            "cwd_repo_root",
            "PASS" if runtime.cwd_is_repo_root else "WARN",
            "current_repo" if runtime.cwd_is_repo_root else "different_directory",
        ),
        DiagnosticCheck(
            "pixelscope_import_source",
            "PASS" if runtime.pixelscope_import_source == "current_repo" else "FAIL",
            runtime.pixelscope_import_source,
        ),
    ]
    if runtime.virtual_env_set:
        checks.append(
            DiagnosticCheck(
                "python_under_virtual_env",
                "PASS" if runtime.python_under_virtual_env else "FAIL",
                "yes" if runtime.python_under_virtual_env else "no",
            )
        )
    else:
        checks.append(
            DiagnosticCheck("python_under_virtual_env", "WARN", "VIRTUAL_ENV unset")
        )
    if runtime.pixelscope_candidate_count <= 1:
        checks.append(
            DiagnosticCheck("pixelscope_path_shadowing", "PASS", "single_candidate")
        )
    elif runtime.current_repo_candidate_first:
        checks.append(
            DiagnosticCheck(
                "pixelscope_path_shadowing",
                "WARN",
                f"{runtime.pixelscope_candidate_count} candidates; current repo first",
            )
        )
    else:
        checks.append(
            DiagnosticCheck(
                "pixelscope_path_shadowing",
                "FAIL",
                f"{runtime.pixelscope_candidate_count} candidates; current repo not first",
            )
        )
    return checks


def run_diagnostics(
    server_base_url: str | None,
    timeout_seconds: float,
) -> RemoteIqaDiagnosticReport:
    runtime = _runtime_environment()
    proxy = _proxy_environment()
    source = "argument" if server_base_url else "PIXELSCOPE_P5G_SERVER"
    raw_target = server_base_url or os.environ.get("PIXELSCOPE_P5G_SERVER")
    target, parsed = _parse_target(raw_target, source)
    checks = _runtime_checks(runtime)

    if parsed is None or raw_target is None:
        checks.append(DiagnosticCheck("server_target", "FAIL", "missing_or_invalid"))
        return RemoteIqaDiagnosticReport(runtime, target, proxy, tuple(checks), None)

    checks.append(DiagnosticCheck("server_target", "PASS", "valid_http_url"))
    host = parsed.host
    assert host is not None
    port = target.port
    assert port is not None

    dns_count, dns_families, dns_check = _dns_probe(host, port)
    checks.append(dns_check)
    tcp_reachable, tcp_check = _tcp_probe(host, port, timeout_seconds)
    checks.append(tcp_check)

    http_environment = _http_probe(raw_target, timeout_seconds, trust_env=True)
    http_direct = _http_probe(raw_target, timeout_seconds, trust_env=False)
    production = _production_client_probe(raw_target, timeout_seconds)
    checks.extend((http_environment, http_direct, production))
    interpretation = _interpret_network(
        tcp_reachable,
        http_environment,
        http_direct,
        production,
    )
    network = NetworkObservation(
        dns_address_count=dns_count,
        dns_families=dns_families,
        tcp_reachable=tcp_reachable,
        http_with_environment=http_environment,
        http_direct=http_direct,
        production_client=production,
        interpretation=interpretation,
    )
    return RemoteIqaDiagnosticReport(runtime, target, proxy, tuple(checks), network)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run read-only Remote IQA environment and connectivity diagnostics. "
            "No job is created and host names, IP addresses, proxy values, local paths, "
            "credentials, and response bodies are not printed."
        )
    )
    parser.add_argument(
        "server_base_url",
        nargs="?",
        help="Optional server URL. If omitted, PIXELSCOPE_P5G_SERVER is used.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if args.timeout_seconds <= 0.0:
        parser.error("--timeout-seconds must be positive")

    report = run_diagnostics(args.server_base_url, args.timeout_seconds)
    payload: dict[str, Any] = asdict(report)
    payload["passed"] = report.passed
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
