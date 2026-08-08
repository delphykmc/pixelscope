from __future__ import annotations

from pathlib import Path
from time import perf_counter

import numpy as np

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
from pixelscope.core.statistics import histogram
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import read_raw


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
    source = np.arange(shape[0] * shape[1], dtype=np.uint16).reshape(shape)
    raw_path = tmp_path / "uhd-rggb16.raw"
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

    timings: dict[str, float] = {}
    start = perf_counter()
    mapped = read_raw(raw_path, profile)
    timings["memmap"] = perf_counter() - start
    start = perf_counter()
    preview = to_display_uint8(mapped, DisplayTransform(0, 65535))
    timings["preview"] = perf_counter() - start
    start = perf_counter()
    result = histogram(mapped, 1024)
    timings["histogram"] = perf_counter() - start
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
    assert mapped.shape == shape
    assert mapped.dtype.itemsize == 2
    assert np.issubdtype(mapped.dtype, np.unsignedinteger)
    assert mapped.nbytes == source.nbytes == 2160 * 3840 * 2
    assert np.array_equal(mapped, source)
    assert result.channel_names == ("Gray",)
    assert int(result.counts[0].sum()) == source.size
    assert preview.shape == shape
    assert preview.dtype == np.uint8
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
