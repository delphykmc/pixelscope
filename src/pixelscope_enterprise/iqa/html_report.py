"""Offline, source-identity-preserving HTML report over the UX-3B PNG export.

This is a static visual report, not a portable result, scientific source
serializer, private provider schema, or producer-certified ROI measurement.
"""

from __future__ import annotations

import html
import json
import os
import tempfile
from pathlib import Path
from typing import cast

from PySide6.QtGui import QImage

from pixelscope_enterprise.iqa.analysis_model import AnalysisResult, AttributeDisplay, Roi, roi_statistics
from pixelscope_enterprise.iqa.visual_export import ExportScope, export_folder, write_visual_pngs


def report_folder(parent: Path, result_id: str) -> Path:
    """Match PNG's safe identity slug, with a separate report namespace."""

    png_name = export_folder(parent, result_id).name
    return parent / png_name.replace("iqa-images-", "iqa-report-", 1)


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _number(value: float | None) -> str:
    return "\u2014" if value is None else f"{value:.6g}"


_STYLE = """
:root { color-scheme: light; font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; }
body { max-width: 1440px; margin: 0 auto; padding: 32px 24px 72px; color: #28323e;
       background: #f7f8fa; line-height: 1.45; }
h1, h2, h3 { color: #182334; }
h1 { margin-bottom: 8px; }
main > section { margin: 20px 0; padding: 22px; background: white;
                 border: 1px solid #e2e5eb; border-radius: 12px; }
.muted { color: #566376; }
.note { padding: 10px 14px; border-left: 3px solid #8496aa; background: #f1f4f8; }
.media { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
figure { margin: 0; min-width: 0; }
figure img { width: 100%; height: auto; object-fit: contain; background: #eef0f3;
             border: 1px solid #dfe3e9; image-rendering: pixelated; }
figcaption { font-size: 0.88rem; margin: 6px 0 12px; overflow-wrap: anywhere; }
.unavailable { background: #f3f5f7; padding: 24px 12px; min-height: 70px; color: #566376; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 9px 11px; text-align: left; border-bottom: 1px solid #e5e8ed;
         overflow-wrap: anywhere; }
th { background: #f4f6f9; font-weight: 600; }
code { font-size: 0.9em; overflow-wrap: anywhere; }
@media (max-width: 880px) { .media { grid-template-columns: 1fr; } body { padding: 12px; } }
@media print { body { background: white; } main > section { break-inside: avoid; } }
"""


def _attr_rows(
    result: AnalysisResult, roi_rect: tuple[int, int, int, int] | None
) -> str:
    rows: list[str] = []
    for attr in result.attributes:
        availability = attr.official_availability
        # Partial scalars are not treated as complete full-pair evidence.
        full_value = (
            _number(attr.official_value)
            if availability == "available"
            else "\u2014"
        )
        roi_value = "\u2014"
        coverage = "\u2014"
        if roi_rect is not None and attr.spatial is not None:
            region = roi_statistics(attr.spatial, roi_rect)
            roi_value = _number(region.mean)
            coverage = f"{region.valid_coverage * 100:.2f}%"
        rows.append(
            "<tr>"
            f"<td>{_escape(attr.label)}</td>"
            f"<td>{_escape(attr.group)}</td>"
            f"<td>{_escape(attr.unit)}</td>"
            f"<td>{_escape(full_value)}</td>"
            f"<td>{_escape(availability)}</td>"
            f"<td>{_escape(roi_value)}</td>"
            f"<td>{_escape(coverage)}</td>"
            f"<td>{'Directional' if attr.quality_oriented else 'Neutral signed'}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _region_cards(
    scope_name: str,
    result: AnalysisResult,
    selected: AttributeDisplay,
    exported: set[str],
    omissions: dict[str, str],
) -> str:
    cards: list[str] = []
    for stem, title, label in (
        ("source_A", "Source A", result.source_a_label),
        ("source_B", "Source B", result.source_b_label),
        ("selected_map", "Selected Map", selected.label),
    ):
        name = f"{stem}_{scope_name}.png"  # Fixed allowlisted filename, not user input.
        caption = f"{title}: {label}"
        if name in exported:
            cards.append(
                f'<figure><img loading="lazy" src="{name}" '
                f'alt="{_escape(caption)}">'
                f"<figcaption>{_escape(caption)}</figcaption></figure>"
            )
        else:
            reason = omissions.get(name, "unavailable")
            cards.append(
                f'<figure><div class="unavailable">{_escape(reason)}</div>'
                f"<figcaption>{_escape(caption)}</figcaption></figure>"
            )
    return "\n".join(cards)


