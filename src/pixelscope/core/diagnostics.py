from __future__ import annotations

import re
from dataclasses import dataclass

from pixelscope.core.preload import PreloadDiagnostics

MAX_RECENT_FAILURES = 10
MAX_FAILURE_MESSAGE_CHARS = 240

_TRACEBACK_PREFIX = "Traceback (most recent call last):"
_QUOTED_ABSOLUTE_PATH_RE = re.compile(r"""(["'])(?:(?:[A-Za-z]:[\\/])|(?:\\\\)|/)[^"'\r\n]*\1""")
_URL_RE = re.compile(r"\b(?:https?|file)://[^\s]+", re.IGNORECASE)
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[A-Za-z]:[\\/]|\\\\)[^\s,;]+")
_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:[^/\s]+/)*[^/\s,;:]+")
_BEARER_RE = re.compile(r"\bBearer\s+[^\s,;]+", re.IGNORECASE)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(token|password|passwd|secret|api[_-]?key|authorization)\b"
    r"\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^,;]*)",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"\s+")
_LABEL_RE = re.compile(r"[^A-Za-z0-9_. -]+")


def _require_non_negative_int(name: str, value: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _sanitize_label(value: object, *, fallback: str) -> str:
    try:
        text = str(value)
    except Exception:
        return fallback
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = _LABEL_RE.sub("-", text).strip(" .-")
    return text[:64] or fallback


def sanitize_failure_message(value: object) -> str:
    """Return a short single-line failure message without sensitive context."""

    try:
        raw = str(value)
    except Exception:
        raw = "Failure details unavailable"
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if any(line.startswith(_TRACEBACK_PREFIX) for line in lines):
        text = lines[-1] if lines else "Failure details unavailable"
    else:
        text = " ".join(lines)
    text = _URL_RE.sub("<redacted-url>", text)
    text = _QUOTED_ABSOLUTE_PATH_RE.sub("<redacted-path>", text)
    text = _WINDOWS_ABSOLUTE_PATH_RE.sub("<redacted-path>", text)
    text = _POSIX_ABSOLUTE_PATH_RE.sub("<redacted-path>", text)
    text = _BEARER_RE.sub("Bearer <redacted>", text)
    text = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return "No failure message"
    if len(text) > MAX_FAILURE_MESSAGE_CHARS:
        return text[: MAX_FAILURE_MESSAGE_CHARS - 3].rstrip() + "..."
    return text


@dataclass(frozen=True)
class SourceResidencyDiagnostics:
    used_bytes: int
    budget_bytes: int
    resident_count: int
    over_budget_bytes: int

    def __post_init__(self) -> None:
        for name in ("used_bytes", "budget_bytes", "resident_count", "over_budget_bytes"):
            _require_non_negative_int(name, getattr(self, name))


@dataclass(frozen=True)
class DifferenceCacheDiagnostics:
    used_bytes: int
    budget_bytes: int
    entry_count: int

    def __post_init__(self) -> None:
        for name in ("used_bytes", "budget_bytes", "entry_count"):
            _require_non_negative_int(name, getattr(self, name))


@dataclass(frozen=True)
class WorkerPoolDiagnostics:
    active_count: int
    max_count: int

    def __post_init__(self) -> None:
        _require_non_negative_int("active_count", self.active_count)
        _require_non_negative_int("max_count", self.max_count)


@dataclass(frozen=True)
class WorkerDiagnostics:
    foreground_loads: WorkerPoolDiagnostics
    preload: WorkerPoolDiagnostics

    def __post_init__(self) -> None:
        if not isinstance(self.foreground_loads, WorkerPoolDiagnostics):
            raise TypeError("foreground_loads must be WorkerPoolDiagnostics")
        if not isinstance(self.preload, WorkerPoolDiagnostics):
            raise TypeError("preload must be WorkerPoolDiagnostics")


@dataclass(frozen=True)
class FailureDiagnostic:
    subsystem: str
    category: str
    exception_type: str
    message: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "subsystem",
            _sanitize_label(self.subsystem, fallback="runtime"),
        )
        object.__setattr__(
            self,
            "category",
            _sanitize_label(self.category, fallback="failure"),
        )
        object.__setattr__(
            self,
            "exception_type",
            _sanitize_label(self.exception_type, fallback="Exception"),
        )
        object.__setattr__(self, "message", sanitize_failure_message(self.message))

    @classmethod
    def from_exception(
        cls,
        subsystem: str,
        category: str,
        error: BaseException,
    ) -> FailureDiagnostic:
        if not isinstance(error, BaseException):
            raise TypeError("error must be BaseException")
        return cls(
            subsystem=subsystem,
            category=category,
            exception_type=type(error).__name__,
            message=sanitize_failure_message(error),
        )


