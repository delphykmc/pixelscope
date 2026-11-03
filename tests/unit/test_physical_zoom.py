from __future__ import annotations

from math import nan

import pytest

from pixelscope.ui.physical_zoom import measure_basis


@pytest.mark.parametrize("dpr", [1.0, 1.25, 1.5, 1.75, 2.0, 4.0])
@pytest.mark.parametrize("physical_scale", [1.0, 2.0, 4.0])
def test_basis_reports_physical_scale_at_fractional_dpr(
    dpr: float, physical_scale: float
) -> None:
    logical_step = physical_scale / dpr
    measurement = measure_basis(
        (14.25, -10.5),
        (14.25 + logical_step, -10.5),
        (14.25, -10.5 + logical_step),
        dpr,
    )
    assert measurement.valid
    assert measurement.scale_x == pytest.approx(physical_scale)
    assert measurement.scale_y == pytest.approx(physical_scale)
    assert measurement.percent == pytest.approx(physical_scale * 100)


@pytest.mark.parametrize(
    ("x_step", "y_step"),
    [
        ((-1.0, 0.0), (0.0, 1.0)),  # horizontal mirror
        ((1.0, 0.0), (0.0, -1.0)),  # vertical mirror
        ((0.0, 1.0), (-1.0, 0.0)),  # 90-degree rotation
        ((1.0, 0.2), (0.0, 1.0)),  # shear
        ((1.0, 0.0), (0.0, 1.05)),  # anisotropic scales
        ((0.0, 0.0), (0.0, 1.0)),  # degenerate mapping
    ],
)
def test_distorted_or_mirrored_basis_has_no_single_zoom_label(
    x_step: tuple[float, float], y_step: tuple[float, float]
) -> None:
    measurement = measure_basis((0.0, 0.0), x_step, y_step, 1.0)
    assert measurement.percent is None
    assert not measurement.valid


@pytest.mark.parametrize("dpr", [0.0, -1.0, nan])
def test_invalid_dpr_is_unavailable(dpr: float) -> None:
    measurement = measure_basis((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), dpr)
    assert not measurement.valid
    assert measurement.percent is None