def render_html_report(
    result: AnalysisResult,
    selected: AttributeDisplay,
    manifest: dict[str, object],
) -> str:
    """Return fixed-template HTML. Untrusted labels are text, never markup/URLs."""

    regions = cast(dict[str, dict[str, object]], manifest["regions"])
    exported = set(cast(list[str], manifest["exported_files"]))
    omitted = cast(dict[str, str], manifest["omitted_files"])
    map_info = cast(dict[str, object], manifest["selected_map"])
    roi_rect: tuple[int, int, int, int] | None = None
    if "roi" in regions:
        raw = cast(list[int], regions["roi"]["xywh_px"])
        roi_rect = raw[0], raw[1], raw[2], raw[3]

    panels: list[str] = []
    for scope, region in regions.items():
        coords = cast(list[int], region["xywh_px"])
        coords_text = f"({coords[0]}, {coords[1]}) \u00b7 {coords[2]}\u00d7{coords[3]} px"
        panels.append(
            f"<section><h2>{'Full image' if scope == 'full' else 'Active ROI'}</h2>"
            f"<p class=\"muted\">Original source pixels: {_escape(coords_text)}</p>"
            f'<div class="media">{_region_cards(scope, result, selected, exported, omitted)}</div>'
            "</section>"
        )

    roi_warning = (
        "ROI figures are GRID-derived area-weighted estimates, not verified "
        "producer-provided regional comparison scores."
        if roi_rect is not None
        else "Select an ROI in the analysis window to include GRID-derived regional estimates."
    )
    direction = "Quality-oriented" if selected.quality_oriented else "Neutral signed difference"
    valid = _escape(map_info["total_valid_cells"])
    clipped = _escape(map_info["clipped_valid_cells"])
    gain = _escape(map_info["display_gain"])
    limit = _escape(map_info["display_range"])
    effective = _escape(map_info["effective_half_range"])
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta http-equiv=\"Content-Security-Policy\" "
        "content=\"default-src 'none'; img-src 'self' file:; "
        "style-src 'unsafe-inline'; connect-src 'none'; "
        "base-uri 'none'; form-action 'none'\">"
        f"<title>IQA report \u2014 {_escape(result.result_id)}</title>"
        f"<style>{_STYLE}</style></head><body><main>"
        "<header><h1>IQA visual report</h1>"
        f"<p class=\"muted\">Result: {_escape(result.result_id)} \u00b7 "
        f"{result.image_width}\u00d7{result.image_height} source pixels</p>"
        f"<p>Source A: <strong>{_escape(result.source_a_label)}</strong> &nbsp; "
        f"Source B: <strong>{_escape(result.source_b_label)}</strong></p>"
        "</header>"
        "<p class=\"note\">Offline, non-reloadable report. Source PNGs are decoded "
        "RGB, not bit-exact RAW. Spatial colors are visualizations and do not "
        "change numeric measurements.</p>"
        + "".join(panels)
        + "<section><h2>Measurements</h2>"
        "<p class=\"note\">Full-pair comparison and GRID-derived ROI estimate are "
        f"independent. {_escape(roi_warning)}</p>"
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Attribute</th><th>Group</th><th>Unit</th>"
        "<th>Full-pair comparison</th><th>Full availability</th>"
        "<th>GRID-derived ROI estimate</th><th>ROI valid coverage</th>"
        "<th>Orientation</th></tr></thead><tbody>"
        + _attr_rows(result, roi_rect)
        + "</tbody></table></div></section>"
        "<section><h2>Selected Map rendering</h2>"
        f"<p>Attribute: {_escape(selected.label)} \u00b7 unit: {_escape(selected.unit)} "
        f"\u00b7 {_escape(direction)}</p>"
        f"<p>Display Range: \u00b1{limit}; Gain: {gain}; "
        f"effective map half-range: \u00b1{effective}.</p>"
        f"<p>Clipped valid cells: {clipped} of {valid}, counted over the "
        "<strong>entire spatial grid</strong>, not independently per ROI. "
        "Invalid or uncovered pixels are transparent.</p>"
        "<p class=\"muted\">Offline report assets: fixed PNG files and "
        "export_info.json in this same folder. No scripts or network resources.</p>"
        "</section></main></body></html>\n"
    )


def write_html_report(
    result: AnalysisResult,
    selected: AttributeDisplay,
    source_images: tuple[QImage | None, QImage | None],
    destination: Path,
    *,
    scope: ExportScope,
    roi: Roi | None,
    display_range: float,
    display_gain: float,
) -> Path:
    """Publish an offline HTML + PNG report folder only when completely generated."""

    if destination.exists() or destination.is_symlink():
        raise FileExistsError("HTML report directory already exists")
    if not destination.parent.is_dir():
        raise FileNotFoundError("HTML report parent does not exist")

    with tempfile.TemporaryDirectory(prefix=".iqa-html-", dir=destination.parent) as outer:
        stage = Path(outer) / "report"
        write_visual_pngs(
            result,
            selected,
            source_images,
            stage,
            scope=scope,
            roi=roi,
            display_range=display_range,
            display_gain=display_gain,
        )
        # JSON was produced from immutable adapter data, never from a user-selected
        # preexisting export folder. The writer has already validated scope/geometry.
        manifest = cast(
            dict[str, object],
            json.loads((stage / "export_info.json").read_text(encoding="utf-8")),
        )
        content = render_html_report(result, selected, manifest)
        with (stage / "index.html").open("w", encoding="utf-8", newline="\n") as out:
            out.write(content)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("HTML report directory already exists")
        os.rename(stage, destination)
        return destination
