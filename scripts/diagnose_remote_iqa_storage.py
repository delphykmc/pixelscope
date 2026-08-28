from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path, PureWindowsPath

from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.remote.iqa_storage import StorageResolutionError, resolve_existing_source
from pixelscope.remote.iqa_submission import SUPPORTED_REMOTE_SUFFIXES


@dataclass(frozen=True)
class SourceObservation:
    source_index: int
    lexical_contains: bool
    resolved_contains: bool
    resolver_match: bool
    staged: bool | None
    relative_path_present: bool
    error: str | None


@dataclass(frozen=True)
class StorageDiagnosticReport:
    root_exists: bool
    root_is_directory: bool
    eligible_source_count: int
    checked_source_count: int
    observations: tuple[SourceObservation, ...]

    @property
    def passed(self) -> bool:
        return (
            self.root_exists
            and self.root_is_directory
            and self.checked_source_count > 0
            and all(item.resolver_match for item in self.observations)
        )


def _windows_lexically_contains(root: Path, source: Path) -> bool:
    root_parts = tuple(part.casefold() for part in PureWindowsPath(str(root)).parts)
    source_parts = tuple(part.casefold() for part in PureWindowsPath(str(source)).parts)
    return len(source_parts) > len(root_parts) and source_parts[: len(root_parts)] == root_parts


def _resolved_contains(root: Path, source: Path) -> bool:
    try:
        root_resolved = root.resolve(strict=True)
        source_resolved = source.resolve(strict=True)
        common = os.path.commonpath((os.fspath(root_resolved), os.fspath(source_resolved)))
    except (OSError, RuntimeError, ValueError):
        return False
    return os.path.normcase(common) == os.path.normcase(os.fspath(root_resolved))


def run_storage_diagnostics(root: Path, *, max_sources: int = 16) -> StorageDiagnosticReport:
    root_exists = root.exists()
    root_is_directory = root.is_dir()
    if not root_is_directory:
        return StorageDiagnosticReport(root_exists, False, 0, 0, ())

    try:
        sources = tuple(
            item
            for item in root.iterdir()
            if item.is_file()
            and not item.is_symlink()
            and item.suffix.casefold() in SUPPORTED_REMOTE_SUFFIXES
        )
    except OSError:
        return StorageDiagnosticReport(True, True, 0, 0, ())

    settings = RemoteIqaSettings(
        server_base_url="http://diagnostic.invalid",
        storage_roots=(RemoteIqaStorageRoot("diagnostic-root", str(root)),),
    )
    observations: list[SourceObservation] = []
    for index, source in enumerate(sources[:max_sources], start=1):
        try:
            resolved = resolve_existing_source(source, settings)
        except StorageResolutionError as exc:
            observations.append(
                SourceObservation(
                    index,
                    _windows_lexically_contains(root, source),
                    _resolved_contains(root, source),
                    False,
                    None,
                    False,
                    exc.__class__.__name__,
                )
            )
            continue
        observations.append(
            SourceObservation(
                index,
                _windows_lexically_contains(root, source),
                _resolved_contains(root, source),
                resolved is not None,
                None if resolved is None else resolved.staged,
                bool(resolved is not None and resolved.logical_path.relative_path),
                None,
            )
        )

    return StorageDiagnosticReport(
        root_exists=True,
        root_is_directory=True,
        eligible_source_count=len(sources),
        checked_source_count=len(observations),
        observations=tuple(observations),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose Remote IQA shared-root matching without printing root paths or file names."
        )
    )
    parser.add_argument("root", type=Path)
    parser.add_argument("--max-sources", type=int, default=16)
    args = parser.parse_args()
    if args.max_sources < 1:
        parser.error("--max-sources must be positive")

    report = run_storage_diagnostics(args.root, max_sources=args.max_sources)
    payload = asdict(report)
    payload["passed"] = report.passed
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
