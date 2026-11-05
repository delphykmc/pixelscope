"""W07: Pure typed Pivot tests. No Qt, source loading or worker is required."""
from __future__ import annotations

from dataclasses import replace
from math import inf, nan
from uuid import UUID

import pytest

from pixelscope.core.metric_presentation import (
    FOCUSED_METRICS,
    STATISTICS_METRICS,
    build_statistics_pivot,
    format_metric_number,
    metric_definition,
)
from pixelscope.core.review_analysis import (
    AnalysisSourceV1,
    PresentedAnalysisTokenV1,
    measurement,
)
from pixelscope.core.review_analysis_native import AnalysisNativeInterpretationV1


def _key(index: int) -> str:
    return str(UUID(int=index + 1))


def _fixture(
    n: int = 4,
    *,
    layout: str = "RGB",
    channel: str = "R",
    roi: tuple[int, int, int, int] | None = None,
    native_dtype: str = "uint16",
    bits: int = 10,
) -> tuple[PresentedAnalysisTokenV1, tuple[AnalysisSourceV1, ...], tuple]:
    keys = tuple(_key(i) for i in range(n))
    interpretation = (
        AnalysisNativeInterpretationV1(cfa_pattern="RGGB", cfa_phase_xy=(0, 0))
        if layout == "BAYER"
        else AnalysisNativeInterpretationV1(
            yuv_layout=layout,
            yuv_chroma_step_xy=(2, 2) if layout == "YUV420" else (2, 1),
            yuv_plane_shapes=(
                ((8, 8), (4, 4), (4, 4)) if layout == "YUV420" else ((8, 8), (8, 4), (8, 4))
            ),
        )
        if layout in ("YUV420", "YUV422")
        else AnalysisNativeInterpretationV1()
    )
    sources = tuple(
        AnalysisSourceV1(
            source_key=key,
            document_id=f"runtime-{index}",
            generation=2,
            native_shape=(8, 8, 3) if layout == "RGB" else (8, 8),
            reference_shape=(8, 8),
            native_dtype=native_dtype,
            channel_layout=layout,
            effective_bits=bits,
            profile_signature="a" * 64,
            native_interpretation=interpretation,
        )
        for index, key in enumerate(keys)
    )
    token = PresentedAnalysisTokenV1(
        feature="statistics",
        request_id="native-run",
        request_epoch=8,
        source_documents=tuple((source.document_id, source.generation) for source in sources),
        source_keys=keys,
        roi_ref=roi,
        channel="All",
        domain="native",
        profile_signatures=tuple(source.profile_signature for source in sources),
        difference_cache_key=None,
    )
    values = tuple(
        measurement(key, channel, metric, float(index) + offset, 64)
        for index, key in enumerate(keys)
        for metric, offset in (("Mean", 20.000000001), ("Std", 3.5), ("P99", 80.0))
    )
    return token, sources, values


@pytest.mark.parametrize("count", (2, 4, 6))
def test_ordered_pivot_channels_metrics_identity_and_duplicate_aliases(count: int) -> None:
    token, sources, values = _fixture(count)
    aliases = {key: "동일 파일.png" for key in token.source_keys}
    pivot = build_statistics_pivot(token, sources, values, aliases, metrics=FOCUSED_METRICS)
    assert [col.source_key for col in pivot.columns] == list(token.source_keys)
    assert [col.alias for col in pivot.columns] == ["동일 파일.png"] * count
    assert [(row.metric, row.channel) for row in pivot.rows] == [
        ("Mean", "R"),
        ("Std", "R"),
        ("P99", "R"),
    ]
    assert pivot.rows[0].cells[-1].value == pytest.approx(20.000000001 + count - 1)
    # Same labels never act as the source identity; source reordering is explicit.
    reordered_sources = tuple(reversed(sources))
    reordered_token = replace(
        token,
        source_documents=tuple(reversed(token.source_documents)),
        source_keys=tuple(reversed(token.source_keys)),
        profile_signatures=tuple(reversed(token.profile_signatures)),
    )
    reordered = build_statistics_pivot(
        reordered_token, reordered_sources, values, aliases, metrics=FOCUSED_METRICS
    )
    assert [col.source_key for col in reordered.columns] == list(reordered_token.source_keys)
    assert reordered.rows[0].cells[0].value == pivot.rows[0].cells[-1].value


