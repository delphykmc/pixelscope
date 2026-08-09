from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class DisplayTransform:
    """Non-destructive source-to-display conversion parameters.

    ``display_low``/``display_high`` describe the code range mapped to the
    preview endpoints. ``gain`` is presentation-only and is applied around
    ``gain_anchor`` before the final range mapping. The gain model is generic:

    ``display = anchor + gain * (source - anchor)``

    RAW chooses its anchor from Black Level metadata. Ordinary Gray/RGB use a
    zero anchor. None of these parameters redefine the source or analysis domain.
    """

    display_low: float | None = None
    display_high: float | None = None
    gain: float = 1.0
    gain_anchor: float = 0.0
    gamma: float = 1.0

    def __post_init__(self) -> None:
        if self.gain <= 0:
            raise ValueError("gain must be greater than zero")
        if self.gamma <= 0:
            raise ValueError("gamma must be greater than zero")
        if (
            self.display_low is not None
            and self.display_high is not None
            and self.display_high <= self.display_low
        ):
            raise ValueError("display_high must be greater than display_low")


def display_gain_affine(gain: float, anchor: float = 0.0) -> tuple[np.float32, np.float32]:
    """Return float32 ``scale, offset`` for anchor-based display gain.

    The returned values satisfy ``gained = source * scale + offset`` and are
    algebraically identical to ``anchor + gain * (source - anchor)``.
    """

    if gain <= 0:
        raise ValueError("display gain must be greater than zero")
    gain32 = np.float32(gain)
    anchor32 = np.float32(anchor)
    offset = np.float32(anchor32 * np.float32(np.float32(1.0) - gain32))
    return gain32, offset


def display_normalization_affine(
    display_low: float,
    display_high: float,
    gain: float = 1.0,
    anchor: float = 0.0,
) -> tuple[np.float32, np.float32]:
    """Return a fused float32 affine from source codes to normalized display.

    Gain and display-range normalization are combined so callers need only one
    multiply and, when required, one add over the target samples before clipping.
    """

    low32 = np.float32(display_low)
    high32 = np.float32(display_high)
    span = np.float32(high32 - low32)
    if span <= 0:
        raise ValueError("display_high must be greater than display_low")
    gain_scale, gain_offset = display_gain_affine(gain, anchor)
    inverse_span = np.float32(np.float32(1.0) / span)
    scale = np.float32(gain_scale * inverse_span)
    offset = np.float32((gain_offset - low32) * inverse_span)
    return scale, offset


def apply_display_affine_inplace(
    values: NDArray[np.float32],
    scale: np.float32,
    offset: np.float32,
) -> None:
    """Apply one float32 display affine to an array or array view in place."""

    np.multiply(values, scale, out=values)
    if offset != np.float32(0.0):
        np.add(values, offset, out=values)


def apply_display_gain_inplace(
    values: NDArray[np.float32],
    gain: float,
    anchor: float = 0.0,
) -> None:
    """Apply generic anchor-based display gain to float32 values in place."""

    scale, offset = display_gain_affine(gain, anchor)
    apply_display_affine_inplace(values, scale, offset)


def _default_range(array: NDArray[np.generic]) -> tuple[float, float]:
    if np.issubdtype(array.dtype, np.integer):
        bits = array.dtype.itemsize * 8
        if np.issubdtype(array.dtype, np.unsignedinteger):
            return 0.0, float((1 << bits) - 1)
        return float(-(1 << (bits - 1))), float((1 << (bits - 1)) - 1)
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return 0.0, 1.0
    low, high = float(finite.min()), float(finite.max())
    return (low, high) if high > low else (low, low + 1.0)


def resolve_display_range(
    source: NDArray[np.generic], transform: DisplayTransform | None = None
) -> tuple[float, float]:
    """Resolve the canonical display range without changing source data."""

    parameters = transform or DisplayTransform()
    default_low, default_high = _default_range(source)
    low = default_low if parameters.display_low is None else parameters.display_low
    high = default_high if parameters.display_high is None else parameters.display_high
    if high <= low:
        high = low + 1.0
    return float(low), float(high)


def to_display_uint8(
    source: NDArray[np.generic], transform: DisplayTransform | None = None
) -> NDArray[np.uint8]:
    """Return a C-contiguous uint8 preview without modifying *source*.

    Source values are promoted once to float32. Anchor-based gain and display
    normalization are fused into one scale/offset affine, avoiding serial
    full-frame subtract/multiply/add/normalize temporaries. Clipping is deferred
    until final display conversion.
    """

    if source.size == 0:
        raise ValueError("cannot display an empty image")
    parameters = transform or DisplayTransform()
    low, high = resolve_display_range(source, parameters)

    working = source.astype(np.float32, copy=True)
    scale, offset = display_normalization_affine(
        low,
        high,
        parameters.gain,
        parameters.gain_anchor,
    )
    apply_display_affine_inplace(working, scale, offset)
    np.clip(working, 0.0, 1.0, out=working)
    if parameters.gamma != 1.0:
        np.power(working, np.float32(1.0 / parameters.gamma), out=working)
    np.multiply(working, np.float32(255.0), out=working)
    np.rint(working, out=working)
    return np.ascontiguousarray(working.astype(np.uint8))


