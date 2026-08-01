from __future__ import annotations

from dataclasses import dataclass
from math import inf, log10
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.image_document import ImageDocument


@dataclass(frozen=True)
class DifferenceMetrics:
    mae: float
    mse: float
    psnr: float
    minimum_signed: float
    maximum_signed: float
    minimum_absolute: float
    maximum_absolute: float


@dataclass(frozen=True)
class DifferenceAnalysisResult:
    numerical: NDArray[np.generic]
    signed: NDArray[np.float64]
    metrics: DifferenceMetrics
    histogram_counts: NDArray[np.int64]
    histogram_edges: NDArray[np.float64]


def _layout_family(document: ImageDocument) -> str:
    if document.channel_layout == "BAYER":
        return "BAYER"
    if document.channel_layout in ("RGB", "RGBA"):
        return "RGB"
    return document.channel_layout


def validate_difference_documents(
    a: ImageDocument,
    b: ImageDocument,
    normalized_domain: bool = False,
) -> str | None:
    """Return a user-facing incompatibility reason, or None for a valid pair."""

    if a.source is None or b.source is None:
        return "Both images must be loaded before comparison."
    if a.shape[:2] != b.shape[:2]:
        return "Image dimensions do not match."
    family_a, family_b = _layout_family(a), _layout_family(b)
    if family_a not in {"RGB", "BAYER"} or family_b not in {"RGB", "BAYER"}:
        return (
            "Difference supports RGB/RGBA or Bayer images; "
            f"received {a.channel_layout} and {b.channel_layout}."
        )
    if {family_a, family_b} == {"RGB", "BAYER"}:
        return "RGB and Bayer images cannot be compared directly."
    if family_a != family_b:
        return f"Incompatible channel layouts: {a.channel_layout} vs {b.channel_layout}."
    if family_a == "BAYER":
        pattern_a = getattr(a.raw_profile, "bayer_pattern", None)
        pattern_b = getattr(b.raw_profile, "bayer_pattern", None)
        if pattern_a != pattern_b:
            return f"Bayer patterns are different: {pattern_a} vs {pattern_b}."
    if a.bit_depth != b.bit_depth and not normalized_domain:
        return "Native-domain difference requires matching bit depths."
    return None


def _normalized_source(
    source: NDArray[np.generic],
    bit_depth: int,
) -> NDArray[np.float64]:
    maximum = float((1 << bit_depth) - 1)
    if maximum <= 0:
        raise ValueError("bit depth must be positive")
    return source.astype(np.float64) / maximum


def analyze_difference(
    a: NDArray[np.generic],
    b: NDArray[np.generic],
    *,
    mode: Literal["absolute", "signed", "threshold"] = "absolute",
    domain: Literal["native", "normalized"] = "native",
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
        working_a = _normalized_source(a, bit_depth_a)
        working_b = _normalized_source(b, bit_depth_b)
        signed = working_a - working_b
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
    metrics = difference_metrics(signed, peak)
    histogram_counts, histogram_edges = np.histogram(numerical, bins=bins)
    return DifferenceAnalysisResult(
        numerical=numerical,
        signed=signed,
        metrics=metrics,
        histogram_counts=histogram_counts.astype(np.int64, copy=False),
        histogram_edges=histogram_edges.astype(np.float64, copy=False),
    )


def difference_metrics(
    signed: NDArray[np.generic],
    data_range: float,
    bounds: tuple[int, int, int, int] | None = None,
) -> DifferenceMetrics:
    """Summarize a signed full-resolution difference map over an optional ROI."""

    if signed.ndim not in (2, 3) or signed.size == 0:
        raise ValueError("signed difference must be a non-empty HxW or HxWxC array")
    if data_range <= 0:
        raise ValueError("data_range must be positive")
    selected = signed
    if bounds is not None:
        x, y, width, height = bounds
        if (
            x < 0
            or y < 0
            or width <= 0
            or height <= 0
            or x + width > signed.shape[1]
            or y + height > signed.shape[0]
        ):
            raise ValueError("metric ROI extends beyond the difference map")
        selected = signed[y : y + height, x : x + width, ...]
    values = selected.astype(np.float64, copy=False)
    absolute = np.abs(values)
    mse = float(np.mean(np.square(values)))
    psnr = inf if mse == 0 else 20.0 * log10(data_range) - 10.0 * log10(mse)
    return DifferenceMetrics(
        mae=float(np.mean(absolute)),
        mse=mse,
        psnr=psnr,
        minimum_signed=float(np.min(values)),
        maximum_signed=float(np.max(values)),
        minimum_absolute=float(np.min(absolute)),
        maximum_absolute=float(np.max(absolute)),
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
    float_result: NDArray[np.float64] = np.subtract(a.astype(np.float64), b.astype(np.float64))
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
    if np.issubdtype(a.dtype, np.unsignedinteger) and np.issubdtype(b.dtype, np.unsignedinteger):
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
) -> DifferenceMetrics:
    """Summarize an absolute map over an optional ROI without a signed copy."""

    if absolute.ndim not in (2, 3) or absolute.size == 0:
        raise ValueError("absolute difference must be a non-empty HxW or HxWxC array")
    if data_range <= 0:
        raise ValueError("data_range must be positive")
    selected = absolute
    if bounds is not None:
        x, y, width, height = bounds
        if (
            x < 0
            or y < 0
            or width <= 0
            or height <= 0
            or x + width > absolute.shape[1]
            or y + height > absolute.shape[0]
        ):
            raise ValueError("metric ROI extends beyond the difference map")
        selected = absolute[y : y + height, x : x + width, ...]
    values = selected.astype(np.float64, copy=False)
    mse = float(np.mean(np.square(values)))
    psnr = inf if mse == 0 else 20.0 * log10(data_range) - 10.0 * log10(mse)
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    return DifferenceMetrics(
        mae=float(np.mean(values)),
        mse=mse,
        psnr=psnr,
        minimum_signed=minimum,
        maximum_signed=maximum,
        minimum_absolute=minimum,
        maximum_absolute=maximum,
    )
