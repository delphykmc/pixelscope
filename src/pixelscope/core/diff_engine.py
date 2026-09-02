from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from math import ceil, floor, inf, log10, sqrt
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.image_document import ImageDocument

MAX_METRIC_HISTOGRAM_BINS = 65_536
DEFAULT_METRIC_CHUNK_ELEMENTS = 1_048_576
NORMALIZED_QUANTILE_LEVELS = 65_536
NORMALIZED_QUANTILE_MAX_ERROR_FS = 1.0 / (NORMALIZED_QUANTILE_LEVELS - 1)

DifferenceFamily = Literal["GRAY", "RGB", "BAYER", "YUV"]
DifferenceDomain = Literal["native", "normalized"]
DifferenceReasonCode = Literal[
    "ok",
    "select-two",
    "source-unavailable",
    "size-mismatch",
    "layout-mismatch",
    "cfa-mismatch",
    "unsupported-layout",
]


@dataclass(frozen=True)
class DifferenceCompatibility:
    """Pure-core Difference family/domain decision for one document pair."""

    compatible: bool
    family: DifferenceFamily | None
    domain: DifferenceDomain | None
    reason_code: DifferenceReasonCode
    detail: str
    effective_bit_depth_a: int
    effective_bit_depth_b: int
    data_range: float | None


@dataclass(frozen=True)
class DifferenceMetrics:
    mae: float
    mse: float
    rmse: float
    psnr: float
    p95: float
    p99: float
    maximum_absolute: float
    nonzero_ratio: float
    minimum_signed: float
    maximum_signed: float
    minimum_absolute: float


@dataclass(frozen=True)
class DifferenceAnalysisResult:
    numerical: NDArray[np.generic]
    signed: NDArray[np.generic]
    metrics: DifferenceMetrics
    histogram_counts: NDArray[np.int64]
    histogram_edges: NDArray[np.float64]


def _layout_family(document: ImageDocument) -> DifferenceFamily | None:
    if document.channel_layout == "GRAY":
        return "GRAY"
    if document.channel_layout == "BAYER":
        return "BAYER"
    if document.channel_layout in ("RGB", "RGBA"):
        return "RGB"
    return None


def _incompatible(
    a: ImageDocument,
    b: ImageDocument,
    reason_code: DifferenceReasonCode,
    detail: str,
    family: DifferenceFamily | None = None,
) -> DifferenceCompatibility:
    return DifferenceCompatibility(
        compatible=False,
        family=family,
        domain=None,
        reason_code=reason_code,
        detail=detail,
        effective_bit_depth_a=a.bit_depth,
        effective_bit_depth_b=b.bit_depth,
        data_range=None,
    )


def difference_compatibility(a: ImageDocument, b: ImageDocument) -> DifferenceCompatibility:
    """Return structured family/domain compatibility for the production Difference path."""

    family_a = _layout_family(a)
    family_b = _layout_family(b)
    if a.source is None or b.source is None:
        return _incompatible(
            a,
            b,
            "source-unavailable",
            "Both images must be loaded before comparison.",
        )
    if a.shape[:2] != b.shape[:2]:
        return _incompatible(
            a,
            b,
            "size-mismatch",
            f"Image dimensions do not match: {a.shape[:2]} vs {b.shape[:2]}.",
        )
    if family_a is None or family_b is None:
        return _incompatible(
            a,
            b,
            "unsupported-layout",
            "Difference supports Gray, RGB/RGBA, or Bayer images; "
            f"received {a.channel_layout} and {b.channel_layout}.",
        )
    if family_a != family_b:
        return _incompatible(
            a,
            b,
            "layout-mismatch",
            f"Difference image families do not match: {family_a} vs {family_b}.",
        )
    if family_a == "BAYER":
        pattern_a = getattr(a.raw_profile, "bayer_pattern", None)
        pattern_b = getattr(b.raw_profile, "bayer_pattern", None)
        if pattern_a is None or pattern_b is None:
            return _incompatible(
                a,
                b,
                "unsupported-layout",
                "Bayer Difference requires a CFA pattern for both images.",
                family_a,
            )
        if pattern_a != pattern_b:
            return _incompatible(
                a,
                b,
                "cfa-mismatch",
                f"Bayer CFA patterns do not match: {pattern_a} vs {pattern_b}.",
                family_a,
            )
    if a.bit_depth <= 0 or b.bit_depth <= 0:
        return _incompatible(
            a,
            b,
            "unsupported-layout",
            "Difference requires positive effective bit depths.",
            family_a,
        )
    domain: DifferenceDomain = "native" if a.bit_depth == b.bit_depth else "normalized"
    data_range = float((1 << a.bit_depth) - 1) if domain == "native" else 1.0
    return DifferenceCompatibility(
        compatible=True,
        family=family_a,
        domain=domain,
        reason_code="ok",
        detail="Compatible Difference pair.",
        effective_bit_depth_a=a.bit_depth,
        effective_bit_depth_b=b.bit_depth,
        data_range=data_range,
    )