def test_delta_uses_unrounded_native_float_and_explicit_reference() -> None:
    token, sources, values = _fixture(2)
    values = (
        measurement(token.source_keys[0], "R", "Mean", 0.123456789123, 64),
        measurement(token.source_keys[1], "R", "Mean", 0.123456789987, 64),
    )
    pivot = build_statistics_pivot(
        token, sources, values, {}, metrics=("Mean",), reference_key=token.source_keys[0]
    )
    ref, target = pivot.rows[0].cells
    assert ref.absolute_delta == 0.0
    assert target.absolute_delta == values[1].value - values[0].value
    assert target.absolute_delta != 0.0
    assert ref.formatted_value() == target.formatted_value()
    assert target.formatted_value(precision=17) != ref.formatted_value(precision=17)
    assert target.relative_delta_percent == pytest.approx(
        (values[1].value - values[0].value) / abs(values[0].value) * 100.0
    )
    without_reference = build_statistics_pivot(token, sources, values, {}, metrics=("Mean",))
    assert all(cell.absolute_delta is None for cell in without_reference.rows[0].cells)


def test_reference_zero_preserves_absolute_delta_but_rejects_relative() -> None:
    token, sources, _values = _fixture(2)
    values = (
        measurement(token.source_keys[0], "R", "Mean", 0, 64),
        measurement(token.source_keys[1], "R", "Mean", 17, 64),
    )
    cells = (
        build_statistics_pivot(
            token, sources, values, {}, metrics=("Mean",), reference_key=token.source_keys[0]
        )
        .rows[0]
        .cells
    )
    assert cells[1].absolute_delta == 17.0
    assert cells[1].relative_delta_percent is None
    assert "zero" in (cells[1].delta_reason or "")


@pytest.mark.parametrize(
    "alter,expected",
    (
        ({"native_dtype": "uint8"}, "dtype"),
        ({"effective_bits": 12}, "bit"),
        ({"channel_layout": "Gray", "native_shape": (8, 8)}, "layout"),
        ({"reference_shape": (10, 10)}, "bounds"),
    ),
)
def test_native_delta_mismatch_fails_closed(alter: dict, expected: str) -> None:
    token, sources, values = _fixture(2)
    changed = (sources[0], replace(sources[1], **alter))
    cell = (
        build_statistics_pivot(
            token, changed, values, {}, metrics=("Mean",), reference_key=token.source_keys[0]
        )
        .rows[0]
        .cells[1]
    )
    assert cell.absolute_delta is None
    assert expected.lower() in (cell.delta_reason or "").lower()


def test_roi_token_preserved_and_full_bounds_guard_only_for_full_scope() -> None:
    token, sources, values = _fixture(2, roi=(1, 1, 4, 4))
    different_shape = (sources[0], replace(sources[1], reference_shape=(10, 10)))
    pivot = build_statistics_pivot(
        token, different_shape, values, {}, metrics=("Mean",), reference_key=token.source_keys[0]
    )
    assert pivot.token.roi_ref == (1, 1, 4, 4)
    assert pivot.rows[0].cells[1].absolute_delta == 1.0
    assert token.roi_ref == (1, 1, 4, 4)


def test_sample_count_channel_and_revision_are_comparability_gates() -> None:
    token, sources, _values = _fixture(2)
    a, b = token.source_keys
    values = (
        measurement(a, "R", "Mean", 7, 12),
        measurement(b, "R", "Mean", 9, 18),
        measurement(a, "G", "Mean", 11, 12),
        measurement(b, "G", "Mean", 13, 12, "other-v1"),
    )
    pivot = build_statistics_pivot(token, sources, values, {}, metrics=("Mean",), reference_key=a)
    red, green = pivot.rows
    assert red.cells[1].absolute_delta is None
    assert "sample counts" in (red.cells[1].delta_reason or "")
    assert green.cells[1].absolute_delta is None
    assert "definition" in (green.cells[1].delta_reason or "")
    assert (
        len(build_statistics_pivot(token, sources, values, {}, channel="G", metrics=("Mean",)).rows)
        == 1
    )


