from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest

from pixelscope.core.diagnostics import (
    MAX_FAILURE_MESSAGE_CHARS,
    MAX_RECENT_FAILURES,
    DifferenceCacheDiagnostics,
    FailureDiagnostic,
    RuntimeDiagnosticsSnapshot,
    SourceResidencyDiagnostics,
    WorkerDiagnostics,
    WorkerPoolDiagnostics,
    format_runtime_diagnostics,
    sanitize_failure_message,
)
from pixelscope.core.preload import PreloadDiagnostics


def _snapshot(
    *,
    failures: tuple[FailureDiagnostic, ...] = (),
) -> RuntimeDiagnosticsSnapshot:
    return RuntimeDiagnosticsSnapshot(
        source=SourceResidencyDiagnostics(
            used_bytes=1536,
            budget_bytes=1024,
            resident_count=3,
            over_budget_bytes=512,
        ),
        difference=DifferenceCacheDiagnostics(
            used_bytes=256,
            budget_bytes=2048,
            entry_count=2,
        ),
        workers=WorkerDiagnostics(
            foreground_loads=WorkerPoolDiagnostics(active_count=2, max_count=2),
            preload=WorkerPoolDiagnostics(active_count=1, max_count=1),
        ),
        preload=PreloadDiagnostics(
            enabled=True,
            planned_target_count=4,
            active_worker_count=1,
            successful_retained_count=7,
            stale_drop_count=5,
            cancellation_request_count=3,
            failure_count=2,
        ),
        normal_load_stale_drop_count=6,
        recent_failures=failures,
    )


def test_snapshot_and_nested_models_are_frozen() -> None:
    snapshot = _snapshot()

    with pytest.raises(FrozenInstanceError):
        snapshot.normal_load_stale_drop_count = 9  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.source.used_bytes = 0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        snapshot.workers.preload.max_count = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("factory", "field"),
    (
        (lambda: SourceResidencyDiagnostics(-1, 1, 0, 0), "used_bytes"),
        (lambda: DifferenceCacheDiagnostics(0, 1, -1), "entry_count"),
        (lambda: WorkerPoolDiagnostics(0, -1), "max_count"),
    ),
)
def test_numeric_models_reject_negative_values(
    factory: Callable[[], object],
    field: str,
) -> None:
    with pytest.raises(ValueError, match=rf"{field} must be non-negative"):
        factory()


def test_numeric_models_reject_bool_values() -> None:
    with pytest.raises(TypeError, match="used_bytes must be int"):
        SourceResidencyDiagnostics(True, 1, 0, 0)  # type: ignore[arg-type]


def test_formatter_is_deterministic_and_has_fixed_section_order() -> None:
    failure = FailureDiagnostic.from_exception("foreground-load", "decode", ValueError("bad"))
    snapshot = _snapshot(failures=(failure,))

    first = format_runtime_diagnostics(snapshot)
    second = format_runtime_diagnostics(snapshot)

    assert first == second
    assert [
        first.index(section)
        for section in (
            "Source Residency",
            "Difference Map Cache",
            "Workers",
            "Preload",
            "Stale Results",
            "Recent Failures",
        )
    ] == sorted(
        first.index(section)
        for section in (
            "Source Residency",
            "Difference Map Cache",
            "Workers",
            "Preload",
            "Stale Results",
            "Recent Failures",
        )
    )
    assert "Used bytes: 1536" in first
    assert "Over-budget bytes: 512" in first
    assert "Foreground loads: active 2 / max 2" in first
    assert "Preload: active 1 / max 1" in first
    assert "Foreground stale drops: 6" in first
    assert "1. [foreground-load/decode] ValueError: bad" in first


def test_zero_snapshot_formats_without_failures() -> None:
    snapshot = RuntimeDiagnosticsSnapshot(
        source=SourceResidencyDiagnostics(0, 0, 0, 0),
        difference=DifferenceCacheDiagnostics(0, 0, 0),
        workers=WorkerDiagnostics(
            foreground_loads=WorkerPoolDiagnostics(0, 2),
            preload=WorkerPoolDiagnostics(0, 1),
        ),
        preload=PreloadDiagnostics(False, 0, 0, 0, 0, 0, 0),
        normal_load_stale_drop_count=0,
    )

    text = format_runtime_diagnostics(snapshot)

    assert "Enabled: no" in text
    assert text.endswith("Recent Failures\nNone\n")


def test_recent_failure_history_keeps_only_latest_bounded_entries() -> None:
    failures = tuple(
        FailureDiagnostic("preload", "decode", "RuntimeError", f"failure {index}")
        for index in range(MAX_RECENT_FAILURES + 3)
    )

    snapshot = _snapshot(failures=failures)

    assert len(snapshot.recent_failures) == MAX_RECENT_FAILURES
    assert snapshot.recent_failures[0].message == "failure 3"
    assert snapshot.recent_failures[-1].message == f"failure {MAX_RECENT_FAILURES + 2}"


@pytest.mark.parametrize(
    "message",
    (
        r"decode failed at C:\Users\alice\images\frame.raw: expected 4096, actual 2048",
        "decode failed at /home/alice/images/frame.raw: expected 4096, actual 2048",
        r"decode failed at 'C:\Users\alice\My Images\frame.raw'",
        "decode failed at '/home/alice/My Images/frame.raw'",
    ),
)
def test_failure_sanitization_redacts_windows_and_posix_paths(message: str) -> None:
    sanitized = sanitize_failure_message(message)

    assert "alice" not in sanitized
    assert "frame.raw" not in sanitized
    assert "<redacted-path>" in sanitized
    if "expected" in message:
        assert "expected 4096, actual 2048" in sanitized


@pytest.mark.parametrize(
    ("message", "secret_value"),
    (
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
        (
            "decode failed; password=correct horse battery staple; retryable",
            "correct horse battery staple",
        ),
        ("api_key = first second third, decode failed", "first second third"),
    ),
)
def test_failure_sanitization_redacts_complete_unquoted_credential_values(
    message: str,
    secret_value: str,
) -> None:
    sanitized = sanitize_failure_message(message)

    assert secret_value not in sanitized
    assert "<redacted>" in sanitized


def test_failure_sanitization_removes_traceback_multiline_and_credentials() -> None:
    message = (
        "Traceback (most recent call last):\n"
        '  File "C:\\Users\\alice\\decoder.py", line 7\n'
        "RuntimeError: token=secret-value; Bearer abc.def.ghi decode failed"
    )

    diagnostic = FailureDiagnostic.from_exception(
        "foreground load",
        "decode",
        RuntimeError(message),
    )

    assert "Traceback" not in diagnostic.message
    assert "decoder.py" not in diagnostic.message
    assert "secret-value" not in diagnostic.message
    assert "abc.def.ghi" not in diagnostic.message
    assert "token=<redacted>" in diagnostic.message
    assert "Bearer <redacted>" in diagnostic.message
    assert "\n" not in diagnostic.message


def test_failure_sanitization_truncates_long_messages() -> None:
    sanitized = sanitize_failure_message("x" * (MAX_FAILURE_MESSAGE_CHARS + 20))

    assert len(sanitized) == MAX_FAILURE_MESSAGE_CHARS
    assert sanitized.endswith("...")