def validate_difference_documents(
    a: ImageDocument,
    b: ImageDocument,
    normalized_domain: bool = False,
) -> str | None:
    """Backward-compatible string adapter over the structured compatibility result."""

    del normalized_domain
    result = difference_compatibility(a, b)
    return None if result.compatible else result.detail


def _full_scale(bit_depth: int) -> float:
    maximum = float((1 << bit_depth) - 1)
    if maximum <= 0:
        raise ValueError("bit depth must be positive")
    return maximum


def _normalized_difference(
    a: NDArray[np.generic],
    b: NDArray[np.generic],
    bit_depth_a: int,
    bit_depth_b: int,
    *,
    absolute: bool,
    chunk_elements: int = DEFAULT_METRIC_CHUNK_ELEMENTS,
) -> NDArray[np.float32]:
    """Calculate normalized A-B with bounded float32 working chunks."""

    _validate_pair(a, b)
    if chunk_elements <= 0:
        raise ValueError("normalization chunk size must be positive")
    scale_a = np.float32(1.0 / _full_scale(bit_depth_a))
    scale_b = np.float32(1.0 / _full_scale(bit_depth_b))
    output = np.empty(a.shape, dtype=np.float32)
    iterator = np.nditer(
        [a, b, output],
        flags=["external_loop", "buffered"],
        op_flags=[["readonly"], ["readonly"], ["writeonly"]],
        order="C",
        buffersize=chunk_elements,
    )
    for a_chunk, b_chunk, output_chunk in iterator:
        normalized_a = np.array(a_chunk, dtype=np.float32, copy=True)
        normalized_b = np.array(b_chunk, dtype=np.float32, copy=True)
        np.multiply(normalized_a, scale_a, out=normalized_a)
        np.multiply(normalized_b, scale_b, out=normalized_b)
        np.subtract(normalized_a, normalized_b, out=output_chunk, casting="unsafe")
        if absolute:
            np.abs(output_chunk, out=output_chunk)
    return output


def normalized_absolute_difference(
    a: NDArray[np.generic],
    b: NDArray[np.generic],
    bit_depth_a: int,
    bit_depth_b: int,
    *,
    chunk_elements: int = DEFAULT_METRIC_CHUNK_ELEMENTS,
) -> NDArray[np.float32]:
    """Return abs(A/full_scale_A - B/full_scale_B) as canonical float32."""

    return _normalized_difference(
        a,
        b,
        bit_depth_a,
        bit_depth_b,
        absolute=True,
        chunk_elements=chunk_elements,
    )


def normalized_signed_difference(
    a: NDArray[np.generic],
    b: NDArray[np.generic],
    bit_depth_a: int,
    bit_depth_b: int,
    *,
    chunk_elements: int = DEFAULT_METRIC_CHUNK_ELEMENTS,
) -> NDArray[np.float32]:
    """Return A/full_scale_A - B/full_scale_B as bounded-compute float32."""

    return _normalized_difference(
        a,
        b,
        bit_depth_a,
        bit_depth_b,
        absolute=False,
        chunk_elements=chunk_elements,
    )


