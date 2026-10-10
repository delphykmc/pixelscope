"""UX-3B standalone HTML report: offline assets, provenance and escaping."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtGui import QColor, QImage

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay, SpatialMap
from pixelscope_enterprise.iqa.html_report import report_folder, write_html_report


def _case() -> tuple[AnalysisResult, AttributeDisplay, QImage]:
    spatial = SpatialMap(
        values=np.array([[2.0, np.nan], [0.0, -3.0]], dtype=np.float64),
        valid_mask=np.array([[True, False], [True, True]]),
        image_width=8,
        image_height=8,
        block_width=4.0,
        block_height=4.0,
    )
    selected = AttributeDisplay(
        attribute_id="signed",
        label="Signed <Noise> & Texture",
        unit="dB",
        group="Quality & detail",
        official_value=1.5,
        official_availability="available",
        quality_oriented=False,
        fixed_range=4.0,
        spatial=spatial,
    )
    partial = AttributeDisplay(
        attribute_id="partial",
        label="<script>alert(1)</script>",
        unit="delta",
        group="Untrusted",
        official_value=99.999,
        official_availability="partial",
        quality_oriented=True,
        fixed_range=10.0,
    )
    result = AnalysisResult(
        result_id="../../unsafe-<result>",
        image_width=8,
        image_height=8,
        source_a_label='<img src="https://bad.example/x" onerror="alert(2)">',
        source_b_label="=Source B",
        attributes=(selected, partial),
    )
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor(30, 40, 50))
    return result, selected, image


def test_offline_report_escapes_untrusted_text_and_reuses_true_pngs(tmp_path: Path) -> None:
    result, selected, image = _case()
    destination = report_folder(tmp_path, result.result_id)
    assert destination.parent == tmp_path
    assert "<" not in destination.name and ".." not in destination.name
    output = write_html_report(
        result,
        selected,
        (image, None),
        destination,
        scope="both",
        roi=(1.0, 1.0, 4.0, 4.0),
        display_range=4.0,
        display_gain=2.0,
    )
    page = (output / "index.html").read_text(encoding="utf-8")
    metadata = json.loads((output / "export_info.json").read_text(encoding="utf-8"))
    assert (output / "source_A_full.png").exists()
    assert (output / "source_A_roi.png").exists()
    assert (output / "selected_map_full.png").exists()
    assert (output / "selected_map_roi.png").exists()
    assert not (output / "source_B_full.png").exists()
    assert '<script' not in page.lower()
    assert 'src="https://' not in page
    assert "&lt;img src=&quot;https://bad.example/x&quot;" in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "99.999" not in page  # A partial full-pair scalar is not official complete evidence.
    assert "1.5" in page
    assert "ROI valid coverage" in page
    assert "Full-pair comparison" in page
    assert "GRID-derived" in page
    assert "default-src 'none'" in page
    assert "connect-src 'none'" in page
    assert '<img loading="lazy" src="source_A_roi.png"' in page
    assert "No scripts or network resources." in page
    assert metadata["requested_scope"] == "both"
    assert metadata["selected_map"]["effective_half_range"] == 2.0
    assert metadata["omitted_files"]["source_B_roi.png"]
    assert {p.name for p in tmp_path.iterdir()} == {destination.name}


def test_map_only_report_and_roi_unavailable(tmp_path: Path) -> None:
    result, selected, _image = _case()
    dest = tmp_path / "map-only"
    write_html_report(
        result,
        selected,
        (None, None),
        dest,
        scope="full",
        roi=None,
        display_range=4.0,
        display_gain=1.0,
    )
    page = (dest / "index.html").read_text(encoding="utf-8")
    assert "original RGB unavailable" in page
    assert "Select an ROI" in page
    assert (dest / "selected_map_full.png").exists()
    assert "source_A_full.png" not in [p.name for p in dest.iterdir()]
    assert "None of" not in page


def test_existing_folder_and_failed_html_generation_leave_no_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, selected, image = _case()
    existing = tmp_path / "existing"
    existing.mkdir()
    marker = existing / "untouched"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_html_report(
            result, selected, (image, None), existing,
            scope="full", roi=None, display_range=4.0, display_gain=1.0,
        )
    assert marker.read_text(encoding="utf-8") == "preserve"

    import pixelscope_enterprise.iqa.html_report as report_module

    def fail_html(*_args: object, **_kwargs: object) -> str:
        raise OSError("simulated HTML render failure")

    monkeypatch.setattr(report_module, "render_html_report", fail_html)
    dest = tmp_path / "broken"
    with pytest.raises(OSError, match="simulated"):
        write_html_report(
            result, selected, (image, None), dest,
            scope="roi", roi=(0.0, 0.0, 4.0, 4.0),
            display_range=4.0, display_gain=1.0,
        )
    assert not dest.exists()
    assert {p.name for p in tmp_path.iterdir()} == {"existing"}
