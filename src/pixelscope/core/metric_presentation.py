"""Qt-free, read-only presentation of W02 native analysis measurements (W07).

No analysis, decoding, ROI sampling or normalization occurs here. Source identity,
measurement state and all arithmetic remain independent of display aliases.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Sequence

from pixelscope.core.review_analysis import (
    AnalysisMeasurementV1,
    AnalysisSourceV1,
    PresentedAnalysisTokenV1,
)

STATISTICS_METRICS = ("Min", "Max", "Mean", "Std", "P1", "P50", "P99")
FOCUSED_METRICS = ("Mean", "Std", "P99")
PERCENTILE_METRICS = ("P1", "P50", "P99")
NUMERIC_STATES = ("finite", "pos_inf", "neg_inf", "nan", "unavailable")


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    unit: str
    semantic: str
    # A normalized ratio is always represented on [0, 1], never silently as %.
    delta_allowed: bool = True


def metric_definition(name: str) -> MetricDefinition:
    """Conservative unit catalog shared by Statistics, Difference and Review.

    Unknown metrics are displayed without unit claims or Reference Delta.
    """
    if name in STATISTICS_METRICS or name in ("MAE", "RMSE", "P95", "Max difference"):
        return MetricDefinition(name, "native code", "native_code")
    if name == "MSE":
        return MetricDefinition(name, "native code²", "native_code_squared")
    if name == "PSNR":
        return MetricDefinition(name, "dB", "decibel", delta_allowed=False)
    if name == "Non-zero ratio":
        return MetricDefinition(name, "ratio [0,1]", "ratio")
    return MetricDefinition(name, "unspecified", "unknown", delta_allowed=False)


def format_metric_number(value: float | None, state: str, *, precision: int = 6) -> str:
    """Screen (6 sig. digits) and round-trip export (17 digits) are independent.

    State labels are explicit: missing values are not numerically zero.
    """
    if not 1 <= precision <= 17:
        raise ValueError("precision must be between 1 and 17 significant digits")
    if state not in NUMERIC_STATES:
        raise ValueError("unknown numerical state")
    if state == "unavailable":
        return "N/A"
    if state == "nan":
        return "NaN"
    if state == "pos_inf":
        return "+Inf"
    if state == "neg_inf":
        return "-Inf"
    if value is None or not isfinite(value):
        raise ValueError("finite state requires finite value")
    return format(value, f".{precision}g")


@dataclass(frozen=True)
class PivotColumn:
    source_key: str
    alias: str
    source: AnalysisSourceV1


@dataclass(frozen=True)
class PivotCell:
    source_key: str
    measurement: AnalysisMeasurementV1 | None
    unit: str
    absolute_delta: float | None
    relative_delta_percent: float | None
    delta_reason: str | None

    @property
    def state(self) -> str:
        return self.measurement.state if self.measurement is not None else "unavailable"

    @property
    def value(self) -> float | None:
        return self.measurement.value if self.measurement is not None else None

    @property
    def sample_count(self) -> int | None:
        return self.measurement.sample_count if self.measurement is not None else None

    def formatted_value(self, *, precision: int = 6) -> str:
        return format_metric_number(self.value, self.state, precision=precision)

    def formatted_delta(self, *, relative: bool = False, precision: int = 6) -> str:
        number = self.relative_delta_percent if relative else self.absolute_delta
        return format_metric_number(
            number, "finite" if number is not None else "unavailable", precision=precision
        )


@dataclass(frozen=True)
class PivotRow:
    channel: str
    metric: str
    definition: MetricDefinition
    cells: tuple[PivotCell, ...]


@dataclass(frozen=True)
class StatisticsPivot:
    """Immutable projection with source order matching the W02 presented token."""

    token: PresentedAnalysisTokenV1
    columns: tuple[PivotColumn, ...]
    rows: tuple[PivotRow, ...]
    reference_key: str | None


def _numeric_compatibility(
    token: PresentedAnalysisTokenV1,
    target: AnalysisSourceV1,
    reference: AnalysisSourceV1,
    target_measurement: AnalysisMeasurementV1 | None,
    reference_measurement: AnalysisMeasurementV1 | None,
    definition: MetricDefinition,
) -> str | None:
    if not definition.delta_allowed:
        return "Metric has no defined comparable Delta unit"
    if target_measurement is None or reference_measurement is None:
        return "Metric/channel unavailable in one source"
    if target_measurement.definition_revision != reference_measurement.definition_revision:
        return "Metric definition revisions differ"
    if target_measurement.state != "finite" or reference_measurement.state != "finite":
        return "Non-finite or unavailable measurement"
    if (
        target_measurement.sample_count is None
        or reference_measurement.sample_count is None
        or target_measurement.sample_count != reference_measurement.sample_count
    ):
        return "Native sample counts differ or are unavailable"
    if token.domain != "native":
        return "Different or unsupported numeric domain"
    if (
        target.channel_layout != reference.channel_layout
        or target.native_dtype != reference.native_dtype
        or target.effective_bits != reference.effective_bits
    ):
        return "Native layout, dtype or effective bit depth differs"
    if token.roi_ref is None and target.reference_shape != reference.reference_shape:
        return "Full-image reference bounds differ"
    t, r = target.native_interpretation, reference.native_interpretation
    if (
        t.sampling_semantics != r.sampling_semantics
        or t.sample_step_xy != r.sample_step_xy
        or t.sample_phase_xy != r.sample_phase_xy
        or t.sample_channel != r.sample_channel
        or t.cfa_pattern != r.cfa_pattern
        or t.cfa_phase_xy != r.cfa_phase_xy
        or t.yuv_layout != r.yuv_layout
        or t.yuv_chroma_step_xy != r.yuv_chroma_step_xy
        or t.raw_black_levels != r.raw_black_levels
        or t.raw_white_level != r.raw_white_level
    ):
        return "Native sample footprint, CFA phase or code calibration differs"
    if target_measurement.channel != reference_measurement.channel:
        return "Channels differ"
    return None


def build_statistics_pivot(
    token: PresentedAnalysisTokenV1,
    sources: Sequence[AnalysisSourceV1],
    measurements: Sequence[AnalysisMeasurementV1],
    aliases: Mapping[str, str],
    *,
    channel: str = "All",
    metrics: Sequence[str] = STATISTICS_METRICS,
    reference_key: str | None = None,
) -> StatisticsPivot:
    """Build a read-only row=metric, column=source table from W02 typed data.

    The caller must separately verify that the token is CURRENT, never just
    PRESENTED: historical snapshots can use this projection only as history.
    """
    if token.feature != "statistics":
        raise ValueError("pivot requires a Statistics token")
    if not 1 <= len(sources) <= 6:
        raise ValueError("pivot requires between 1 and 6 presented sources")
    if tuple(s.source_key for s in sources) != token.source_keys:
        raise ValueError("source order/identity is not aligned with token")
    if tuple((s.document_id, s.generation) for s in sources) != token.source_documents:
        raise ValueError("stale source generation")
    if tuple(s.profile_signature for s in sources) != token.profile_signatures:
        raise ValueError("stale interpretation profile")
    if token.domain != "native":
        raise ValueError("Statistics pivot accepts native domain only")
    if reference_key is not None and reference_key not in token.source_keys:
        raise ValueError("Reference source is not in current comparison")
    if not metrics or any(name not in STATISTICS_METRICS for name in metrics):
        raise ValueError("unsupported Statistics metric filter")
    if len(set(metrics)) != len(metrics):
        raise ValueError("duplicated Statistics metric filter")

    source_by_key = {s.source_key: s for s in sources}
    values: dict[tuple[str, str, str], AnalysisMeasurementV1] = {}
    channels: list[str] = []
    for item in measurements:
        if item.source_key not in source_by_key:
            raise ValueError("measurement source not in token")
        key = (item.source_key, item.channel, item.metric)
        if key in values:
            raise ValueError("ambiguous duplicate measurement")
        values[key] = item
        if item.channel not in channels and item.metric in STATISTICS_METRICS:
            channels.append(item.channel)
    visible_channels = channels if channel == "All" else [channel]
    if channel != "All" and channel not in channels:
        visible_channels = []

    columns = tuple(
        PivotColumn(source.source_key, aliases.get(source.source_key) or f"Source {index}", source)
        for index, source in enumerate(sources, 1)
    )
    rows: list[PivotRow] = []
    for metric in metrics:
        definition = metric_definition(metric)
        for current_channel in visible_channels:
            if not any((s.source_key, current_channel, metric) in values for s in sources):
                continue
            reference_measurement = (
                values.get((reference_key, current_channel, metric))
                if reference_key is not None
                else None
            )
            reference = source_by_key[reference_key] if reference_key is not None else None
            cells: list[PivotCell] = []
            for source in sources:
                item = values.get((source.source_key, current_channel, metric))
                reason = (
                    _numeric_compatibility(
                        token, source, reference, item, reference_measurement, definition
                    )
                    if reference is not None
                    else "No Reference selected"
                )
                delta: float | None = None
                relative: float | None = None
                if reason is None and item is not None and reference_measurement is not None:
                    assert item.value is not None and reference_measurement.value is not None
                    candidate = item.value - reference_measurement.value
                    if isfinite(candidate):
                        delta = candidate
                        denominator = abs(reference_measurement.value)
                        if denominator == 0:
                            reason = "Relative Delta undefined: Reference is zero"
                        else:
                            percent = candidate / denominator * 100.0
                            if isfinite(percent):
                                relative = percent
                            else:
                                reason = "Relative Delta overflow"
                    else:
                        reason = "Absolute Delta overflow"
                cells.append(
                    PivotCell(source.source_key, item, definition.unit, delta, relative, reason)
                )
            rows.append(PivotRow(current_channel, metric, definition, tuple(cells)))
    return StatisticsPivot(token, columns, tuple(rows), reference_key)
