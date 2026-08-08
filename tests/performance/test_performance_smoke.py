from __future__ import annotations

from pathlib import Path
from time import perf_counter

import numpy as np

from pixelscope.core.bayer import analyze_bayer_roi
from pixelscope.core.diff_engine import (
    absolute_difference_metrics,
    compact_absolute_difference,
    signed_difference,
)
from pixelscope.core.display_transform import (
    DisplayTransform,
    render_threshold_mask,
    to_display_uint8,
)
from pixelscope.core.roi import RoiBounds
from pixelscope.core.statistics import histogram
from pixelscope.io.image_reader import read_raw_document
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.comparison_analysis_panel import automatic_histogram_spec


def test_fhd_rgb_uint8_characterization() -> None:
    shape = (1080, 1920, 3)
    source = np.empty(shape, dtype=np.uint8)
    source[..., 0] = 17
    source[..., 1] = 73
    source[..., 2] = 211

    timings: dict[str, float] = {}
    start = perf_counter()
    preview = to_display_uint8(source)
    timings["preview"] = perf_counter() - start
    start = perf_counter()
    result = histogram(source, 256)
    timings["histogram"] = perf_counter() - start
    start = perf_counter()
    absolute = compact_absolute_difference(source, source)
    timings["difference"] = perf_counter() - start
    start = perf_counter()
    mask = render_threshold_mask(absolute, 0)
    timings["threshold_mask"] = perf_counter() - start

    print(
        "characterization=FHD_RGB_uint8",
        "performance_seconds=",
        timings,
        "native_bytes=",
        source.nbytes,
    )
    assert source.nbytes == 1080 * 1920 * 3
    assert preview.shape == shape
    assert preview.dtype == np.uint8
    assert result.channel_names == ("R", "G", "B")
    assert all(int(counts.sum()) == 1080 * 1920 for counts in result.counts)
    assert absolute.shape == shape
    assert absolute.dtype == np.uint8
    assert not np.any(absolute)
    assert mask.shape == (1080, 1920, 3)
    assert mask.dtype == np.uint8
    assert not np.any(mask)


def test_fhd_grayscale_uint16_characterization() -> None:
    shape = (1080, 1920)
    source = np.arange(shape[0] * shape[1], dtype=np.uint16).reshape(shape)

    timings: dict[str, float] = {}
    start = perf_counter()
    preview = to_display_uint8(source, DisplayTransform(0, 65535))
    timings["preview"] = perf_counter() - start
    start = perf_counter()
    result = histogram(source, 1024)
    timings["histogram"] = perf_counter() - start
    start = perf_counter()
    signed = signed_difference(source, source)
    timings["signed_difference"] = perf_counter() - start
    start = perf_counter()
    absolute = compact_absolute_difference(source, source)
    timings["compact_absolute_difference"] = perf_counter() - start

    print(
        "characterization=FHD_GRAY_uint16",
        "performance_seconds=",
        timings,
        "native_bytes=",
        source.nbytes,
    )
    assert source.nbytes == 1080 * 1920 * 2
    assert preview.shape == shape
    assert preview.dtype == np.uint8
    assert result.channel_names == ("Gray",)
    assert int(result.counts[0].sum()) == source.size
    assert signed.dtype == np.int32
    assert absolute.dtype == np.uint16
    assert not np.any(signed)
    assert not np.any(absolute)


