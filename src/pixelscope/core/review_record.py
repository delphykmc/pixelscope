# ruff: noqa: E721  # Strict JSON primitive checks must reject bool-as-int.
"""Strict Qt-free local Review v1 DTOs and portable projection (Issue #210 W09a).

A Review is captured evidence, never an instruction to mutate live workspace.
The W02 context serializer and W04 view-state DTO remain the sole authorities for
their existing wire formats. No runtime QObject, numpy array or worker is stored.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, cast
from uuid import UUID, uuid4

from pixelscope.core.review_analysis import (
    AnalysisSnapshotV1,
    parse_analysis_context,
    serialize_analysis_context,
)
from pixelscope.core.review_analysis_native import AnalysisNativeInterpretationV1
from pixelscope.core.review_view_state import ReviewViewStateV1
from pixelscope.version import __version__

REVIEW_KIND = "pixelscope-review"
REVIEW_SCHEMA_VERSION = 1
PORTABLE_KIND = "pixelscope-portable-review"
MAX_REVIEW_BYTES = 16 * 1024 * 1024
MAX_REVIEW_DEPTH = 48
MAX_SOURCES = 10_000
MAX_FINDINGS = 1_000
MAX_ANALYSIS_PER_FINDING = 16
MAX_NOTE_BYTES = 32 * 1024
MAX_EXTENSIONS_BYTES = 64 * 1024
_HEX = re.compile(r"^[0-9a-f]{64}$")
_LABEL = re.compile(r"^[\w .:+-]{1,96}$", re.UNICODE)
_DTYPE = re.compile(
    r"^(?:bool|u?int(?:8|16|32|64)|float(?:16|32|64)|" r"[<>=|](?:[iu](?:1|2|4|8)|f(?:2|4|8)|b1))$"
)
_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+_-]{0,63}$")
_STATUSES = frozenset({"available", "partial", "unavailable"})
_ANALYSIS_STATUSES = frozenset({"captured", "unavailable"})


class ReviewValidationError(ValueError):
    """Untrusted Review JSON or invalid value object; no workspace mutation."""


def _fields(raw: object, required: set[str], name: str) -> dict[str, Any]:
    if type(raw) is not dict or set(raw) != required:
        raise ReviewValidationError(f"invalid {name} fields")
    return raw


def _uuid(value: object) -> str:
    if type(value) is not str:
        raise ReviewValidationError("UUID must be a canonical lowercase string")
    try:
        if str(UUID(value)) != value:
            raise ValueError(value)
    except (ValueError, AttributeError) as exc:
        raise ReviewValidationError("invalid canonical UUID") from exc
    return value


def _time(value: object) -> str:
    if type(value) is not str or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", value
    ):
        raise ReviewValidationError("expected UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReviewValidationError("invalid UTC timestamp") from exc
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _text(value: object, name: str, limit: int, *, nonblank: bool = False) -> str:
    if type(value) is not str or len(value.encode("utf-8")) > limit:
        raise ReviewValidationError(f"invalid {name} or text budget exceeded")
    if nonblank and not value.strip():
        raise ReviewValidationError(f"{name} must not be blank")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ReviewValidationError(f"{name} contains control characters")
    return value


def _digest(value: object, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if type(value) is not str or not _HEX.fullmatch(value):
        raise ReviewValidationError("invalid SHA-256 hex digest")
    return value


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > 2**63 - 1:
        raise ReviewValidationError(f"invalid {name} integer")
    return value


def _number(value: object, name: str, *, minimum: float = 0.0) -> float:
    if type(value) not in (int, float):
        raise ReviewValidationError(f"invalid {name} number")
    result = float(cast(int | float, value))
    if not math.isfinite(result) or result < minimum:
        raise ReviewValidationError(f"invalid {name} finite number")
    return result


def _keys(raw: object, *, maximum: int, allow_empty: bool = False) -> tuple[str, ...]:
    if type(raw) not in (list, tuple):
        raise ReviewValidationError("invalid ordered source key collection")
    sequence = cast(list[object] | tuple[object, ...], raw)
    if len(sequence) > maximum or (not allow_empty and not sequence):
        raise ReviewValidationError("invalid ordered source key collection")
    keys = tuple(_uuid(item) for item in sequence)
    if len(set(keys)) != len(keys):
        raise ReviewValidationError("duplicate source keys")
    return keys


def _rect(raw: object, *, line: bool = False) -> tuple[int, int, int, int] | None:
    if raw is None:
        return None
    labels = ("x1", "y1", "x2", "y2") if line else ("x", "y", "width", "height")
    obj = _fields(raw, set(labels), "line" if line else "ROI")
    values = tuple(
        _integer(obj[key], key, minimum=0 if line or key in ("x", "y") else 1) for key in labels
    )
    return cast(tuple[int, int, int, int], values)


def _rect_wire(
    value: tuple[int, int, int, int] | None, *, line: bool = False
) -> dict[str, int] | None:
    if value is None:
        return None
    labels = ("x1", "y1", "x2", "y2") if line else ("x", "y", "width", "height")
    return dict(zip(labels, value, strict=True))


def _json_depth(value: object, depth: int = 0) -> None:
    if depth > MAX_REVIEW_DEPTH:
        raise ReviewValidationError("JSON nesting depth exceeded")
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ReviewValidationError("JSON object keys must be strings")
        for item in value.values():
            _json_depth(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _json_depth(item, depth + 1)
    elif type(value) is float:
        if not math.isfinite(value):
            raise ReviewValidationError("nonfinite number must use an explicit state")
    elif type(value) is int:
        if value.bit_length() > 64:
            raise ReviewValidationError("JSON integer exceeds limit")
    elif value is not None and type(value) not in (str, bool):
        raise ReviewValidationError("non-JSON value in Review")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ReviewValidationError("duplicate JSON object key")
        obj[key] = value
    return obj


def _reject_constant(value: str) -> object:
    raise ReviewValidationError(f"nonfinite JSON token: {value}")


def canonical_json(value: object, *, limit: int = MAX_REVIEW_BYTES) -> bytes:
    _json_depth(value)
    try:
        raw = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ReviewValidationError("cannot serialize Review JSON") from exc
    if len(raw) > limit:
        raise ReviewValidationError("Review JSON byte budget exceeded")
    return raw


def parse_bounded_json(raw: bytes) -> object:
    if type(raw) is not bytes or len(raw) > MAX_REVIEW_BYTES:
        raise ReviewValidationError("Review must be bounded UTF-8 JSON bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_reject_constant
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ReviewValidationError(f"invalid Review JSON: {exc}") from exc
    _json_depth(value)
    return value


@dataclass(frozen=True)
class ReviewLocatorV1:
    basename: str
    relative_hint: str | None = None
    local_path: str | None = None

    def __post_init__(self) -> None:
        name = _text(self.basename, "basename", 512, nonblank=True)
        if name in (".", "..") or "/" in name or "\\" in name or ":" in name:
            raise ReviewValidationError("basename must not contain path components")
        if self.relative_hint is not None:
            hint = _text(self.relative_hint, "relative_hint", 1024, nonblank=True)
            if (
                "\\" in hint
                or PurePosixPath(hint).is_absolute()
                or (any(p in (".", "..", "") for p in hint.split("/")))
                or PureWindowsPath(hint).drive
            ):
                raise ReviewValidationError("unsafe relative locator hint")
        if self.local_path is not None:
            path = _text(self.local_path, "local_path", 4096, nonblank=True)
            if not (Path(path).is_absolute() or PureWindowsPath(path).is_absolute()):
                raise ReviewValidationError("local_path must be absolute")

    def to_dict(self) -> dict[str, Any]:
        return {
            "basename": self.basename,
            "relative_hint": self.relative_hint,
            "local_path": self.local_path,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ReviewLocatorV1:
        d = _fields(raw, {"basename", "relative_hint", "local_path"}, "locator")
        return cls(**d)


@dataclass(frozen=True)
class ReviewFingerprintV1:
    algorithm: str
    digest: str | None
    size_bytes: int
    mtime_ns: int | None
    state: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ReviewValidationError("unsupported fingerprint algorithm")
        _digest(self.digest, optional=True)
        _integer(self.size_bytes, "size_bytes")
        if self.mtime_ns is not None:
            _integer(self.mtime_ns, "mtime_ns")
        if self.state not in ("verified", "unverified"):
            raise ReviewValidationError("invalid fingerprint state")
        if self.state == "verified" and self.digest is None:
            raise ReviewValidationError("verified fingerprint requires SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "digest": self.digest,
            "size_bytes": self.size_bytes,
            "mtime_ns": self.mtime_ns,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ReviewFingerprintV1:
        return cls(
            **_fields(
                raw, {"algorithm", "digest", "size_bytes", "mtime_ns", "state"}, "fingerprint"
            )
        )


@dataclass(frozen=True)
class ReviewNativeSignatureV1:
    profile_signature: str
    native_shape: tuple[int, ...]
    reference_shape: tuple[int, int]
    native_dtype: str
    channel_layout: str
    effective_bits: int
    native_interpretation_json: bytes

    def __post_init__(self) -> None:
        _digest(self.profile_signature)
        if len(self.native_shape) not in (2, 3) or any(
            type(v) is not int or v <= 0 for v in self.native_shape
        ):
            raise ReviewValidationError("invalid native shape")
        if len(self.reference_shape) != 2 or any(
            type(v) is not int or v <= 0 for v in self.reference_shape
        ):
            raise ReviewValidationError("invalid reference shape")
        _integer(self.effective_bits, "effective_bits", minimum=1)
        if self.effective_bits > 64:
            raise ReviewValidationError("effective_bits exceeds 64")
        if type(self.native_dtype) is not str or not _DTYPE.fullmatch(self.native_dtype):
            raise ReviewValidationError("invalid native_dtype")
        if type(self.channel_layout) is not str or not _LABEL.fullmatch(self.channel_layout):
            raise ReviewValidationError("invalid channel_layout")
        native = AnalysisNativeInterpretationV1.from_portable(
            parse_bounded_json(self.native_interpretation_json)
        )
        if self.channel_layout.startswith("YUV") and native.yuv_layout != self.channel_layout:
            raise ReviewValidationError("native YUV layout mismatch")
        if self.channel_layout == "BAYER" and native.cfa_pattern is None:
            raise ReviewValidationError("Bayer CFA interpretation missing")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_signature": self.profile_signature,
            "native_shape": list(self.native_shape),
            "reference_shape": list(self.reference_shape),
            "native_dtype": self.native_dtype,
            "channel_layout": self.channel_layout,
            "effective_bits": self.effective_bits,
            "native_interpretation": parse_bounded_json(self.native_interpretation_json),
        }

    @classmethod
    def from_dict(cls, raw: object) -> ReviewNativeSignatureV1:
        d = _fields(
            raw,
            {
                "profile_signature",
                "native_shape",
                "reference_shape",
                "native_dtype",
                "channel_layout",
                "effective_bits",
                "native_interpretation",
            },
            "native signature",
        )
        if type(d["native_shape"]) is not list or type(d["reference_shape"]) is not list:
            raise ReviewValidationError("native shapes must be JSON arrays")
        return cls(
            d["profile_signature"],
            tuple(d["native_shape"]),
            tuple(d["reference_shape"]),
            d["native_dtype"],
            d["channel_layout"],
            d["effective_bits"],
            canonical_json(d["native_interpretation"], limit=16_384),
        )


@dataclass(frozen=True)
class ReviewSourceV1:
    source_key: str
    locator: ReviewLocatorV1
    native_signature: ReviewNativeSignatureV1
    fingerprint: ReviewFingerprintV1
    display_tag: str | None = None

    def __post_init__(self) -> None:
        _uuid(self.source_key)
        if (
            not isinstance(self.locator, ReviewLocatorV1)
            or not isinstance(self.native_signature, ReviewNativeSignatureV1)
            or not isinstance(self.fingerprint, ReviewFingerprintV1)
        ):
            raise ReviewValidationError("invalid Review source DTO")
        if self.display_tag is not None:
            _text(self.display_tag, "display_tag", 512, nonblank=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_key": self.source_key,
            "locator": self.locator.to_dict(),
            "native_signature": self.native_signature.to_dict(),
            "fingerprint": self.fingerprint.to_dict(),
            "display_tag": self.display_tag,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ReviewSourceV1:
        d = _fields(
            raw,
            {"source_key", "locator", "native_signature", "fingerprint", "display_tag"},
            "source",
        )
        return cls(
            d["source_key"],
            ReviewLocatorV1.from_dict(d["locator"]),
            ReviewNativeSignatureV1.from_dict(d["native_signature"]),
            ReviewFingerprintV1.from_dict(d["fingerprint"]),
            d["display_tag"],
        )


@dataclass(frozen=True)
class ReviewWorkspaceIntentV1:
    source_order: tuple[str, ...] = ()
    selected_keys: tuple[str, ...] = ()
    page_anchor_key: str | None = None
    active_key: str | None = None
    primary_key: str | None = None
    layout_mode: str = "Auto"
    display_gain: float = 1.0
    split_channels: bool = False

    def __post_init__(self) -> None:
        # Frozen DTOs must not retain mutable lists from programmatic callers.
        object.__setattr__(
            self, "source_order", _keys(self.source_order, maximum=MAX_SOURCES, allow_empty=True)
        )
        object.__setattr__(
            self, "selected_keys", _keys(self.selected_keys, maximum=MAX_SOURCES, allow_empty=True)
        )
        if not set(self.selected_keys) <= set(self.source_order):
            raise ReviewValidationError("selection outside source order")
        for value in (self.page_anchor_key, self.active_key, self.primary_key):
            if value is not None and _uuid(value) not in self.selected_keys:
                raise ReviewValidationError("workspace role outside selection")
        if self.layout_mode not in ("Auto", "Single View", "Multi View"):
            raise ReviewValidationError("invalid workspace layout")
        _number(self.display_gain, "display_gain", minimum=0.000001)
        if type(self.split_channels) is not bool:
            raise ReviewValidationError("split_channels must be bool")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_order": list(self.source_order),
            "selected_keys": list(self.selected_keys),
            "page_anchor_key": self.page_anchor_key,
            "active_key": self.active_key,
            "primary_key": self.primary_key,
            "layout_mode": self.layout_mode,
            "display_gain": self.display_gain,
            "split_channels": self.split_channels,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ReviewWorkspaceIntentV1:
        d = _fields(
            raw,
            {
                "source_order",
                "selected_keys",
                "page_anchor_key",
                "active_key",
                "primary_key",
                "layout_mode",
                "display_gain",
                "split_channels",
            },
            "workspace intent",
        )
        return cls(
            _keys(d["source_order"], maximum=MAX_SOURCES, allow_empty=True),
            _keys(d["selected_keys"], maximum=MAX_SOURCES, allow_empty=True),
            d["page_anchor_key"],
            d["active_key"],
            d["primary_key"],
            d["layout_mode"],
            d["display_gain"],
            d["split_channels"],
        )


@dataclass(frozen=True)
class ReviewDifferenceIntentV1:
    reference_key: str
    target_key: str
    channel: str
    mode: str
    threshold: float
    gain: int
    region: str

    def __post_init__(self) -> None:
        if _uuid(self.reference_key) == _uuid(self.target_key):
            raise ReviewValidationError("difference pair requires distinct sources")
        if (
            self.mode not in ("Absolute", "Mask")
            or (
                self.channel
                not in ("All", "R", "G", "B", "Gray", "Mosaic", "Gr", "Gb", "Y", "U", "V")
            )
            or self.region not in ("Full image", "Active ROI")
        ):
            raise ReviewValidationError("unsupported difference recipe")
        if _number(self.threshold, "threshold") > 65535.0:
            raise ReviewValidationError("difference threshold exceeds limit")
        if _integer(self.gain, "difference gain", minimum=1) > 1000:
            raise ReviewValidationError("difference gain exceeds limit")

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_key": self.reference_key,
            "target_key": self.target_key,
            "channel": self.channel,
            "mode": self.mode,
            "threshold": self.threshold,
            "gain": self.gain,
            "region": self.region,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ReviewDifferenceIntentV1:
        d = _fields(
            raw,
            {"reference_key", "target_key", "channel", "mode", "threshold", "gain", "region"},
            "difference intent",
        )
        return cls(**d)


@dataclass(frozen=True)
class ReviewAnalysisCaptureV1:
    """A copy of W02's *portable* immutable context, or explicit unavailability."""

    status: str
    context_json: bytes | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _ANALYSIS_STATUSES:
            raise ReviewValidationError("unknown analysis capture status")
        if self.status == "captured":
            if type(self.context_json) is not bytes or self.reason is not None:
                raise ReviewValidationError("captured analysis requires context only")
            parse_analysis_context(self.context_json)
        else:
            if self.context_json is not None:
                raise ReviewValidationError("unavailable analysis cannot contain context")
            _text(self.reason, "unavailable reason", 1024, nonblank=True)

    @classmethod
    def from_snapshot(cls, snapshot: AnalysisSnapshotV1) -> ReviewAnalysisCaptureV1:
        if not isinstance(snapshot, AnalysisSnapshotV1):
            raise ReviewValidationError("W02 AnalysisSnapshotV1 required")
        return cls("captured", serialize_analysis_context(snapshot))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "context": (
                parse_bounded_json(self.context_json) if self.context_json is not None else None
            ),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ReviewAnalysisCaptureV1:
        d = _fields(raw, {"status", "context", "reason"}, "analysis")
        return cls(
            d["status"],
            canonical_json(d["context"]) if d["context"] is not None else None,
            d["reason"],
        )


