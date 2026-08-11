from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pixelscope.core.comparison_set import (
    COMPARISON_SET_KIND,
    COMPARISON_SET_SCHEMA_VERSION,
    ComparisonSet,
    ComparisonSetError,
    ComparisonSetSource,
)
from pixelscope.io.raw_profile import RawProfile


class ComparisonSetRepository:
    """Read and atomically write versioned local Comparison Set artifacts."""

    def load(self, path: str | Path) -> ComparisonSet:
        target = Path(path)
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ComparisonSetError(f"cannot read comparison set: {exc}") from exc
        return self.from_payload(payload)

    def save(self, path: str | Path, comparison_set: ComparisonSet) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.to_payload(comparison_set), indent=2, ensure_ascii=False) + "\n"
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, target)
        except OSError:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def from_payload(self, payload: object) -> ComparisonSet:
        if not isinstance(payload, dict):
            raise ComparisonSetError("comparison-set root must be an object")
        if payload.get("kind") != COMPARISON_SET_KIND:
            raise ComparisonSetError("invalid comparison-set kind")
        version = payload.get("schema_version")
        if type(version) is not int or version != COMPARISON_SET_SCHEMA_VERSION:
            raise ComparisonSetError(f"unsupported comparison-set schema version: {version!r}")
        sources_value = payload.get("sources")
        if not isinstance(sources_value, list) or not sources_value:
            raise ComparisonSetError("comparison-set sources must be a non-empty array")

        sources: list[ComparisonSetSource] = []
        for entry in sources_value:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                raise ComparisonSetError("each comparison-set source requires a string path")
            raw_payload = entry.get("raw_profile")
            raw_profile: dict[str, Any] | None = None
            if raw_payload is not None:
                if not isinstance(raw_payload, dict):
                    raise ComparisonSetError("raw_profile must be an object or null")
                try:
                    raw_profile = RawProfile.parse_obj(raw_payload).dict()
                except Exception as exc:  # noqa: BLE001 - normalize pydantic validation errors
                    raise ComparisonSetError(f"invalid RAW profile: {exc}") from exc
            sources.append(ComparisonSetSource(entry["path"], raw_profile))

        active = payload.get("active_path")
        primary = payload.get("primary_path")
        layout = payload.get("layout_mode", "Auto")
        if active is not None and not isinstance(active, str):
            raise ComparisonSetError("active_path must be a string or null")
        if primary is not None and not isinstance(primary, str):
            raise ComparisonSetError("primary_path must be a string or null")
        if not isinstance(layout, str):
            raise ComparisonSetError("layout_mode must be a string")
        return ComparisonSet(
            sources=tuple(sources),
            active_path=active,
            primary_path=primary,
            layout_mode=layout,
        )

    def to_payload(self, comparison_set: ComparisonSet) -> dict[str, object]:
        return {
            "kind": comparison_set.kind,
            "schema_version": comparison_set.schema_version,
            "sources": [
                {"path": source.path, **({"raw_profile": source.raw_profile} if source.raw_profile is not None else {})}
                for source in comparison_set.sources
            ],
            "active_path": comparison_set.active_path,
            "primary_path": comparison_set.primary_path,
            "layout_mode": comparison_set.layout_mode,
        }