@dataclass(frozen=True)
class RuntimeDiagnosticsSnapshot:
    source: SourceResidencyDiagnostics
    difference: DifferenceCacheDiagnostics
    workers: WorkerDiagnostics
    preload: PreloadDiagnostics
    normal_load_stale_drop_count: int
    recent_failures: tuple[FailureDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceResidencyDiagnostics):
            raise TypeError("source must be SourceResidencyDiagnostics")
        if not isinstance(self.difference, DifferenceCacheDiagnostics):
            raise TypeError("difference must be DifferenceCacheDiagnostics")
        if not isinstance(self.workers, WorkerDiagnostics):
            raise TypeError("workers must be WorkerDiagnostics")
        if not isinstance(self.preload, PreloadDiagnostics):
            raise TypeError("preload must be PreloadDiagnostics")
        _require_non_negative_int(
            "normal_load_stale_drop_count",
            self.normal_load_stale_drop_count,
        )
        failures = tuple(self.recent_failures)
        if any(not isinstance(failure, FailureDiagnostic) for failure in failures):
            raise TypeError("recent_failures must contain FailureDiagnostic values")
        object.__setattr__(self, "recent_failures", failures[-MAX_RECENT_FAILURES:])


def format_runtime_diagnostics(snapshot: RuntimeDiagnosticsSnapshot) -> str:
    """Format one immutable snapshot without reading or changing runtime state."""

    if not isinstance(snapshot, RuntimeDiagnosticsSnapshot):
        raise TypeError("snapshot must be RuntimeDiagnosticsSnapshot")

    source = snapshot.source
    difference = snapshot.difference
    workers = snapshot.workers
    preload = snapshot.preload
    lines = [
        "PixelScope Runtime Diagnostics",
        "",
        "Source Residency",
        f"Used bytes: {source.used_bytes}",
        f"Budget bytes: {source.budget_bytes}",
        f"Resident sources: {source.resident_count}",
        f"Over-budget bytes: {source.over_budget_bytes}",
        "",
        "Difference Map Cache",
        f"Used bytes: {difference.used_bytes}",
        f"Budget bytes: {difference.budget_bytes}",
        f"Entries: {difference.entry_count}",
        "",
        "Workers",
        "Foreground loads: "
        f"active {workers.foreground_loads.active_count} / "
        f"max {workers.foreground_loads.max_count}",
        f"Preload: active {workers.preload.active_count} / max {workers.preload.max_count}",
        "",
        "Preload",
        f"Enabled: {'yes' if preload.enabled else 'no'}",
        f"Planned targets: {preload.planned_target_count}",
        f"Active workers: {preload.active_worker_count}",
        f"Promoted to foreground: {preload.promotion_count}",
        f"Retained successes: {preload.successful_retained_count}",
        f"Stale drops: {preload.stale_drop_count}",
        f"Cancellation requests: {preload.cancellation_request_count}",
        f"Failures: {preload.failure_count}",
        "",
        "Stale Results",
        f"Foreground stale drops: {snapshot.normal_load_stale_drop_count}",
        f"Preload stale drops: {preload.stale_drop_count}",
        "",
        "Recent Failures",
    ]
    if snapshot.recent_failures:
        lines.extend(
            f"{index}. [{failure.subsystem}/{failure.category}] "
            f"{failure.exception_type}: {failure.message}"
            for index, failure in enumerate(snapshot.recent_failures, start=1)
        )
    else:
        lines.append("None")
    return "\n".join(lines) + "\n"