def test_uhd_bayer_uint16_raw_characterization(tmp_path: Path) -> None:
    shape = (2160, 3840)
    plane_values = (0, 16384, 32768, 65535)
    source = np.empty(shape, dtype=np.uint16)
    source[0::2, 0::2] = plane_values[0]
    source[0::2, 1::2] = plane_values[1]
    source[1::2, 0::2] = plane_values[2]
    source[1::2, 1::2] = plane_values[3]
    raw_path = tmp_path / "uhd-rggb16.raw"
    profile_path = tmp_path / "uhd-rggb16.json"
    source.tofile(raw_path)
    profile = RawProfile(
        name="uhd-rggb16",
        width=shape[1],
        height=shape[0],
        stride_bytes=shape[1] * 2,
        container_dtype="uint16",
        endianness="little",
        bit_depth=16,
        channel_layout="BAYER",
        bayer_pattern="RGGB",
        black_level=0,
        white_level=65535,
    )
    profile.save_json(profile_path)

    timings: dict[str, float] = {}
    start = perf_counter()
    document = read_raw_document(raw_path, profile_path)
    timings["raw_document_load"] = perf_counter() - start
    mapped = document.source
    preview = document.preview
    assert mapped is not None
    assert preview is not None

    bins, value_range = automatic_histogram_spec(document)
    start = perf_counter()
    analysis = analyze_bayer_roi(
        mapped,
        RoiBounds(0, 0, shape[1], shape[0]),
        "RGGB",
        bins,
        value_range,
    )
    timings["bayer_analysis"] = perf_counter() - start
    start = perf_counter()
    signed = signed_difference(mapped, source)
    timings["signed_difference"] = perf_counter() - start
    start = perf_counter()
    absolute = compact_absolute_difference(mapped, source)
    timings["compact_absolute_difference"] = perf_counter() - start
    start = perf_counter()
    metrics = absolute_difference_metrics(absolute, 65535.0)
    timings["difference_metrics"] = perf_counter() - start
    start = perf_counter()
    mask = render_threshold_mask(absolute, 10)
    timings["threshold_mask"] = perf_counter() - start

    print(
        "characterization=UHD_BAYER_uint16_RAW",
        "performance_seconds=",
        timings,
        "native_bytes=",
        mapped.nbytes,
        "temporary_bytes=",
        {
            "preview": preview.nbytes,
            "signed": signed.nbytes,
            "absolute": absolute.nbytes,
            "mask": mask.nbytes,
        },
    )
    assert document.channel_layout == "BAYER"
    assert document.bit_depth == 16
    assert document.raw_profile == profile
    assert mapped.shape == shape
    assert mapped.dtype.itemsize == 2
    assert np.issubdtype(mapped.dtype, np.unsignedinteger)
    assert mapped.nbytes == source.nbytes == 2160 * 3840 * 2
    assert np.array_equal(mapped, source)

    assert preview.shape == (2160, 3840, 3)
    assert preview.dtype == np.uint8
    assert tuple(preview[0, 0]) == (0, 0, 0)
    assert tuple(preview[0, 1]) == (24, 64, 24)
    assert tuple(preview[1, 0]) == (49, 128, 49)
    assert tuple(preview[1, 1]) == (97, 255, 97)
    assert np.array_equal(preview[..., 0], preview[..., 2])

    assert bins == 4096
    assert value_range == (0.0, 65536.0)
    assert analysis.channel_names == ("R", "Gr", "Gb", "B")
    assert analysis.histogram.channel_names == analysis.channel_names
    assert analysis.channel_sample_counts == (2_073_600,) * 4
    assert sum(analysis.channel_sample_counts) == source.size
    expected_bins = (0, 1024, 2048, 4095)
    for counts, expected_bin in zip(
        analysis.histogram.counts,
        expected_bins,
        strict=True,
    ):
        assert int(counts.sum()) == 2_073_600
        assert np.count_nonzero(counts) == 1
        assert int(counts[expected_bin]) == 2_073_600
    channel_means = [statistics.mean for statistics in analysis.channel_statistics]
    assert channel_means == list(plane_values)

    assert signed.dtype == np.int32
    assert absolute.dtype == np.uint16
    assert not np.any(signed)
    assert not np.any(absolute)
    assert metrics.mse == 0.0
    assert metrics.p99 == 0.0
    assert metrics.nonzero_ratio == 0.0
    assert mask.shape == (2160, 3840, 3)
    assert mask.dtype == np.uint8
    assert not np.any(mask)