def analyze_difference(
    a: NDArray[np.generic],
    b: NDArray[np.generic],
    *,
    mode: Literal["absolute", "signed", "threshold"] = "absolute",
    domain: DifferenceDomain = "native",
    bit_depth_a: int | None = None,
    bit_depth_b: int | None = None,
    threshold: float = 0.0,
    data_range: float | None = None,
    bins: int = 256,
) -> DifferenceAnalysisResult:
    """Calculate overflow-safe difference pixels, metrics, and one histogram."""

    _validate_pair(a, b)
    peak: float
    if domain == "normalized":
        if bit_depth_a is None or bit_depth_b is None:
            raise ValueError("normalized comparison requires both bit depths")
        signed: NDArray[np.generic] = normalized_signed_difference(
            a,
            b,
            bit_depth_a,
            bit_depth_b,
        )
        peak = 1.0
    elif domain == "native":
        signed = signed_difference(a, b).astype(np.float64)
        selected_range = data_range
        if selected_range is None:
            if np.issubdtype(a.dtype, np.integer):
                selected_range = float((1 << (a.dtype.itemsize * 8)) - 1)
            else:
                selected_range = float(np.asarray(np.max(a)).item()) - float(
                    np.asarray(np.min(a)).item()
                )
        peak = selected_range
    else:
        raise ValueError(f"unsupported difference domain: {domain}")
    absolute = np.abs(signed)
    if mode == "absolute":
        numerical: NDArray[np.generic] = absolute
    elif mode == "signed":
        numerical = signed
    elif mode == "threshold":
        numerical = (absolute > threshold).astype(np.uint8)
    else:
        raise ValueError(f"unsupported difference mode: {mode}")
    metrics = absolute_difference_metrics(absolute, peak)
    metrics = replace(
        metrics,
        minimum_signed=float(np.asarray(np.min(signed)).item()),
        maximum_signed=float(np.asarray(np.max(signed)).item()),
    )
    histogram_counts, histogram_edges = np.histogram(numerical, bins=bins)
    return DifferenceAnalysisResult(
        numerical=numerical,
        signed=signed,
        metrics=metrics,
        histogram_counts=histogram_counts.astype(np.int64, copy=False),
        histogram_edges=histogram_edges.astype(np.float64, copy=False),
    )


def _selected_values(
    values: NDArray[np.generic],
    bounds: tuple[int, int, int, int] | None,
    description: str,
) -> NDArray[np.generic]:
    if values.ndim not in (2, 3) or values.size == 0:
        raise ValueError(f"{description} must be a non-empty HxW or HxWxC array")
    if bounds is None:
        return values
    x, y, width, height = bounds
    if (
        x < 0
        or y < 0
        or width <= 0
        or height <= 0
        or x + width > values.shape[1]
        or y + height > values.shape[0]
    ):
        raise ValueError("metric ROI extends beyond the difference map")
    return values[y : y + height, x : x + width, ...]


def _iter_metric_chunks(
    values: NDArray[np.generic],
    chunk_elements: int,
) -> Iterator[NDArray[np.generic]]:
    if chunk_elements <= 0:
        raise ValueError("metric chunk size must be positive")
    iterator = np.nditer(
        values,
        flags=["external_loop", "buffered"],
        op_flags=[["readonly"]],
        order="K",
        buffersize=chunk_elements,
    )
    for chunk in iterator:
        yield np.asarray(chunk)


def _histogram_percentile(counts: NDArray[np.int64], percentile: float) -> float:
    sample_count = int(np.sum(counts, dtype=np.int64))
    if sample_count <= 0:
        raise ValueError("cannot calculate a percentile from an empty histogram")
    rank = (sample_count - 1) * percentile / 100.0
    lower_rank = floor(rank)
    upper_rank = ceil(rank)
    cumulative = np.cumsum(counts, dtype=np.int64)
    lower_value = int(np.searchsorted(cumulative, lower_rank, side="right"))
    upper_value = int(np.searchsorted(cumulative, upper_rank, side="right"))
    if lower_rank == upper_rank:
        return float(lower_value)
    fraction = rank - lower_rank
    return float(lower_value + (upper_value - lower_value) * fraction)