@dataclass(frozen=True)
class ReviewFindingV1:
    id: str
    title: str
    note: str
    tags: tuple[str, ...]
    captured_utc: str
    source_keys: tuple[str, ...]
    reference_key: str
    pair_target_key: str | None
    view_state: ReviewViewStateV1
    roi_ref: tuple[int, int, int, int] | None
    line_ref: tuple[int, int, int, int] | None
    channel: str
    display_gain: float
    difference_intent: ReviewDifferenceIntentV1 | None
    analysis: tuple[ReviewAnalysisCaptureV1, ...] = ()
    availability: str = "unavailable"

    def __post_init__(self) -> None:
        _uuid(self.id)
        _text(self.title, "title", 256, nonblank=True)
        _text(self.note, "note", MAX_NOTE_BYTES)
        if type(self.tags) not in (tuple, list):
            raise ReviewValidationError("finding tags must be a sequence")
        object.__setattr__(self, "tags", tuple(self.tags))
        if (
            len(self.tags) > 32
            or any(type(tag) is not str for tag in self.tags)
            or len(set(self.tags)) != len(self.tags)
        ):
            raise ReviewValidationError("invalid/duplicate finding tags")
        for tag in self.tags:
            _text(tag, "tag", 256, nonblank=True)
        _time(self.captured_utc)
        object.__setattr__(self, "source_keys", _keys(self.source_keys, maximum=6))
        if _uuid(self.reference_key) not in self.source_keys:
            raise ReviewValidationError("reference is not part of finding")
        if self.pair_target_key is not None and (
            _uuid(self.pair_target_key) not in self.source_keys
            or self.pair_target_key == self.reference_key
        ):
            raise ReviewValidationError("invalid pair target")
        if not isinstance(self.view_state, ReviewViewStateV1):
            raise ReviewValidationError("invalid W04 view state")
        if tuple(self.view_state.page_source_keys) != self.source_keys or (
            self.view_state.reference_source_key != self.reference_key
        ):
            raise ReviewValidationError("W04 page/reference conflicts with finding")
        height, width = self.view_state.reference_shape
        if self.roi_ref is not None:
            coords = _rect(_rect_wire(self.roi_ref))
            assert coords is not None
            x, y, w, h = coords
            if x + w > width or y + h > height:
                raise ReviewValidationError("ROI exceeds reference-space shape")
        if self.line_ref is not None:
            coords = _rect(_rect_wire(self.line_ref, line=True), line=True)
            assert coords is not None
            x1, y1, x2, y2 = coords
            if max(x1, x2) >= width or max(y1, y2) >= height:
                raise ReviewValidationError("line exceeds reference-space shape")
        if type(self.channel) is not str or not _LABEL.fullmatch(self.channel):
            raise ReviewValidationError("invalid analysis channel")
        _number(self.display_gain, "display_gain", minimum=0.000001)
        if self.difference_intent is not None:
            d = self.difference_intent
            if not isinstance(d, ReviewDifferenceIntentV1) or (
                d.reference_key != self.reference_key or d.target_key != self.pair_target_key
            ):
                raise ReviewValidationError("difference recipe disagrees with pair")
        if type(self.analysis) not in (tuple, list):
            raise ReviewValidationError("analysis captures must be a sequence")
        object.__setattr__(self, "analysis", tuple(self.analysis))
        if len(self.analysis) > MAX_ANALYSIS_PER_FINDING:
            raise ReviewValidationError("too many analysis captures")
        snapshot_ids: set[str] = set()
        for item in self.analysis:
            if not isinstance(item, ReviewAnalysisCaptureV1):
                raise ReviewValidationError("invalid analysis capture object")
            if item.status == "captured":
                assert item.context_json is not None
                context = parse_analysis_context(item.context_json)
                context_sources = cast(list[dict[str, Any]], context["sources"])
                if not {s["source_key"] for s in context_sources} <= set(self.source_keys):
                    raise ReviewValidationError("analysis source outside finding")
                if context["channel"] != self.channel:
                    raise ReviewValidationError("W02 analysis channel disagrees with Finding")
                captured_roi = context["roi_ref"]
                if (
                    (captured_roi is None) != (self.roi_ref is None)
                    or (captured_roi is not None
                        and tuple(cast(list[int], captured_roi)) != self.roi_ref)
                ):
                    raise ReviewValidationError("W02 analysis scope/ROI disagrees with Finding")
                if context["feature"] == "difference":
                    if self.difference_intent is None or self.pair_target_key is None:
                        raise ReviewValidationError("captured difference requires explicit recipe")
                    if [s["source_key"] for s in context_sources] != [
                        self.reference_key, self.pair_target_key
                    ]:
                        raise ReviewValidationError("W02 difference pair order differs")
                    if context["difference_cache_key"] is None:
                        raise ReviewValidationError("captured difference requires cache identity")
                    if self.difference_intent.channel != context["channel"]:
                        raise ReviewValidationError("W02 difference channel disagrees with recipe")
                    if (
                        (self.difference_intent.region == "Active ROI")
                        != (self.roi_ref is not None)
                    ):
                        raise ReviewValidationError("W02 difference region disagrees with ROI")
                # The W02 parser allows opaque snapshot IDs; Review v1 requires UUIDs.
                snapshot_id = _uuid(context["snapshot_id"])
                if snapshot_id in snapshot_ids:
                    raise ReviewValidationError("duplicate analysis snapshot id")
                snapshot_ids.add(snapshot_id)
        if self.availability not in _STATUSES:
            raise ReviewValidationError("unknown finding availability")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "note": self.note,
            "tags": list(self.tags),
            "captured_utc": self.captured_utc,
            "source_keys": list(self.source_keys),
            "reference_key": self.reference_key,
            "pair_target_key": self.pair_target_key,
            "view_state": self.view_state.to_dict(),
            "roi_ref": _rect_wire(self.roi_ref),
            "line_ref": _rect_wire(self.line_ref, line=True),
            "channel": self.channel,
            "display_gain": self.display_gain,
            "difference_intent": (
                self.difference_intent.to_dict() if self.difference_intent else None
            ),
            "analysis": [item.to_dict() for item in self.analysis],
            "availability": self.availability,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ReviewFindingV1:
        d = _fields(
            raw,
            {
                "id",
                "title",
                "note",
                "tags",
                "captured_utc",
                "source_keys",
                "reference_key",
                "pair_target_key",
                "view_state",
                "roi_ref",
                "line_ref",
                "channel",
                "display_gain",
                "difference_intent",
                "analysis",
                "availability",
            },
            "finding",
        )
        if type(d["tags"]) is not list or any(type(v) is not str for v in d["tags"]):
            raise ReviewValidationError("tags must be string array")
        if type(d["analysis"]) is not list or len(d["analysis"]) > MAX_ANALYSIS_PER_FINDING:
            raise ReviewValidationError("analysis must be bounded array")
        return cls(
            d["id"],
            d["title"],
            d["note"],
            tuple(d["tags"]),
            d["captured_utc"],
            _keys(d["source_keys"], maximum=6),
            d["reference_key"],
            d["pair_target_key"],
            ReviewViewStateV1.from_dict(d["view_state"]),
            _rect(d["roi_ref"]),
            _rect(d["line_ref"], line=True),
            d["channel"],
            d["display_gain"],
            ReviewDifferenceIntentV1.from_dict(d["difference_intent"])
            if d["difference_intent"] is not None
            else None,
            tuple(ReviewAnalysisCaptureV1.from_dict(item) for item in d["analysis"]),
            d["availability"],
        )