def test_bayer_cfa_and_yuv_chroma_footprint_are_not_interchangeable() -> None:
    token, sources, values = _fixture(2, layout="BAYER", channel="Gr")
    rggb = AnalysisNativeInterpretationV1(cfa_pattern="RGGB", cfa_phase_xy=(0, 0))
    bggr = AnalysisNativeInterpretationV1(cfa_pattern="BGGR", cfa_phase_xy=(0, 0))
    source_a = replace(sources[0], native_interpretation=rggb)
    source_b = replace(sources[1], native_interpretation=bggr)
    pivot = build_statistics_pivot(
        token,
        (source_a, source_b),
        values,
        {},
        metrics=("Mean",),
        reference_key=token.source_keys[0],
    )
    assert pivot.rows[0].cells[1].absolute_delta is None
    assert "CFA phase" in (pivot.rows[0].cells[1].delta_reason or "")

    token, sources, values = _fixture(2, layout="YUV420", channel="U")
    native = AnalysisNativeInterpretationV1(
        yuv_layout="YUV420",
        yuv_chroma_step_xy=(2, 2),
        yuv_plane_shapes=((8, 8), (4, 4), (4, 4)),
    )
    yuv_sources = tuple(replace(source, native_interpretation=native) for source in sources)
    compatible = build_statistics_pivot(
        token, yuv_sources, values, {}, metrics=("Mean",), reference_key=token.source_keys[0]
    )
    assert compatible.rows[0].cells[1].absolute_delta == 1.0
    # A different native footprint is not a valid code-domain comparison.
    changed = replace(
        yuv_sources[1],
        native_interpretation=AnalysisNativeInterpretationV1(
            yuv_layout="YUV422",
            yuv_chroma_step_xy=(2, 1),
            yuv_plane_shapes=((8, 8), (8, 4), (8, 4)),
        ),
        channel_layout="YUV422",
    )
    mismatched = build_statistics_pivot(
        token,
        (yuv_sources[0], changed),
        values,
        {},
        metrics=("Mean",),
        reference_key=token.source_keys[0],
    )
    assert mismatched.rows[0].cells[1].absolute_delta is None


@pytest.mark.parametrize(
    "input_value,state,text",
    (
        (nan, "nan", "NaN"),
        (inf, "pos_inf", "+Inf"),
        (-inf, "neg_inf", "-Inf"),
        (None, "unavailable", "N/A"),
    ),
)
def test_nonfinite_native_measurements_keep_explicit_state(
    input_value: float | None, state: str, text: str
) -> None:
    token, sources, _ = _fixture(2)
    data = (
        measurement(token.source_keys[0], "R", "Mean", 5, 64),
        measurement(token.source_keys[1], "R", "Mean", input_value, 64),
    )
    cell = (
        build_statistics_pivot(
            token, sources, data, {}, metrics=("Mean",), reference_key=token.source_keys[0]
        )
        .rows[0]
        .cells[1]
    )
    assert cell.state == state
    assert cell.formatted_value() == text
    assert cell.absolute_delta is None


def test_typed_unit_catalog_precision_and_validation() -> None:
    assert metric_definition("Mean").unit == "native code"
    assert metric_definition("PSNR").unit == "dB"
    assert not metric_definition("PSNR").delta_allowed
    assert metric_definition("MSE").unit == "native code²"
    assert metric_definition("Non-zero ratio").unit == "ratio [0,1]"
    assert metric_definition("MAE", domain="normalized").unit == "normalized [0,1]"
    assert metric_definition("MSE", domain="normalized").unit == "normalized²"
    assert metric_definition("PSNR", domain="normalized").unit == "dB"
    with pytest.raises(ValueError, match="domain"):
        metric_definition("Mean", domain="unknown")
    assert format_metric_number(0.123456789987, "finite", precision=6) == "0.123457"
    assert format_metric_number(0.123456789987, "finite", precision=17) == "0.123456789987"
    assert format_metric_number(None, "unavailable") == "N/A"
    with pytest.raises(ValueError):
        format_metric_number(1.0, "finite", precision=18)


def test_reject_stale_generation_profile_and_duplicate_measurement() -> None:
    token, sources, values = _fixture(2)
    for kwargs in (
        {"sources": (sources[0], replace(sources[1], generation=3))},
        {"sources": (sources[0], replace(sources[1], profile_signature="b" * 64))},
        {"sources": tuple(reversed(sources))},
    ):
        with pytest.raises(ValueError):
            build_statistics_pivot(token, kwargs["sources"], values, {}, metrics=FOCUSED_METRICS)
    with pytest.raises(ValueError):
        build_statistics_pivot(token, sources, values, {}, reference_key=_key(99))
    with pytest.raises(ValueError):
        build_statistics_pivot(token, sources, values, {}, metrics=("unknown",))
    with pytest.raises(ValueError):
        build_statistics_pivot(token, sources, (*values, values[0]), {}, metrics=STATISTICS_METRICS)
