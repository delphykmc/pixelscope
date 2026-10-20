"""Optional, Qt-free quality-verdict presentation for supplied signed IQA values.

This module intentionally never reorients a value, modifies a mask, or supplies
an official/local measurement.  Only an adapter may declare quality direction
and the trustworthiness of the original-relative signal gate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from pixelscope_enterprise.iqa.analysis_model import (
    NEUTRAL_PRESENTATION_RGB,
    AttributeDisplay,
    apply_spatial_reference_tint_rgba,
)

SUPERIOR_RGB = (64, 143, 218)
INFERIOR_RGB = (224, 85, 90)
# One shared visible-neutral palette with request 4, distinct from muted gray.
NEUTRAL_RGB = NEUTRAL_PRESENTATION_RGB
MUTED_RGB = (211, 214, 219)
DEFAULT_VISIBILITY_THRESHOLD = 0.5
REFERENCE_TINT_MAX_ALPHA = 176


@dataclass(frozen=True)
class QualityPresentation:
    verdict: str
    tone: str
    rgb: tuple[int, int, int]
    opacity: float
    visible: bool


def verdict_for_value(
    attribute: AttributeDisplay,
    value: float | None,
    *,
    threshold: float = DEFAULT_VISIBILITY_THRESHOLD,
) -> QualityPresentation:
    """Classify an unchanged signed difference, with an inclusive dead zone."""

    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("visibility threshold must be finite and nonnegative")
    if (
        value is None
        or not np.isfinite(value)
        or abs(value) <= threshold
        or attribute.summary_signal_gate is not True
    ):
        return QualityPresentation("Not visible", "muted", MUTED_RGB, 0.32, False)
    if attribute.quality_direction == "none":
        return QualityPresentation("No quality direction", "neutral", NEUTRAL_RGB, 0.85, True)
    is_superior = (value > 0) == (attribute.quality_direction == "higher_is_better")
    if is_superior:
        return QualityPresentation("Superior", "superior", SUPERIOR_RGB, 1.0, True)
    return QualityPresentation("Inferior", "inferior", INFERIOR_RGB, 1.0, True)


def quality_spatial_rgba(
    attribute: AttributeDisplay,
    half_range: float,
    *,
    threshold: float = DEFAULT_VISIBILITY_THRESHOLD,
    translucent: bool = False,
) -> NDArray[np.uint8] | None:
    """Render verdict colors on the bounded grid, preserving invalid alpha=0.

    The visibility gate is metadata about source-signal trust, never inferred
    from the signed difference itself.  No per-cell value or mask is rewritten.
    For request 1's reference underlay, ``translucent=True`` applies exactly
    one shared alpha attenuation to this base renderer. Never multiply the
    magnitude or quality opacity twice, and keep zero/invalid cells clear.
    """

    grid = attribute.spatial
    if grid is None:
        return None
    if not np.isfinite(half_range) or half_range <= 0:
        raise ValueError("display half-range must be positive and finite")
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("visibility threshold must be finite and nonnegative")

    values = np.where(grid.valid_mask, grid.values, 0.0)
    magnitude = np.clip(np.abs(values) / half_range, 0.0, 1.0)
    eligible = (np.abs(values) > threshold) & (attribute.summary_signal_gate is True)
    rgba = np.empty((*values.shape, 4), dtype=np.uint8)
    # One channel at a time prevents wide float64 RGB temporaries at the
    # maximum supported 4-million-cell grid size.
    if attribute.quality_direction == "none":
        superior = None
    else:
        superior = (
            (values > 0) if attribute.quality_direction == "higher_is_better" else (values < 0)
        )
    for channel in range(3):
        if superior is None:
            colored = np.rint(239.0 + magnitude * (NEUTRAL_RGB[channel] - 239.0)).astype(np.uint8)
        else:
            endpoints = np.where(superior, SUPERIOR_RGB[channel], INFERIOR_RGB[channel])
            colored = np.rint(239.0 + magnitude * (endpoints - 239.0)).astype(np.uint8)
        rgba[..., channel] = np.where(eligible, colored, MUTED_RGB[channel])
    rgba[..., 3] = np.where(
        grid.valid_mask,
        np.where(eligible, 217 if attribute.quality_direction == "none" else 255, 82),
        0,
    ).astype(np.uint8)
    if translucent:
        # The request-1 helper attenuates *this* selected color/alpha once.
        return apply_spatial_reference_tint_rgba(
            attribute, half_range, rgba, max_alpha=REFERENCE_TINT_MAX_ALPHA
        )
    return np.ascontiguousarray(rgba)


def quality_map_legend(threshold: float = DEFAULT_VISIBILITY_THRESHOLD) -> str:
    return (
        "Blue: Superior | Red: Inferior | Gray: No quality direction | "
        f"Faint gray: |Δ| ≤ {threshold:g} or signal gate not trusted"
    )