def _integer_absolute_metrics(
    selected: NDArray[np.generic],
    data_range: float,
    chunk_elements: int,
) -> DifferenceMetrics:
    histogram_bins = min(
        MAX_METRIC_HISTOGRAM_BINS,
        max(256, int(data_range) + 1),
    )
    counts = np.zeros(histogram_bins, dtype=np.int64)
    sample_count = 0
    absolute_sum = 0
    square_sum = 0
    nonzero_count = 0
    minimum = histogram_bins - 1
    maximum = 0

    for chunk in _iter_metric_chunks(selected, chunk_elements):
        if chunk.size == 0:
            continue
        chunk_minimum = int(np.asarray(np.min(chunk)).item())
        chunk_maximum = int(np.asarray(np.max(chunk)).item())
        if chunk_minimum < 0:
            raise ValueError("absolute difference values must be non-negative")
        if chunk_maximum >= histogram_bins:
            raise ValueError("native metric histogram supports absolute values through 65535")
        indexes = chunk.astype(np.intp, copy=False)
        chunk_counts = np.bincount(indexes, minlength=histogram_bins)
        counts += chunk_counts.astype(np.int64, copy=False)
        unsigned = chunk.astype(np.uint64, copy=False)
        sample_count += int(chunk.size)
        absolute_sum += int(np.sum(unsigned, dtype=np.uint64))
        square_sum += int(np.dot(unsigned, unsigned))
        nonzero_count += int(np.count_nonzero(chunk))
        minimum = min(minimum, chunk_minimum)
        maximum = max(maximum, chunk_maximum)

    if sample_count <= 0:
        raise ValueError("absolute difference must contain at least one sample")
    mae = absolute_sum / sample_count
    mse = square_sum / sample_count
    rmse = sqrt(mse)
    psnr = inf if mse == 0 else 20.0 * log10(data_range) - 10.0 * log10(mse)
    return DifferenceMetrics(
        mae=float(mae),
        mse=float(mse),
        rmse=float(rmse),
        psnr=float(psnr),
        p95=_histogram_percentile(counts, 95.0),
        p99=_histogram_percentile(counts, 99.0),
        maximum_absolute=float(maximum),
        nonzero_ratio=float(nonzero_count / sample_count),
        minimum_signed=float(minimum),
        maximum_signed=float(maximum),
        minimum_absolute=float(minimum),
    )


def _floating_absolute_metrics(
    selected: NDArray[np.generic],
    data_range: float,
    chunk_elements: int,
) -> DifferenceMetrics:
    counts = np.zeros(NORMALIZED_QUANTILE_LEVELS, dtype=np.int64)
    sample_count = 0
    absolute_sum = 0.0
    square_sum = 0.0
    nonzero_count = 0
    minimum = inf
    maximum = 0.0
    scale = (NORMALIZED_QUANTILE_LEVELS - 1) / data_range
    tolerance = max(1.0e-7, data_range * 1.0e-6)
    for chunk in _iter_metric_chunks(selected, chunk_elements):
        values = chunk.astype(np.float64, copy=False)
        if np.any(values < -tolerance):
            raise ValueError("absolute difference values must be non-negative")
        chunk_minimum = float(np.min(values))
        chunk_maximum = float(np.max(values))
        if chunk_maximum > data_range + tolerance:
            raise ValueError("absolute difference exceeds the declared data range")
        clipped = np.clip(values, 0.0, data_range)
        indexes = np.rint(clipped * scale).astype(np.intp, copy=False)
        chunk_counts = np.bincount(indexes, minlength=NORMALIZED_QUANTILE_LEVELS)
        counts += chunk_counts.astype(np.int64, copy=False)
        sample_count += int(values.size)
        absolute_sum += float(np.sum(values, dtype=np.float64))
        square_sum += float(np.dot(values, values))
        nonzero_count += int(np.count_nonzero(values))
        minimum = min(minimum, chunk_minimum)
        maximum = max(maximum, chunk_maximum)
    if sample_count <= 0:
        raise ValueError("absolute difference must contain at least one sample")
    mae = absolute_sum / sample_count
    mse = square_sum / sample_count
    rmse = sqrt(mse)
    psnr = inf if mse == 0 else 20.0 * log10(data_range) - 10.0 * log10(mse)
    p95 = _histogram_percentile(counts, 95.0) / scale
    p99 = _histogram_percentile(counts, 99.0) / scale
    return DifferenceMetrics(
        mae=float(mae),
        mse=float(mse),
        rmse=float(rmse),
        psnr=float(psnr),
        p95=float(p95),
        p99=float(p99),
        maximum_absolute=float(maximum),
        nonzero_ratio=float(nonzero_count / sample_count),
        minimum_signed=float(minimum),
        maximum_signed=float(maximum),
        minimum_absolute=float(minimum),
    )