def render_ordinary_display_preview(
    source: NDArray[np.generic],
    *,
    channel_layout: str,
    transform: DisplayTransform,
    canonical_preview: NDArray[np.uint8],
    gain: float,
) -> NDArray[np.uint8]:
    """Render viewer-only Display Gain for non-RAW Gray/RGB/RGBA presentations.

    Ordinary sources use a zero anchor. RGBA processes only the RGB source view
    and copies alpha from the canonical 1× preview, avoiding a four-channel
    float32 gain working buffer. Transient RGB split-channel documents keep their
    existing colored-tile presentation while their native 2-D source stays
    authoritative for analysis.
    """

    if gain <= 0:
        raise ValueError("display gain must be greater than zero")
    if gain == 1.0:
        return canonical_preview

    layout = channel_layout.upper()
    if layout == "DIFFERENCE":
        raise ValueError("Difference presentation owns its own display gain")

    low, high = resolve_display_range(source, transform)
    gained_transform = DisplayTransform(
        display_low=low,
        display_high=high,
        gain=gain,
        gain_anchor=0.0,
        gamma=transform.gamma,
    )

    if layout == "RGBA":
        if source.ndim != 3 or source.shape[2] != 4:
            raise ValueError("RGBA Display Gain requires a four-channel source")
        if canonical_preview.ndim != 3 or canonical_preview.shape[2] != 4:
            raise ValueError("RGBA Display Gain requires a four-channel canonical preview")
        rgb_preview = to_display_uint8(source[..., :3], gained_transform)
        result = np.empty(canonical_preview.shape, dtype=np.uint8)
        result[..., :3] = rgb_preview
        result[..., 3] = canonical_preview[..., 3]
        return np.ascontiguousarray(result)

    if layout in {"CHANNEL_R", "CHANNEL_G", "CHANNEL_B"}:
        if source.ndim != 2:
            raise ValueError("split-channel Display Gain requires a 2-D source")
        channel_preview = to_display_uint8(source, gained_transform)
        result = np.zeros((*source.shape, 3), dtype=np.uint8)
        channel_index = {"CHANNEL_R": 0, "CHANNEL_G": 1, "CHANNEL_B": 2}[layout]
        result[..., channel_index] = channel_preview
        return result

    if layout not in {"GRAY", "RGB"}:
        raise ValueError(f"unsupported ordinary Display Gain layout: {channel_layout}")
    return to_display_uint8(source, gained_transform)


def render_signed_difference(diff: NDArray[Any]) -> NDArray[np.uint8]:
    """Render signed values as blue-negative, gray-zero, red-positive RGB."""

    if diff.size == 0:
        raise ValueError("cannot display an empty difference")
    display_values = diff.astype(np.float32)
    if display_values.ndim == 3:
        display_values = np.mean(display_values, axis=-1)
    maximum = max(float(np.max(np.abs(display_values.astype(np.float64)))), 1.0)
    normalized = np.clip(display_values / maximum, -1.0, 1.0)
    base = 127.0
    red = base + np.maximum(normalized, 0.0) * 128.0
    blue = base + np.maximum(-normalized, 0.0) * 128.0
    green = base - np.abs(normalized) * 127.0
    rgb = np.stack((red, green, blue), axis=-1)
    return np.ascontiguousarray(np.clip(rgb, 0, 255).astype(np.uint8))


def render_absolute_difference(diff: NDArray[Any], gain: float = 1.0) -> NDArray[np.uint8]:
    """Render absolute numerical difference with an independent display gain."""

    if gain <= 0:
        raise ValueError("display gain must be greater than zero")
    maximum = max(float(np.max(diff)), 1.0)
    scaled = np.clip(diff.astype(np.float32) * gain / maximum, 0.0, 1.0)
    return np.ascontiguousarray(np.rint(scaled * 255.0).astype(np.uint8))


def render_absolute_difference_range(
    diff: NDArray[Any], low: int, high: int, gain: int = 1
) -> NDArray[np.uint8]:
    """Render an absolute map using an explicit integer display range."""

    if high <= low:
        raise ValueError("high must be greater than low")
    if gain <= 0:
        raise ValueError("display gain must be greater than zero")
    scaled = np.clip(
        (diff.astype(np.float32) - np.float32(low)) * np.float32(gain / (high - low)),
        0.0,
        1.0,
    )
    return np.ascontiguousarray(np.rint(scaled * 255.0).astype(np.uint8))


def render_threshold_mask(diff: NDArray[Any], threshold: float) -> NDArray[np.uint8]:
    """Render red where any selected channel exceeds *threshold*, black elsewhere."""

    if threshold < 0:
        raise ValueError("threshold must be non-negative")
    selected = np.greater(diff, threshold)
    mask = np.any(selected, axis=2) if selected.ndim == 3 else selected
    preview = np.zeros((*mask.shape, 3), dtype=np.uint8)
    preview[mask, 0] = 255
    return preview
