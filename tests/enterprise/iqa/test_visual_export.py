"""UX-3B visual PNG contract: pixel alignment, validity and transactional output."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtGui import QColor, QImage

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay, SpatialMap
from pixelscope_enterprise.iqa.visual_export import (
    export_folder,
    map_rgba,
    write_visual_pngs,
)


def _pair(*, with_grid: bool = True) -> tuple[AnalysisResult, AttributeDisplay]:
    grid = SpatialMap(
        values=np.array([[2.0, -3.0], [0.0, 1.0]], dtype=np.float64),
        valid_mask=np.array([[True, False], [True, True]]),
        image_width=5,
        image_height=4,
        block_width=2.0,
        block_height=2.0,
        origin_x=1.0,
    )
    attribute = AttributeDisplay(
        attribute_id="signed",
        label="Unoriented signed delta",
        unit="delta",
        group="synthetic",
        official_value=0.0,
        official_availability="available",
        quality_oriented=False,
        fixed_range=4.0,
        spatial=grid if with_grid else None,
    )
    return (
        AnalysisResult(
            result_id="../../secret-result",
            image_width=5,
            image_height=4,
            source_a_label="=UNTRUSTED, A",
            source_b_label="Source B",
            attributes=(attribute,),
        ),
        attribute,
    )


def _source() -> QImage:
    image = QImage(5, 4, QImage.Format.Format_RGB32)
    image.fill(QColor(51, 121, 191))
    image.setPixelColor(1, 1, QColor(5, 9, 17))
    return image


def test_source_pixel_geometry_invalid_alpha_and_real_zero() -> None:
    _result, attribute = _pair()
    raster = map_rgba(attribute, (0, 0, 5, 4), 4.0)
    assert raster.shape == (4, 5, 4)
    assert raster[0, 0, 3] == 0  # Left edge outside the declared grid origin.
    assert raster[0, 1, 3] == 255  # In first grid cell.
    assert raster[0, 3, 3] == 0  # Invalid grid cell is transparent, not zero.
    assert raster[2, 1, 3] == 255  # True zero is valid and opaque.
    assert tuple(raster[2, 1, :3]) == (239, 239, 239)
    roi_raster = map_rgba(attribute, (1, 1, 2, 2), 4.0)
    np.testing.assert_array_equal(roi_raster, raster[1:3, 1:3])
    assert not np.array_equal(map_rgba(attribute, (1, 1, 2, 2), 2.0), roi_raster)
    assert attribute.spatial is not None
    assert attribute.spatial.values[1, 0] == 0.0  # Display change is non-destructive.


def test_full_and_roi_pngs_keep_semantic_a_and_truthful_metadata(tmp_path: Path) -> None:
    result, attribute = _pair()
    target = export_folder(tmp_path, result.result_id)
    assert target.parent == tmp_path
    assert ".." not in target.name and "/" not in target.name
    saved = write_visual_pngs(
        result,
        attribute,
        (_source(), None),
        target,
        scope="both",
        roi=(1.0, 1.0, 2.0, 2.0),
        display_range=4.0,
        display_gain=2.0,
    )
    assert saved == target
    expected = {
        "source_A_full.png",
        "source_A_roi.png",
        "selected_map_full.png",
        "selected_map_roi.png",
        "export_info.json",
    }
    assert {path.name for path in target.iterdir()} == expected
    original = QImage(str(target / "source_A_full.png"))
    crop = QImage(str(target / "source_A_roi.png"))
    assert (original.width(), original.height()) == (5, 4)
    assert (crop.width(), crop.height()) == (2, 2)
    assert crop.pixelColor(0, 0) == QColor(5, 9, 17)
    map_full = QImage(str(target / "selected_map_full.png"))
    map_roi = QImage(str(target / "selected_map_roi.png"))
    assert map_full.pixelColor(0, 0).alpha() == 0
    assert map_full.pixelColor(3, 0).alpha() == 0
    assert map_full.pixelColor(1, 2).alpha() == 255
    assert map_roi.pixelColor(0, 1) == map_full.pixelColor(1, 2)

    info = json.loads((target / "export_info.json").read_text(encoding="utf-8"))
    assert info["kind"] == "nonportable_visual_png_export"
    assert info["source_a_label"] == "=UNTRUSTED, A"
    assert info["source_b_label"] == "Source B"
    assert info["regions"]["roi"]["xywh_px"] == [1, 1, 2, 2]
    assert info["selected_map"]["clamp_count_scope"] == "whole_spatial_grid_valid_cells"
    assert info["selected_map"]["clipped_valid_cells"] == 0
    assert info["selected_map"]["effective_half_range"] == 2.0
    assert not info["selected_map"]["quality_oriented"]
    assert "source_B_full.png" in info["omitted_files"]
    assert "source_B_roi.png" in info["omitted_files"]
    assert "source_A_roi.png" in info["exported_files"]
    assert "source_a" not in info  # No absolute private source path.


def test_missing_source_and_missing_map_are_honest(tmp_path: Path) -> None:
    result, attribute = _pair(with_grid=False)
    target = tmp_path / "empty"
    with pytest.raises(ValueError, match="no source"):
        write_visual_pngs(
            result, attribute, (None, None), target,
            scope="full", roi=None, display_range=4.0, display_gain=1.0,
        )
    assert not target.exists()
    written = write_visual_pngs(
        result, attribute, (_source(), None), target,
        scope="full", roi=None, display_range=4.0, display_gain=1.0,
    )
    assert (written / "source_A_full.png").exists()
    assert not (written / "selected_map_full.png").exists()
    info = json.loads((written / "export_info.json").read_text(encoding="utf-8"))
    assert info["omitted_files"]["selected_map_full.png"].startswith("selected Attribute")
    assert info["selected_map"]["total_valid_cells"] is None


def test_invalid_scope_and_existing_directory_do_not_overwrite(tmp_path: Path) -> None:
    result, attribute = _pair()
    for scope, roi in (("roi", None), ("both", None), ("not-a-scope", None)):
        with pytest.raises(ValueError):
            write_visual_pngs(
                result, attribute, (_source(), None), tmp_path / f"bad-{scope}",
                scope=scope, roi=roi, display_range=4.0, display_gain=1.0,
            )
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "do_not_touch.txt"
    sentinel.write_text("unchanged")
    with pytest.raises(FileExistsError):
        write_visual_pngs(
            result, attribute, (_source(), None), existing,
            scope="full", roi=None, display_range=4.0, display_gain=1.0,
        )
    assert sentinel.read_text() == "unchanged"


def test_writer_failure_cleans_staging_and_keeps_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, attribute = _pair()
    import pixelscope_enterprise.iqa.visual_export as export

    def fail_rename(_source: Path, _destination: Path) -> None:
        raise OSError("injected final publish failure")

    monkeypatch.setattr(export.os, "rename", fail_rename)
    target = tmp_path / "new"
    with pytest.raises(OSError, match="publish failure"):
        write_visual_pngs(
            result, attribute, (_source(), None), target,
            scope="roi", roi=(1.0, 1.0, 2.0, 2.0),
            display_range=4.0, display_gain=1.0,
        )
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
    assert result.attributes[0].official_value == 0.0
