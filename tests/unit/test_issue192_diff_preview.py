import numpy as np
import pytest

from pixelscope.core.display_transform import (
    render_absolute_difference,
    render_absolute_difference_range,
    render_signed_difference,
    render_threshold_mask,
)


def reference(diff, gain=1.0):
    """Snapshot of unmodified main@a9ecbf4, independent of candidate import."""
    if gain <= 0:
        raise ValueError("display gain must be greater than zero")
    maximum = max(float(np.max(diff)), 1.0)
    scaled = np.clip(diff.astype(np.float32) * gain / maximum, 0.0, 1.0)
    return np.ascontiguousarray(np.rint(scaled * 255.0).astype(np.uint8))


GAINS = (
    1e-8,
    0.1,
    0.5,
    np.nextafter(0.5, 0),
    np.nextafter(0.5, 1),
    1,
    1.25,
    2.5,
    1000,
    1e30,
    np.float32(0.7),
    np.float64(1.3),
)


@pytest.mark.parametrize("gain", GAINS)
def test_every_byte_and_actual_maximum_match_reference(gain):
    for maximum in range(256):
        values = np.arange(maximum + 1, dtype=np.uint8)
        source = np.resize(values, (17, 19, 3))
        before = source.copy()
        actual = render_absolute_difference(source, gain)
        assert np.array_equal(actual, reference(source, gain)), (maximum, gain)
        assert actual.shape == source.shape and actual.dtype == np.uint8
        assert actual.flags.c_contiguous and not np.shares_memory(actual, source)
        assert np.array_equal(source, before)


@pytest.mark.parametrize(
    "layout", ["gray", "rgb", "four", "roi", "reverse", "transpose", "readonly"]
)
def test_layout_strides_readonly_and_ownership(layout):
    source = np.random.default_rng(192).integers(0, 256, (37, 43, 4), dtype=np.uint8)
    source = {
        "gray": source[..., 0],
        "rgb": source[..., :3],
        "four": source,
        "roi": source[2:31:2, 3:39:3],
        "reverse": source[::-1, ::-1],
        "transpose": source.transpose(1, 0, 2),
        "readonly": source,
    }[layout]
    source.setflags(write=False)
    for gain in GAINS:
        result = render_absolute_difference(source, gain)
        assert np.array_equal(result, reference(source, gain))
        assert result.flags.c_contiguous and not np.shares_memory(result, source)


@pytest.mark.parametrize("dtype", [np.uint16, np.int16, np.float32, np.float64])
def test_nonbyte_fallback_exact(dtype):
    source = np.array([[0, 1, 17], [2, 7, 255]], dtype=dtype)
    for gain in GAINS:
        assert np.array_equal(render_absolute_difference(source, gain), reference(source, gain))


@pytest.mark.parametrize("gain", [0, -1, -0.1])
def test_invalid_gain_preserves_error(gain):
    with pytest.raises(ValueError, match="display gain must be greater than zero"):
        render_absolute_difference(np.zeros((2, 3), dtype=np.uint8), gain)


@pytest.mark.parametrize("gain", [float("inf"), float("nan"), 1e300, 1e-40])
@pytest.mark.parametrize("value", [0, 1, 255])
def test_extreme_gain_and_floating_error_behavior(gain, value):
    source = np.full((2, 3), value, dtype=np.uint8)
    with np.errstate(all="raise"):
        try:
            expected = reference(source, gain)
        except (FloatingPointError, ValueError, TypeError) as error:
            with pytest.raises(type(error)):
                render_absolute_difference(source, gain)
        else:
            assert np.array_equal(render_absolute_difference(source, gain), expected)


def test_halfstep_neighbors_preserve_multiply_divide_and_round_order():
    for maximum in (1, 2, 127, 254, 255):
        source = np.resize(np.arange(maximum + 1, dtype=np.uint8), (17, 19, 3))
        for value in (1, maximum):
            for code in (0, 1, 63, 127, 254):
                half = maximum * (code + 0.5) / (255 * value)
                for gain in (half, np.nextafter(half, 0), np.nextafter(half, np.inf)):
                    assert np.array_equal(
                        render_absolute_difference(source, gain), reference(source, gain)
                    )


@pytest.mark.parametrize("shape", [(256,), (8, 16, 2), (4, 8, 8, 3), (3, 5, 1)])
def test_other_shapes_keep_baseline_contract(shape):
    source = np.resize(np.arange(256, dtype=np.uint8), shape)
    assert np.array_equal(render_absolute_difference(source, 1.3), reference(source, 1.3))


def test_array_gain_and_subclass_preserve_fallback_contract():
    source = np.arange(12, dtype=np.uint8).reshape(3, 4)
    gain = np.array([1.3])
    assert np.array_equal(render_absolute_difference(source, gain), reference(source, gain))

    class ByteArray(np.ndarray):
        pass

    matrix = source.view(ByteArray)
    assert np.array_equal(render_absolute_difference(matrix), reference(matrix))


def test_other_diff_modes_keep_independent_baseline_goldens():
    source = np.array([[0, 10, 50, 100, 255]], dtype=np.uint16)
    assert np.array_equal(
        render_absolute_difference_range(source, 10, 100, 2),
        np.array([[0, 0, 227, 255, 255]], dtype=np.uint8),
    )
    signed = np.array([[-100, 0, 100]], dtype=np.int16)
    assert np.array_equal(
        render_signed_difference(signed),
        np.array([[[127, 0, 255], [127, 127, 127], [255, 0, 127]]], dtype=np.uint8),
    )
    rgb = np.array([[[10, 0, 0], [0, 11, 0], [0, 0, 11]]], dtype=np.uint8)
    assert np.array_equal(
        render_threshold_mask(rgb, 10),
        np.array([[[0, 0, 0], [255, 0, 0], [255, 0, 0]]], dtype=np.uint8),
    )
