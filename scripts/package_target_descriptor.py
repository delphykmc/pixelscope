"""Validated caller-owned packaging target for a downstream distribution.

Descriptor location is caller-selected, never fixed beneath an IQA handoff
root. Relative spec/requirements paths are resolved from the repository root
and are not allowed to escape it. Nothing reads private configuration unless
the caller explicitly passes --target-descriptor.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.release_contract import REPO_ROOT

_SLUG = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_BASENAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_EXE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}\.exe$", re.IGNORECASE)
_APP_ID = re.compile(r"^\{[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\}$")
_ALLOWED = frozenset(
    {
        "schema_version",
        "target_id",
        "spec",
        "app_dir",
        "executable",
        "display_name",
        "installer_app_id",
        "smoke_window_title",
        "runtime_requirements",
    }
)


@dataclass(frozen=True)
class PackageTargetDescriptor:
    target_id: str
    spec: Path
    app_dir: str
    executable: str
    display_name: str
    installer_app_id: str
    smoke_window_title: str
    runtime_requirements: Path | None = None

    @property
    def output_root(self) -> Path:
        return REPO_ROOT / "dist" / self.app_dir

    @property
    def executable_path(self) -> Path:
        return self.output_root / self.executable

    @property
    def stem_prefix(self) -> str:
        return self.app_dir


def _repo_file(value: Any, label: str, extension: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"target descriptor {label} must be a repo-relative file")
    pure = Path(value)
    if pure.is_absolute() or ".." in pure.parts or ":" in value or "\\" in value:
        raise ValueError(f"unsafe target descriptor {label} path")
    resolved = (REPO_ROOT / pure).resolve()
    if not resolved.is_relative_to(REPO_ROOT.resolve()):
        raise ValueError(f"target descriptor {label} escapes repository")
    if resolved.suffix.casefold() != extension or not resolved.is_file():
        raise ValueError(f"target descriptor {label} must refer to an existing {extension} file")
    return resolved


def _label(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > 80
        or any(ord(c) < 32 or c in '"{};\\' for c in value)
    ):
        raise ValueError(f"unsafe target descriptor {name}")
    return value


def load_target_descriptor(path: Path) -> PackageTargetDescriptor:
    """Load a caller-selected JSON descriptor; reject ambiguous/malformed input."""

    source = path.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"target descriptor not found: {source}")
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid UTF-8/JSON target descriptor") from exc
    if not isinstance(data, dict) or data.keys() - _ALLOWED:
        raise ValueError("invalid or unknown target descriptor fields")
    if data.get("schema_version") != 1:
        raise ValueError("unsupported target descriptor schema")
    target_id = data.get("target_id")
    app_dir = data.get("app_dir")
    exe = data.get("executable")
    if not isinstance(target_id, str) or not _SLUG.fullmatch(target_id):
        raise ValueError("invalid target descriptor target_id")
    if target_id in {"core", "reference"}:
        raise ValueError("custom target must not override public target_id")
    if not isinstance(app_dir, str) or not _BASENAME.fullmatch(app_dir):
        raise ValueError("invalid target descriptor app_dir")
    if app_dir.casefold() in {"pixelscope", "pixelscopereference"}:
        raise ValueError("custom target must not overwrite public dist")
    if not isinstance(exe, str) or not _EXE.fullmatch(exe):
        raise ValueError("invalid target descriptor executable")
    if exe[:-4].casefold() != app_dir.casefold():
        raise ValueError("target executable must match onedir app_dir")
    app_id = data.get("installer_app_id")
    if not isinstance(app_id, str) or not _APP_ID.fullmatch(app_id):
        raise ValueError("invalid target descriptor installer_app_id GUID")
    req = data.get("runtime_requirements")
    return PackageTargetDescriptor(
        target_id=target_id,
        spec=_repo_file(data.get("spec"), "spec", ".spec"),
        app_dir=app_dir,
        executable=exe,
        display_name=_label(data.get("display_name"), "display_name"),
        installer_app_id=app_id,
        smoke_window_title=_label(data.get("smoke_window_title"), "smoke_window_title"),
        runtime_requirements=(
            _repo_file(req, "runtime_requirements", ".txt") if req is not None else None
        ),
    )