@dataclass(frozen=True)
class ReviewDocumentV1:
    document_id: str
    app_version: str
    created_utc: str
    updated_utc: str
    sources: tuple[ReviewSourceV1, ...]
    workspace_intent: ReviewWorkspaceIntentV1
    findings: tuple[ReviewFindingV1, ...]
    allow_local_paths: bool = False
    extensions_json: bytes = field(default=b"{}")

    def __post_init__(self) -> None:
        _uuid(self.document_id)
        if type(self.app_version) is not str or not _VERSION.fullmatch(self.app_version):
            raise ReviewValidationError("invalid application version")
        _time(self.created_utc)
        _time(self.updated_utc)
        created = datetime.fromisoformat(self.created_utc.replace("Z", "+00:00"))
        updated = datetime.fromisoformat(self.updated_utc.replace("Z", "+00:00"))
        if created > updated:
            raise ReviewValidationError("update precedes creation")
        if type(self.sources) not in (tuple, list) or type(self.findings) not in (tuple, list):
            raise ReviewValidationError("Review collections must be sequences")
        if len(self.sources) > MAX_SOURCES or len(self.findings) > MAX_FINDINGS:
            raise ReviewValidationError("review collection exceeds resource limits")
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "findings", tuple(self.findings))
        if any(not isinstance(source, ReviewSourceV1) for source in self.sources):
            raise ReviewValidationError("invalid Review source collection")
        source_keys = tuple(item.source_key for item in self.sources)
        if len(set(source_keys)) != len(source_keys):
            raise ReviewValidationError("duplicate Review source UUID")
        if not isinstance(self.workspace_intent, ReviewWorkspaceIntentV1) or (
            self.workspace_intent.source_order != source_keys
        ):
            raise ReviewValidationError("workspace source order must match sources")
        if type(self.allow_local_paths) is not bool:
            raise ReviewValidationError("allow_local_paths must be bool")
        if not self.allow_local_paths and any(s.locator.local_path for s in self.sources):
            raise ReviewValidationError("local path requires explicit Review opt-in")
        ids: set[str] = set()
        source_by_key = {source.source_key: source for source in self.sources}
        for finding in self.findings:
            if not isinstance(finding, ReviewFindingV1):
                raise ReviewValidationError("invalid finding object")
            if finding.id in ids:
                raise ReviewValidationError("duplicate finding UUID")
            ids.add(finding.id)
            if not set(finding.source_keys) <= set(source_keys):
                raise ReviewValidationError("finding references missing source")
            # Reject counterfeit W02 context and W04 reference geometry before
            # a historical source key can ever be rebound to loaded content.
            for key in finding.source_keys:
                expected_shape = source_by_key[key].native_signature.reference_shape
                if finding.view_state.source_shapes_ref[key] != expected_shape:
                    raise ReviewValidationError("finding W04 shape disagrees with source signature")
            for analysis in finding.analysis:
                if analysis.status != "captured":
                    continue
                assert analysis.context_json is not None
                context = parse_analysis_context(analysis.context_json)
                context_roi = context["roi_ref"]
                if (
                    (context_roi is None) != (finding.roi_ref is None)
                    or (context_roi is not None
                        and tuple(cast(list[int], context_roi)) != finding.roi_ref)
                ):
                    raise ReviewValidationError("W02 analysis ROI disagrees with finding")
                for captured in cast(list[dict[str, Any]], context["sources"]):
                    expected = source_by_key[captured["source_key"]]
                    signature = expected.native_signature
                    if (
                        captured["profile_signature"] != signature.profile_signature
                        or tuple(captured["native_shape"]) != signature.native_shape
                        or tuple(captured["reference_shape"]) != signature.reference_shape
                        or captured["native_dtype"] != signature.native_dtype
                        or captured["channel_layout"] != signature.channel_layout
                        or captured["effective_bits"] != signature.effective_bits
                        or captured["native_interpretation"] != signature.to_dict()["native_interpretation"]
                    ):
                        raise ReviewValidationError("W02 source interpretation conflicts with Review")
                    captured_digest = captured["sha256"]
                    if captured_digest is not None and (
                        captured_digest != expected.fingerprint.digest
                    ):
                        raise ReviewValidationError("W02 source fingerprint conflicts with Review")
        extensions = parse_bounded_json(self.extensions_json)
        if type(extensions) is not dict or len(self.extensions_json) > MAX_EXTENSIONS_BYTES:
            raise ReviewValidationError("invalid bounded local extensions")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": REVIEW_KIND,
            "schema_version": REVIEW_SCHEMA_VERSION,
            "document_id": self.document_id,
            "app_version": self.app_version,
            "created_utc": self.created_utc,
            "updated_utc": self.updated_utc,
            "sources": [s.to_dict() for s in self.sources],
            "workspace_intent": self.workspace_intent.to_dict(),
            "findings": [f.to_dict() for f in self.findings],
            "allow_local_paths": self.allow_local_paths,
            "extensions": parse_bounded_json(self.extensions_json),
        }

    @classmethod
    def from_dict(cls, raw: object) -> ReviewDocumentV1:
        d = _fields(
            raw,
            {
                "kind",
                "schema_version",
                "document_id",
                "app_version",
                "created_utc",
                "updated_utc",
                "sources",
                "workspace_intent",
                "findings",
                "allow_local_paths",
                "extensions",
            },
            "Review root",
        )
        if (
            d["kind"] != REVIEW_KIND
            or type(d["schema_version"]) is not int
            or (d["schema_version"] != REVIEW_SCHEMA_VERSION)
        ):
            raise ReviewValidationError("unknown Review kind/future schema version")
        if type(d["sources"]) is not list or len(d["sources"]) > MAX_SOURCES:
            raise ReviewValidationError("invalid source collection")
        if type(d["findings"]) is not list or len(d["findings"]) > MAX_FINDINGS:
            raise ReviewValidationError("invalid finding collection")
        return cls(
            d["document_id"],
            d["app_version"],
            d["created_utc"],
            d["updated_utc"],
            tuple(ReviewSourceV1.from_dict(s) for s in d["sources"]),
            ReviewWorkspaceIntentV1.from_dict(d["workspace_intent"]),
            tuple(ReviewFindingV1.from_dict(f) for f in d["findings"]),
            d["allow_local_paths"],
            canonical_json(d["extensions"], limit=MAX_EXTENSIONS_BYTES),
        )

    def to_bytes(self) -> bytes:
        # Reserve the trailing newline inside the same 16 MiB read/write budget.
        raw = canonical_json(self.to_dict(), limit=MAX_REVIEW_BYTES - 1)
        ReviewDocumentV1.from_dict(parse_bounded_json(raw))
        return raw + b"\n"

    @classmethod
    def from_bytes(cls, raw: bytes) -> ReviewDocumentV1:
        return cls.from_dict(parse_bounded_json(raw))


