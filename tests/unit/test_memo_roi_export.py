"""Contract tests for the current page's ROI PNG evidence export."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from pixelscope.core.roi import RoiBounds
from pixelscope.io.memo_roi_export import export_roi_pngs


def test_two_selected_rgb_roi_outputs_exact_crops(tmp_path: Path) -> None:
    first = np.arange(9 * 13 * 3, dtype=np.uint8).reshape(9, 13, 3)
    second = np.full((9, 13, 3), [12, 31, 54], dtype=np.uint8)
    roi = RoiBounds(2, 3, 5, 4)
    files = export_roi_pngs(
        tmp_path,
        (("a.png", first), ("a.jpg", second)),
        roi,
    )
    assert len(files) == 2
    assert files[0].name != files[1].name
    for path, expected in zip(files, (first, second)):
        decoded = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        assert decoded is not None
        rgb = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)
        np.testing.assert_array_equal(rgb, expected[3:7, 2:7])


def test_exact_roi_failure_has_no_outputs(tmp_path: Path) -> None:
    original = np.zeros((20, 20, 4), dtype=np.uint8)
    short = np.zeros((5, 5, 3), dtype=np.uint8)
    with pytest.raises(ValueError, match="outside"):
        export_roi_pngs(
            tmp_path,
            (("one.png", original), ("two.png", short)),
            RoiBounds(3, 3, 4, 4),
        )
    assert list(tmp_path.iterdir()) == []


def test_repeated_export_never_overwrites(tmp_path: Path) -> None:
    gray = np.full((7, 7), 85, dtype=np.uint8)
    first = export_roi_pngs(tmp_path, (("x.png", gray),), RoiBounds(0, 0, 2, 2))
    second = export_roi_pngs(tmp_path, (("x.png", gray),), RoiBounds(0, 0, 2, 2))
    assert first != second
    assert first[0].read_bytes() == second[0].read_bytes()


def test_cancel_cleans_outputs(tmp_path: Path) -> None:
    preview = np.zeros((10, 10), dtype=np.uint8)
    count = 0

    def cancel() -> bool:
        nonlocal count
        count += 1
        return count >= 3

    with pytest.raises(RuntimeError, match="cancelled"):
        export_roi_pngs(
            tmp_path, (("one.png", preview), ("two.png", preview)),
            RoiBounds(0, 0, 2, 2), cancel=cancel,
        )
    assert not list(tmp_path.iterdir())
