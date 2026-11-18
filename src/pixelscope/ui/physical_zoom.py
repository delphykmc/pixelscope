"""Qt-free reference-to-physical-pixel basis and zoom accuracy helpers.

The UI supplies *actual displayed* ImageItem basis points in viewport logical
coordinates. This module neither assumes square ImageItem samples nor replaces
native SpatialSampling/reference geometry authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite


@dataclass(frozen=True)
class PhysicalZoomMeasurement:
    """Measured physical pixels per reference pixel along each image basis."""

    scale_x: float = 0.0
    scale_y: float = 0.0
    dpr: float = 0.0
    valid: bool = False
    axis_aligned: bool = False

    @property
    def percent(self) -> float | None:
        """Common physical zoom; None for an invalid or distorted mapping."""
        return 100.0 * self.scale_x if self.valid else None


@dataclass(frozen=True)
class ZoomApplyResult:
    target_percent: float
    measurement: PhysicalZoomMeasurement
    achieved: bool
    passes: int


def measure_basis(
    origin: tuple[float, float],
    x_step: tuple[float, float],
    y_step: tuple[float, float],
    dpr: float,
    *,
    tolerance: float = 0.005,
) -> PhysicalZoomMeasurement:
    """Measure a composed Qt mapping without rounding to integer viewport pixels.

    A scale label is meaningful only for a positive, axis-aligned, approximately
    isotropic transform. Mirroring, rotation and shear invalidate a single
    percentage even when the two basis-vector norms happen to match.
    """
    values = (*origin, *x_step, *y_step, dpr, tolerance)
    if not all(isfinite(v) for v in values) or dpr <= 0 or tolerance < 0:
        return PhysicalZoomMeasurement(dpr=dpr)
    dx = ((x_step[0] - origin[0]) * dpr, (x_step[1] - origin[1]) * dpr)
    dy = ((y_step[0] - origin[0]) * dpr, (y_step[1] - origin[1]) * dpr)
    sx, sy = hypot(*dx), hypot(*dy)
    if sx <= 0 or sy <= 0:
        return PhysicalZoomMeasurement(scale_x=sx, scale_y=sy, dpr=dpr)
    aligned = (
        dx[0] > 0 and dy[1] > 0 and abs(dx[1]) <= tolerance * sx and abs(dy[0]) <= tolerance * sy
    )
    uniform = abs(sx - sy) <= tolerance * max(sx, sy)
    return PhysicalZoomMeasurement(
        scale_x=sx,
        scale_y=sy,
        dpr=dpr,
        valid=aligned and uniform,
        axis_aligned=aligned,
    )