def new_review(sources: tuple[ReviewSourceV1, ...] = ()) -> ReviewDocumentV1:
    now = utc_now()
    return ReviewDocumentV1(
        str(uuid4()),
        __version__,
        now,
        now,
        sources,
        ReviewWorkspaceIntentV1(source_order=tuple(s.source_key for s in sources)),
        (),
    )


@dataclass(frozen=True)
class PortableReviewProjectionV1:
    """Fixed positive allowlist; never passes local dicts or arbitrary extensions."""

    payload_json: bytes

    def to_bytes(self) -> bytes:
        return self.payload_json + b"\n"


def _snapshot_id(capture: ReviewAnalysisCaptureV1) -> str:
    assert capture.context_json is not None
    return cast(str, parse_analysis_context(capture.context_json)["snapshot_id"])


def project_portable_review(
    document: ReviewDocumentV1,
    *,
    disclose_titles: bool = False,
    disclose_notes_and_tags: bool = False,
    disclose_source_names: bool = False,
) -> PortableReviewProjectionV1:
    """W10 can consume this safe base; free-text disclosure requires explicit UI review.

    Snapshot numeric projection is intentionally deferred to W10's evidence DTO.
    """
    names = {s.source_key: f"Source {i}" for i, s in enumerate(document.sources, 1)}
    source_rows = [
        {
            "source_id": names[s.source_key],
            "name": s.locator.basename if disclose_source_names else names[s.source_key],
            "native_shape": list(s.native_signature.native_shape),
            "reference_shape": list(s.native_signature.reference_shape),
            "native_dtype": s.native_signature.native_dtype,
            "channel_layout": s.native_signature.channel_layout,
            "effective_bits": s.native_signature.effective_bits,
            "fingerprint_state": s.fingerprint.state,
        }
        for s in document.sources
    ]
    finding_rows = []
    for index, finding in enumerate(document.findings, 1):
        finding_rows.append(
            {
                "id": finding.id,
                "title": finding.title if disclose_titles else f"Finding {index}",
                "note": finding.note if disclose_notes_and_tags else "",
                "tags": list(finding.tags) if disclose_notes_and_tags else [],
                "source_ids": [names[key] for key in finding.source_keys],
                "reference_source_id": names[finding.reference_key],
                "pair_target_source_id": (
                    names[finding.pair_target_key] if finding.pair_target_key else None
                ),
                "roi_ref": _rect_wire(finding.roi_ref),
                "line_ref": _rect_wire(finding.line_ref, line=True),
                "channel": finding.channel,
                "availability": finding.availability,
                "snapshot_ids": [
                    _snapshot_id(a) for a in finding.analysis if a.status == "captured"
                ],
            }
        )
    payload = {
        "kind": PORTABLE_KIND,
        "schema_version": 1,
        "sources": source_rows,
        "findings": finding_rows,
        "user_text_included": bool(disclose_titles or disclose_notes_and_tags),
        "source_names_included": disclose_source_names,
    }
    return PortableReviewProjectionV1(canonical_json(payload))
