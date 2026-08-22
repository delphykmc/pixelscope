"""Canonical version-dispatch entry point for published Remote IQA results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_reader import load_result as load_result_v1
from pixelscope.remote.iqa_v2_domain import VersionedResultLoadOutcome
from pixelscope.remote.iqa_v2_partial import load_partial_result_v2
from pixelscope.remote.iqa_v2_reader import V2_MANIFEST_LIMIT, load_result_v2


def load_result(root: Path | str) -> VersionedResultLoadOutcome:
    """Dispatch schema v2 natively and schema v1 through read-only compatibility."""
    result_root = Path(root)
    try:
        manifest = _read_dispatch_manifest(result_root)
    except OSError as exc:
        return VersionedResultLoadOutcome(LoadStatus.CORRUPT, reason=str(exc))
    if not isinstance(manifest, dict):
        return VersionedResultLoadOutcome(
            LoadStatus.INVALID, reason="manifest must be a JSON object"
        )
    if manifest.get("kind") != "pixelscope-iqa-result":
        return VersionedResultLoadOutcome(
            LoadStatus.INVALID,
            reason="manifest kind must be pixelscope-iqa-result",
        )
    version = manifest.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        return VersionedResultLoadOutcome(
            LoadStatus.INVALID, reason="schema_version must be an integer"
        )
    if version == 2:
        if manifest.get("publication_state") == "partial":
            return load_partial_result_v2(result_root)
        return load_result_v2(result_root)
    if version == 1:
        legacy = load_result_v1(result_root)
        return VersionedResultLoadOutcome(
            legacy.status,
            result=legacy.result,
            reason=legacy.reason,
        )
    return VersionedResultLoadOutcome(
        LoadStatus.UNSUPPORTED,
        reason=f"unsupported IQA schema_version {version}",
    )


def _read_dispatch_manifest(root: Path) -> Any:
    path = root / "manifest.json"
    if not path.is_file():
        raise OSError("missing manifest.json publication marker")
    if path.stat().st_size > V2_MANIFEST_LIMIT:
        raise OSError("manifest exceeds dispatcher safety ceiling")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OSError(f"manifest is unreadable: {exc}") from exc