def difference_metrics(
    signed: NDArray[np.generic],
    data_range: float,
    bounds: tuple[int, int, int, int] | None = None,
) -> DifferenceMetrics:
    """Summarize a signed full-resolution difference map over an optional ROI."""

    if data_range <= 0:
        raise ValueError("data_range must be positive")
    selected = _selected_values(signed, bounds, "signed difference")
    signed_minimum = float(np.asarray(np.min(selected)).item())
    signed_maximum = float(np.asarray(np.max(selected)).item())
    absolute = np.abs(selected)
    metrics = absolute_difference_metrics(absolute, data_range)
    return replace(
        metrics,
        minimum_signed=signed_minimum,
        maximum_signed=signed_maximum,
    )


def _validate_pair(a: NDArray[np.generic], b: NDArray[np.generic]) -> None:
    if a.shape != b.shape:
        raise ValueError(f"image shape mismatch: A{a.shape} != B{b.shape}")
    if a.size == 0:
        raise ValueError("images must not be empty")
    if not np.issubdtype(a.dtype, np.number) or not np.issubdtype(b.dtype, np.number):
        raise TypeError("difference operands must be numeric arrays")


def signed_difference(
    a: NDArray[np.generic], b: NDArray[np.generic]
) -> NDArray[np.int32] | NDArray[np.int64] | NDArray[np.float64]:
    """Calculate A-B after promotion, preventing integer wrap-around."""

    _validate_pair(a, b)
    if np.issubdtype(a.dtype, np.integer) and np.issubdtype(b.dtype, np.integer):
        if a.dtype.itemsize <= 2 and b.dtype.itemsize <= 2:
            compact_result: NDArray[np.int32] = np.subtract(a, b, dtype=np.int32)
            return compact_result
        integer_result: NDArray[np.int64] = np.subtract(a, b, dtype=np.int64)
        return integer_result
    float_result: NDArray[np.float64] = np.subtract(
        a.astype(np.float64),
        b.astype(np.float64),
    )
    return float_result


def absolute_difference(
    a: NDArray[np.generic], b: NDArray[np.generic]
) -> NDArray[np.int32] | NDArray[np.int64] | NDArray[np.float64]:
    """Return abs(A-B) based on the overflow-safe signed result."""

    signed = signed_difference(a, b)
    if signed.dtype == np.dtype(np.int32):
        compact_result: NDArray[np.int32] = np.abs(signed)
        return compact_result
    if signed.dtype == np.dtype(np.int64):
        integer_result: NDArray[np.int64] = np.abs(signed)
        return integer_result
    float_result: NDArray[np.float64] = np.abs(signed)
    return float_result


def compact_absolute_difference(
    a: NDArray[np.generic], b: NDArray[np.generic]
) -> NDArray[np.generic]:
    """Return exact absolute differences without retaining a promoted full-size map."""

    _validate_pair(a, b)
    if np.issubdtype(a.dtype, np.unsignedinteger) and np.issubdtype(
        b.dtype,
        np.unsignedinteger,
    ):
        itemsize = max(a.dtype.itemsize, b.dtype.itemsize)
        if itemsize <= 2:
            promoted = np.subtract(a, b, dtype=np.int32)
            np.abs(promoted, out=promoted)
            target = np.uint8 if itemsize == 1 else np.uint16
            return np.ascontiguousarray(promoted.astype(target))
        if itemsize <= 4:
            promoted64 = np.subtract(a, b, dtype=np.int64)
            np.abs(promoted64, out=promoted64)
            return np.ascontiguousarray(promoted64.astype(np.uint32))
    return np.ascontiguousarray(absolute_difference(a, b))


def absolute_difference_metrics(
    absolute: NDArray[np.generic],
    data_range: float,
    bounds: tuple[int, int, int, int] | None = None,
    *,
    chunk_elements: int = DEFAULT_METRIC_CHUNK_ELEMENTS,
) -> DifferenceMetrics:
    """Summarize an absolute map without full float64 or squared-map temporaries.

    Native integer maps use an exact histogram with at most 65,536 bins. Floating
    maps use a fixed 65,536-level histogram over the declared data range for P95/P99,
    so normalized-domain quantiles have deterministic error no greater than
    1/65535 full scale while mean/squared error remain chunk-accumulated.
    """

    if data_range <= 0:
        raise ValueError("data_range must be positive")
    selected = _selected_values(absolute, bounds, "absolute difference")
    if np.issubdtype(selected.dtype, np.integer):
        return _integer_absolute_metrics(selected, data_range, chunk_elements)
    return _floating_absolute_metrics(selected, data_range, chunk_elements)
