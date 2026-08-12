from __future__ import annotations

import json
import os
import tempfile
from math import isfinite
from pathlib import Path
from typing import Any

from pixelscope.core.comparison_set import (
    LEGACY_COMPARISON_SET_KIND,
    SESSION_DIFFERENCE_CHANNELS,
    SESSION_DIFFERENCE_MAX_GAIN,
    SESSION_DIFFERENCE_MAX_THRESHOLD,
    SESSION_DIFFERENCE_MODES,
    SESSION_DIFFERENCE_REGIONS,
    SESSION_KIND,
    SESSION_SCHEMA_VERSION,
    ComparisonSetError,
    Session,
    SessionDifference,
    SessionSource,
)
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.io.raw_profile import RawProfile


class ComparisonSetRepository:
    """Read and atomically write versioned local PixelScope Session artifacts."""

    def load(self, path: str | Path) -> Session:
        target = Path(path)
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ComparisonSetError(f"cannot read session: {exc}") from exc
        return self.from_payload(payload)

    def save(self, path: str | Path, session: Session) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self.to_payload(session), indent=2, ensure_ascii=False) + "\n"
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
            assert temp_path is not None
            os.replace(temp_path, target)
        except OSError:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

    def from_payload(self, payload: object) -> Session:
        if not isinstance(payload, dict):
            raise ComparisonSetError("session root must be an object")
        kind = payload.get("kind")
        version = payload.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool) or version != 1:
            raise ComparisonSetError(f"unsupported session schema version: {version!r}")
        if kind == LEGACY_COMPARISON_SET_KIND:
            return self._from_legacy_comparison_set(payload)
        if kind != SESSION_KIND:
            raise ComparisonSetError("invalid session kind")
        if version != SESSION_SCHEMA_VERSION:
            raise ComparisonSetError(f"unsupported session schema version: {version!r}")

        registered = self._parse_sources(
            payload.get("registered_sources"),
            "registered_sources",
        )
        selected_value = payload.get("selected_paths", [])
        if not isinstance(selected_value, list):
            raise ComparisonSetError("selected_paths must be an array")
        selected = tuple(
            self._artifact_absolute_path(value, "selected path") for value in selected_value
        )
        active = self._optional_artifact_absolute_path(
            payload.get("active_path"),
            "active_path",
        )
        primary = self._optional_artifact_absolute_path(
            payload.get("primary_path"),
            "primary_path",
        )
        layout = payload.get("layout_mode", "Auto")
        if not isinstance(layout, str):
            raise ComparisonSetError("layout_mode must be a string")
        display_gain = self._number(payload.get("display_gain", 1.0), "display_gain")
        split_channels = payload.get("split_channels", False)
        if not isinstance(split_channels, bool):
            raise ComparisonSetError("split_channels must be boolean")

        roi = self._parse_roi(payload.get("roi"))
        line = self._parse_line(payload.get("line"))
        difference = self._parse_difference(payload.get("difference"))
        return Session(
            registered_sources=registered,
            selected_paths=selected,
            active_path=active,
            primary_path=primary,
            layout_mode=layout,
            roi=roi,
            line=line,
            display_gain=display_gain,
            split_channels=split_channels,
            difference=difference,
        )

    def _from_legacy_comparison_set(self, payload: dict[str, object]) -> Session:
        """Read P4-B draft artifacts as Sessions without preserving the old UI concept."""

        sources = self._parse_sources(payload.get("sources"), "sources")
        active = self._optional_artifact_absolute_path(
            payload.get("active_path"),
            "active_path",
        )
        primary = self._optional_artifact_absolute_path(
            payload.get("primary_path"),
            "primary_path",
        )
        layout = payload.get("layout_mode", "Auto")
        if not isinstance(layout, str):
            raise ComparisonSetError("layout_mode must be a string")
        return Session(
            registered_sources=sources,
            selected_paths=tuple(source.path for source in sources),
            active_path=active,
            primary_path=primary,
            layout_mode=layout,
        )

    def _parse_sources(self, value: object, field: str) -> tuple[SessionSource, ...]:
        if not isinstance(value, list) or not value:
            raise ComparisonSetError(f"{field} must be a non-empty array")
        result: list[SessionSource] = []
        for entry in value:
            if not isinstance(entry, dict):
                raise ComparisonSetError(f"each {field} entry must be an object")
            source_path = self._artifact_absolute_path(
                entry.get("path"),
                "source path",
            )
            raw_payload = entry.get("raw_profile")
            raw_profile: dict[str, Any] | None = None
            if raw_payload is not None:
                if not isinstance(raw_payload, dict):
                    raise ComparisonSetError("raw_profile must be an object or null")
                try:
                    raw_profile = RawProfile.parse_obj(raw_payload).dict()
                except Exception as exc:  # noqa: BLE001 - normalized validation boundary
                    raise ComparisonSetError(f"invalid RAW profile: {exc}") from exc
            result.append(SessionSource(source_path, raw_profile))
        return tuple(result)

    @classmethod
    def _parse_roi(cls, value: object) -> RoiBounds | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ComparisonSetError("roi must be an object or null")
        try:
            return RoiBounds(
                cls._integer(value["x"], "roi.x"),
                cls._integer(value["y"], "roi.y"),
                cls._integer(value["width"], "roi.width"),
                cls._integer(value["height"], "roi.height"),
            )
        except KeyError as exc:
            raise ComparisonSetError(f"invalid ROI: missing {exc.args[0]}") from exc
        except ValueError as exc:
            raise ComparisonSetError(f"invalid ROI: {exc}") from exc

    @classmethod
    def _parse_line(cls, value: object) -> LineSelection | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ComparisonSetError("line must be an object or null")
        try:
            return LineSelection(
                cls._integer(value["x1"], "line.x1"),
                cls._integer(value["y1"], "line.y1"),
                cls._integer(value["x2"], "line.x2"),
                cls._integer(value["y2"], "line.y2"),
            )
        except KeyError as exc:
            raise ComparisonSetError(f"invalid line: missing {exc.args[0]}") from exc
        except ValueError as exc:
            raise ComparisonSetError(f"invalid line: {exc}") from exc

    def _parse_difference(self, value: object) -> SessionDifference | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ComparisonSetError("difference must be an object or null")

        channel = self._choice(
            value.get("channel", "All"),
            "difference.channel",
            SESSION_DIFFERENCE_CHANNELS,
        )
        mode = self._choice(
            value.get("mode", "Absolute"),
            "difference.mode",
            SESSION_DIFFERENCE_MODES,
        )
        region = self._choice(
            value.get("region", "Full image"),
            "difference.region",
            SESSION_DIFFERENCE_REGIONS,
        )
        threshold = self._number(value.get("threshold", 10.0), "difference.threshold")
        if not 0.0 <= threshold <= SESSION_DIFFERENCE_MAX_THRESHOLD:
            raise ComparisonSetError("difference.threshold is outside the supported range")
        gain = self._integer(value.get("gain", 1), "difference.gain")
        if not 1 <= gain <= SESSION_DIFFERENCE_MAX_GAIN:
            raise ComparisonSetError("difference.gain is outside the supported range")

        return SessionDifference(
            image_a_path=self._artifact_absolute_path(
                value.get("image_a_path"),
                "difference image_a_path",
            ),
            image_b_path=self._artifact_absolute_path(
                value.get("image_b_path"),
                "difference image_b_path",
            ),
            channel=channel,
            mode=mode,
            threshold=threshold,
            gain=gain,
            region=region,
        )

    @staticmethod
    def _integer(value: object, field: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ComparisonSetError(f"{field} must be an integer")
        return value

    @staticmethod
    def _number(value: object, field: str) -> float:
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise ComparisonSetError(f"{field} must be numeric")
        result = float(value)
        if not isfinite(result):
            raise ComparisonSetError(f"{field} must be finite")
        return result

    @staticmethod
    def _choice(value: object, field: str, allowed: frozenset[str]) -> str:
        if not isinstance(value, str) or value not in allowed:
            raise ComparisonSetError(f"unsupported {field}: {value!r}")
        return value

    @staticmethod
    def _artifact_absolute_path(value: object, field: str) -> str:
        if not isinstance(value, str):
            raise ComparisonSetError(f"{field} must be a string")
        if not value.strip():
            raise ComparisonSetError(f"{field} must not be empty")
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            raise ComparisonSetError(f"{field} must be an absolute path")
        return str(candidate.resolve(strict=False))

    @classmethod
    def _optional_artifact_absolute_path(
        cls,
        value: object,
        field: str,
    ) -> str | None:
        if value is None:
            return None
        return cls._artifact_absolute_path(value, field)

    def to_payload(self, session: Session) -> dict[str, object]:
        payload: dict[str, object] = {
            "kind": session.kind,
            "schema_version": session.schema_version,
            "registered_sources": [
                self._source_payload(source) for source in session.registered_sources
            ],
            "selected_paths": list(session.selected_paths),
            "active_path": session.active_path,
            "primary_path": session.primary_path,
            "layout_mode": session.layout_mode,
            "display_gain": session.display_gain,
            "split_channels": session.split_channels,
            "roi": self._roi_payload(session.roi),
            "line": self._line_payload(session.line),
            "difference": self._difference_payload(session.difference),
        }
        return payload

    @staticmethod
    def _source_payload(source: SessionSource) -> dict[str, object]:
        payload: dict[str, object] = {"path": source.path}
        if source.raw_profile is not None:
            payload["raw_profile"] = source.raw_profile
        return payload

    @staticmethod
    def _roi_payload(roi: RoiBounds | None) -> dict[str, int] | None:
        if roi is None:
            return None
        return {
            "x": roi.x,
            "y": roi.y,
            "width": roi.width,
            "height": roi.height,
        }

    @staticmethod
    def _line_payload(line: LineSelection | None) -> dict[str, int] | None:
        if line is None:
            return None
        assert line.y2 is not None
        return {
            "x1": line.x1,
            "y1": line.y1,
            "x2": line.x2,
            "y2": line.y2,
        }

    @staticmethod
    def _difference_payload(
        difference: SessionDifference | None,
    ) -> dict[str, object] | None:
        if difference is None:
            return None
        return {
            "image_a_path": difference.image_a_path,
            "image_b_path": difference.image_b_path,
            "channel": difference.channel,
            "mode": difference.mode,
            "threshold": difference.threshold,
            "gain": difference.gain,
            "region": difference.region,
        }
