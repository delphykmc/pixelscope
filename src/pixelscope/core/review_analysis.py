# fmt: off
# ruff: noqa: E721, E501  # Strict JSON primitives: bool must not pass as int
"""Qt-free immutable analysis capture and portable context contract (Issue #210 W02).

Runtime document IDs are only an ephemeral liveness guard. Portable context never
contains document IDs, source paths, display aliases, native pixels or arbitrary
profile dictionaries. W09 may inject durable Review source keys via the UI adapter.
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Sized
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Protocol
from uuid import UUID, uuid4

FEATURES = frozenset({"statistics", "histogram", "line", "difference"})
_STATE = frozenset({"finite", "pos_inf", "neg_inf", "nan", "unavailable"})
_SAFE_NAME = re.compile(r"^[\w .:+-]{1,96}$", flags=re.UNICODE)
_SAFE_DTYPE = re.compile(
    r"^(?:bool|u?int(?:8|16|32|64)|float(?:16|32|64)|[<>=|](?:[iu](?:1|2|4|8)|f(?:2|4|8)|b1))$"
)
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
MAX_CONTEXT_BYTES = 8 * 1024 * 1024
MAX_MEASUREMENTS = 200_000
MAX_SERIES_SAMPLES = 200_000


def _is_uuid(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


@dataclass(frozen=True)
class PresentedAnalysisTokenV1:
    feature: str
    request_id: str
    request_epoch: int
    source_documents: tuple[tuple[str, int], ...]
    source_keys: tuple[str, ...]
    roi_ref: tuple[int, int, int, int] | None
    channel: str
    domain: str
    profile_signatures: tuple[str, ...]
    difference_cache_key: str | None

    def __post_init__(self) -> None:
        if (self.feature not in FEATURES or type(self.request_id) is not str
                or not self.request_id or type(self.request_epoch) is not int
                or self.request_epoch < 0):
            raise ValueError("invalid presented analysis feature/request")
        if not self.source_documents or len(self.source_documents) != len(self.source_keys):
            raise ValueError("source identities must be nonempty and aligned")
        if len(set(self.source_keys)) != len(self.source_keys):
            raise ValueError("duplicate source keys")
        if any(not _is_uuid(key) for key in self.source_keys):
            raise ValueError("source key must be a Review UUID")
        if len(self.profile_signatures) != len(self.source_keys):
            raise ValueError("profile signatures must align with sources")
        if any(not ident or not isinstance(gen, int) or gen < 0
               for ident, gen in self.source_documents):
            raise ValueError("invalid source document generation")
        if self.roi_ref is not None:
            x, y, w, h = self.roi_ref
            if any(type(v) is not int for v in self.roi_ref) or min(x, y) < 0 or min(w, h) <= 0:
                raise ValueError("ROI must be positive half-open reference-space bounds")
        for value in (self.channel, self.domain):
            if not _SAFE_NAME.fullmatch(value):
                raise ValueError("unsafe analysis channel/domain")


@dataclass(frozen=True)
class AnalysisSourceV1:
    source_key: str
    document_id: str
    generation: int
    native_shape: tuple[int, ...]
    reference_shape: tuple[int, int]
    native_dtype: str
    channel_layout: str
    effective_bits: int
    profile_signature: str
    sha256: str | None = None
    verification: Literal["verified", "unverified"] = "unverified"

    def __post_init__(self) -> None:
        if not _is_uuid(self.source_key) or not self.document_id or type(self.generation) is not int or self.generation < 0:
            raise ValueError("invalid source identity")
        if len(self.native_shape) not in (2, 3) or any(v <= 0 for v in self.native_shape):
            raise ValueError("invalid native shape")
        if len(self.reference_shape) != 2 or any(v <= 0 for v in self.reference_shape):
            raise ValueError("invalid reference shape")
        if not 1 <= self.effective_bits <= 64:
            raise ValueError("invalid source bit depth")
        if not _SAFE_DTYPE.fullmatch(self.native_dtype) or not _SAFE_NAME.fullmatch(self.channel_layout):
            raise ValueError("unsafe native format")
        if not _DIGEST.fullmatch(self.profile_signature):
            raise ValueError("profile signature must be a non-path SHA-256 digest")
        if self.sha256 is not None and not _DIGEST.fullmatch(self.sha256):
            raise ValueError("invalid SHA-256")
        if self.verification == "verified" and self.sha256 is None:
            raise ValueError("verified source requires digest")


@dataclass(frozen=True)
class AnalysisMeasurementV1:
    source_key: str
    channel: str
    metric: str
    value: float | None
    sample_count: int | None
    definition_revision: str = "native-v1"
    state: str = "finite"

    def __post_init__(self) -> None:
        if not self.source_key or any(not _SAFE_NAME.fullmatch(s) for s in (
            self.channel, self.metric, self.definition_revision
        )):
            raise ValueError("invalid measurement label")
        if self.state not in _STATE:
            raise ValueError("invalid numerical availability")
        if self.sample_count is not None and (
            type(self.sample_count) is not int or self.sample_count < 0
        ):
            raise ValueError("invalid sample count")
        if self.state == "finite" and (
            self.value is None or not math.isfinite(self.value)
        ):
            raise ValueError("finite measurements require finite values")
        if self.state != "finite" and self.value is not None:
            raise ValueError("nonfinite/unavailable values use explicit state")


def measurement(
    source_key: str, channel: str, metric: str, value: float | int | None,
    sample_count: int | None, definition_revision: str = "native-v1",
) -> AnalysisMeasurementV1:
    if value is None:
        return AnalysisMeasurementV1(
            source_key, channel, metric, None, sample_count, definition_revision, "unavailable"
        )
    number = float(value)
    state = "nan" if math.isnan(number) else (
        "pos_inf" if number > 0 else "neg_inf"
    ) if math.isinf(number) else "finite"
    return AnalysisMeasurementV1(
        source_key, channel, metric,
        number if state == "finite" else None,
        sample_count, definition_revision, state,
    )



@dataclass(frozen=True)
class AnalysisSeriesV1:
    """Frozen native histogram bins or line points, independent of plot mode.

    Histogram coordinates are N+1 native bin edges; line coordinates are N
    native reference-distance positions. Nonfinite values use explicit states.
    """

    source_key: str
    channel: str
    kind: Literal["histogram", "line"]
    coordinates: tuple[float, ...]
    values: tuple[int | float | None, ...]
    value_states: tuple[str, ...]
    sample_count: int | None
    definition_revision: str

    def __post_init__(self) -> None:
        if not _is_uuid(self.source_key):
            raise ValueError("invalid series source")
        if (self.kind not in ("histogram", "line")
                or not _SAFE_NAME.fullmatch(self.channel)
                or not _SAFE_NAME.fullmatch(self.definition_revision)):
            raise ValueError("invalid series classification")
        count = len(self.values)
        if not 1 <= count <= MAX_SERIES_SAMPLES:
            raise ValueError("series count outside capture bounds")
        expected = count + 1 if self.kind == "histogram" else count
        if len(self.coordinates) != expected or len(self.value_states) != count:
            raise ValueError("series coordinate/state cardinality mismatch")
        if any(not math.isfinite(v) for v in self.coordinates):
            raise ValueError("nonfinite series coordinates")
        if self.sample_count is not None and (
            type(self.sample_count) is not int or self.sample_count < 0
        ):
            raise ValueError("invalid series sample count")
        for value, state in zip(self.values, self.value_states, strict=True):
            if state not in _STATE:
                raise ValueError("invalid series value state")
            if state == "finite":
                if (not isinstance(value, (int, float)) or isinstance(value, bool)
                        or not math.isfinite(value)):
                    raise ValueError("finite series value required")
            elif value is not None:
                raise ValueError("nonfinite series value must be null")


def freeze_series_values(values: object) -> tuple[
    tuple[int | float | None, ...], tuple[str, ...]
]:
    """Bounded copy of a 1-D numeric iterable; reject large inputs before copying."""
    if not isinstance(values, Sized):
        raise ValueError("series must have bounded length")
    if len(values) > MAX_SERIES_SAMPLES:
        raise ValueError("series exceeds budget")
    if not isinstance(values, Iterable):
        raise ValueError("series is not iterable")
    result: list[int | float | None] = []
    states: list[str] = []
    for value in values:
        # Preserve integer histogram counts losslessly.
        native = int(value) if hasattr(value, "dtype") and value.dtype.kind in "iu" else float(value)
        if isinstance(native, int) or math.isfinite(native):
            result.append(native)
            states.append("finite")
        else:
            result.append(None)
            states.append("nan" if math.isnan(native) else
                          "pos_inf" if native > 0 else "neg_inf")
    return tuple(result), tuple(states)


@dataclass(frozen=True)
class AnalysisSnapshotV1:
    snapshot_id: str
    captured_utc: str
    token: PresentedAnalysisTokenV1
    sources: tuple[AnalysisSourceV1, ...]
    measurements: tuple[AnalysisMeasurementV1, ...]
    presentation: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    series: tuple[AnalysisSeriesV1, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.snapshot_id or len(self.sources) != len(self.token.source_keys):
            raise ValueError("invalid snapshot source cardinality")
        if tuple(s.source_key for s in self.sources) != self.token.source_keys:
            raise ValueError("snapshot sources disagree with presented token")
        if tuple((s.document_id, s.generation) for s in self.sources) != self.token.source_documents:
            raise ValueError("snapshot generations disagree with presented token")
        if tuple(s.profile_signature for s in self.sources) != self.token.profile_signatures:
            raise ValueError("snapshot profiles disagree with presented token")
        if len(self.measurements) > MAX_MEASUREMENTS:
            raise ValueError("too many measurements")
        if any(m.source_key not in self.token.source_keys for m in self.measurements):
            raise ValueError("measurement source not presented")
        if sum(len(item.values) for item in self.series) > MAX_SERIES_SAMPLES:
            raise ValueError("series budget exceeded")
        if any(item.source_key not in self.token.source_keys for item in self.series):
            raise ValueError("series source not presented")
        if any(item.kind != self.token.feature for item in self.series):
            raise ValueError("series feature mismatch")
        if any(not _SAFE_NAME.fullmatch(k) or not _SAFE_NAME.fullmatch(v)
               for k, v in self.presentation):
            raise ValueError("unsafe presentation fields")


@dataclass(frozen=True)
class CaptureResult:
    snapshot: AnalysisSnapshotV1 | None
    reason: str | None = None

    @property
    def available(self) -> bool:
        return self.snapshot is not None


class AnalysisPanelAdapter(Protocol):
    def get_presented_analysis_token(self) -> PresentedAnalysisTokenV1 | None: ...
    def get_current_analysis_token(self) -> PresentedAnalysisTokenV1 | None: ...
    def read_presented_analysis(
        self,
    ) -> tuple[tuple[AnalysisSourceV1, ...],
               tuple[AnalysisMeasurementV1, ...],
               tuple[tuple[str, str], ...]]: ...


def capture_presented_analysis(
    panel: AnalysisPanelAdapter, expected: PresentedAnalysisTokenV1,
) -> CaptureResult:
    """Fail closed on pending, changed ROI, source generation, pair or request.

    The adapter copies scalar data before returning. Two token comparisons bracket
    extraction; Qt work/long source hashing is NOT performed here.
    """
    try:
        before = panel.get_presented_analysis_token()
        current = panel.get_current_analysis_token()
        if before is None or current is None:
            return CaptureResult(None, "pending_or_uncomputed")
        if before != expected or current != expected:
            return CaptureResult(None, "stale_or_mismatched")
        sources, values, presentation = panel.read_presented_analysis()
        series_reader = getattr(panel, "read_presented_series", None)
        series = tuple(series_reader()) if callable(series_reader) else ()
        if (panel.get_presented_analysis_token() != expected
                or panel.get_current_analysis_token() != expected):
            return CaptureResult(None, "changed_during_capture")
        return CaptureResult(AnalysisSnapshotV1(
            snapshot_id=str(uuid4()),
            captured_utc=datetime.now(timezone.utc).isoformat(),
            token=expected,
            sources=tuple(sources),
            measurements=tuple(values),
            presentation=tuple(presentation),
            series=series,
        ))
    except (RuntimeError, TypeError, ValueError, AttributeError, IndexError) as exc:
        return CaptureResult(None, f"capture_unavailable:{type(exc).__name__}")


def serialize_analysis_context(snapshot: AnalysisSnapshotV1) -> bytes:
    """Positive allowlist: no absolute path, arbitrary source data, or runtime IDs."""
    token = snapshot.token
    public = {
        "kind": "pixelscope-analysis-context",
        "schema_version": 1,
        "snapshot_id": snapshot.snapshot_id,
        "captured_utc": snapshot.captured_utc,
        "feature": token.feature,
        "request_id": token.request_id,
        "request_epoch": token.request_epoch,
        "scope": "roi" if token.roi_ref is not None else "full",
        "roi_ref": list(token.roi_ref) if token.roi_ref is not None else None,
        "channel": token.channel,
        "domain": token.domain,
        "difference_cache_key": token.difference_cache_key,
        "sources": [
            {
                "source_key": s.source_key,
                "native_shape": list(s.native_shape),
                "reference_shape": list(s.reference_shape),
                "native_dtype": s.native_dtype,
                "channel_layout": s.channel_layout,
                "effective_bits": s.effective_bits,
                "profile_signature": s.profile_signature,
                "sha256": s.sha256,
                "verification": s.verification,
            } for s in snapshot.sources
        ],
        "measurements": [
            {
                "source_key": m.source_key,
                "channel": m.channel,
                "metric": m.metric,
                "state": m.state,
                "value": m.value,
                "sample_count": m.sample_count,
                "definition_revision": m.definition_revision,
            } for m in snapshot.measurements
        ],
        "presentation": dict(snapshot.presentation),
        "series": [
            {
                "source_key": entry.source_key,
                "channel": entry.channel,
                "kind": entry.kind,
                "coordinates": list(entry.coordinates),
                "values": list(entry.values),
                "value_states": list(entry.value_states),
                "sample_count": entry.sample_count,
                "definition_revision": entry.definition_revision,
            }
            for entry in snapshot.series
        ],
    }
    raw = json.dumps(
        public, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(raw) > MAX_CONTEXT_BYTES:
        raise ValueError("analysis context exceeds size budget")
    return raw


def parse_analysis_context(raw: bytes) -> dict[str, object]:
    """Validate the portable wire schema without pretending it is live state."""
    if len(raw) > MAX_CONTEXT_BYTES:
        raise ValueError("context exceeds size budget")

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        out: dict[str, object] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate context key")
            out[key] = value
        return out

    data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    if type(data) is not dict:
        raise ValueError("context root must be object")
    root = {
        "kind", "schema_version", "snapshot_id", "captured_utc", "feature",
        "request_id", "request_epoch", "scope", "roi_ref", "channel", "domain",
        "difference_cache_key", "sources", "measurements", "presentation",
    }
    if set(data) not in (root, root | {"series"}) or data["kind"] != "pixelscope-analysis-context" or type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("unsupported context kind or schema")
    if (type(data["feature"]) is not str or data["feature"] not in FEATURES
            or type(data["scope"]) is not str or data["scope"] not in ("full", "roi")):
        raise ValueError("unsupported analysis feature/scope")
    if (type(data["request_epoch"]) is not int or data["request_epoch"] < 0
            or any(type(data[k]) is not str or not data[k]
                   for k in ("snapshot_id", "captured_utc", "request_id"))):
        raise ValueError("invalid request information")
    if not all(type(data[k]) is str and _SAFE_NAME.fullmatch(data[k])
               for k in ("channel", "domain")):
        raise ValueError("invalid channel/domain")
    roi = data["roi_ref"]
    if (roi is None) != (data["scope"] == "full"):
        raise ValueError("ROI/scope mismatch")
    if roi is not None and (
        type(roi) is not list or len(roi) != 4
        or any(type(x) is not int for x in roi)
        or min(roi[:2]) < 0 or min(roi[2:]) <= 0
    ):
        raise ValueError("invalid ROI")
    if data["difference_cache_key"] is not None and (
        type(data["difference_cache_key"]) is not str
        or not _DIGEST.fullmatch(data["difference_cache_key"])
    ):
        raise ValueError("invalid cache digest")
    sources = data["sources"]
    if type(sources) is not list or not 1 <= len(sources) <= 6:
        raise ValueError("invalid source collection")
    keys: set[str] = set()
    for source in sources:
        if type(source) is not dict or set(source) != {
            "source_key", "native_shape", "reference_shape", "native_dtype",
            "channel_layout", "effective_bits", "profile_signature",
            "sha256", "verification",
        }:
            raise ValueError("unknown source fields")
        key = source["source_key"]
        if not _is_uuid(key) or key in keys:
            raise ValueError("duplicate/invalid source key")
        keys.add(key)
        for shape_key, sizes in (("native_shape", (2, 3)), ("reference_shape", (2,))):
            shape = source[shape_key]
            if type(shape) is not list or len(shape) not in sizes or any(
                type(v) is not int or v <= 0 for v in shape
            ):
                raise ValueError("invalid source shape")
        if type(source["effective_bits"]) is not int or not 1 <= source["effective_bits"] <= 64:
            raise ValueError("invalid bits")
        if (type(source["native_dtype"]) is not str or not _SAFE_DTYPE.fullmatch(source["native_dtype"])
                or type(source["channel_layout"]) is not str or not _SAFE_NAME.fullmatch(source["channel_layout"])):
            raise ValueError("invalid native signature")
        if type(source["profile_signature"]) is not str or not _DIGEST.fullmatch(source["profile_signature"]):
            raise ValueError("invalid profile signature")
        sha = source["sha256"]
        if sha is not None and (type(sha) is not str or not _DIGEST.fullmatch(sha)):
            raise ValueError("invalid digest")
        if type(source["verification"]) is not str or source["verification"] not in ("verified", "unverified") or (
            source["verification"] == "verified" and sha is None
        ):
            raise ValueError("invalid verification")
    values = data["measurements"]
    if type(values) is not list or len(values) > MAX_MEASUREMENTS:
        raise ValueError("invalid measurement collection")
    for item in values:
        if type(item) is not dict or set(item) != {
            "source_key", "channel", "metric", "state", "value",
            "sample_count", "definition_revision",
        } or item["source_key"] not in keys:
            raise ValueError("invalid measurement keys")
        if any(type(item[k]) is not str or not _SAFE_NAME.fullmatch(item[k])
               for k in ("channel", "metric", "definition_revision")):
            raise ValueError("invalid measurement label")
        if type(item["state"]) is not str or item["state"] not in _STATE:
            raise ValueError("invalid numeric state")
        if item["state"] == "finite":
            if type(item["value"]) not in (int, float) or not math.isfinite(item["value"]):
                raise ValueError("finite value required")
        elif item["value"] is not None:
            raise ValueError("nonfinite value must be null")
        count = item["sample_count"]
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("invalid sample count")
    series_data = data.get("series", [])
    if type(series_data) is not list:
        raise ValueError("invalid series array")
    series_size = 0
    for item in series_data:
        if type(item) is not dict or set(item) != {
            "source_key", "channel", "kind", "coordinates", "values",
            "value_states", "sample_count", "definition_revision",
        }:
            raise ValueError("invalid series shape")
        if item["source_key"] not in keys or item["kind"] != data["feature"]:
            raise ValueError("series source or feature mismatch")
        if any(type(item[k]) is not str or not _SAFE_NAME.fullmatch(item[k])
               for k in ("channel", "definition_revision")):
            raise ValueError("invalid series label")
        coords, values, states = (
            item["coordinates"], item["values"], item["value_states"]
        )
        if any(type(a) is not list for a in (coords, values, states)):
            raise ValueError("invalid series arrays")
        count = len(values)
        series_size += count
        if not 1 <= count <= MAX_SERIES_SAMPLES or series_size > MAX_SERIES_SAMPLES:
            raise ValueError("series size budget exceeded")
        if len(states) != count or len(coords) != (
            count + 1 if item["kind"] == "histogram" else count
        ):
            raise ValueError("series coordinate cardinality")
        if any(type(x) not in (float, int) or not math.isfinite(x) for x in coords):
            raise ValueError("nonfinite series coordinate")
        for number, state in zip(values, states, strict=True):
            if state not in _STATE:
                raise ValueError("invalid series state")
            if state == "finite":
                if type(number) not in (float, int) or not math.isfinite(number):
                    raise ValueError("invalid finite series value")
            elif number is not None:
                raise ValueError("invalid unavailable series value")
        if item["sample_count"] is not None and (
            type(item["sample_count"]) is not int or item["sample_count"] < 0
        ):
            raise ValueError("invalid series sample count")
    presentation = data["presentation"]
    if type(presentation) is not dict or any(
        type(k) is not str or type(v) is not str
        or not _SAFE_NAME.fullmatch(k) or not _SAFE_NAME.fullmatch(v)
        for k, v in presentation.items()
    ):
        raise ValueError("invalid presentation")
    return data
