# ruff: noqa: E501  # Keep trusted HTML/CSS/JavaScript template fragments together.
"""Offline report presentation from saved native CSV and 8-bit preview evidence."""
from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import math
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
    from pixelscope.core.review_record import ReviewFindingV1
    from pixelscope.io.memo_archive import MemoArchive

_COPY_SCRIPT = """document.querySelectorAll('[data-copy-note]').forEach(button => {
  button.disabled = false;
  button.addEventListener('click', async () => {
    const note = button.closest('.memo').querySelector('.note').textContent;
    const status = button.closest('.memo').querySelector('[role="status"]');
    button.disabled = true;
    let copied = false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(note);
        copied = true;
      }
    } catch (_) {}
    if (!copied) {
      const active = document.activeElement;
      const selection = window.getSelection();
      const ranges = selection ? Array.from({length: selection.rangeCount}, (_, i) => selection.getRangeAt(i).cloneRange()) : [];
      const field = document.createElement('textarea');
      field.value = note;
      field.setAttribute('readonly', '');
      field.style.position = 'fixed';
      field.style.opacity = '0';
      document.body.appendChild(field);
      try {
        field.focus({preventScroll: true});
        field.select();
        copied = document.execCommand('copy');
      } catch (_) {} finally {
        field.remove();
        if (active && active.focus) active.focus({preventScroll: true});
        if (selection) { selection.removeAllRanges(); ranges.forEach(range => selection.addRange(range)); }
      }
    }
    status.textContent = copied ? 'Copied to clipboard' : 'Copy unavailable — select and copy the memo text.';
    button.dataset.state = copied ? 'copied' : 'ready';
    button.setAttribute('aria-label', copied ? 'Memo copied' : 'Copy memo');
    button.title = copied ? 'Copied' : 'Copy memo';
    button.disabled = false;
    window.setTimeout(() => { button.dataset.state = 'ready'; button.setAttribute('aria-label', 'Copy memo'); button.title = 'Copy memo'; }, 1600);
  });
});"""

_STYLE = """*{box-sizing:border-box}html{color-scheme:light;scroll-behavior:smooth}
body{margin:0;background:#f3f6fa;color:#223047;font:15px/1.6 system-ui,-apple-system,sans-serif;overflow-wrap:anywhere}
main{max-width:1240px;margin:0 auto;padding:40px 28px 56px}a{color:#285ec7}
.masthead{display:flex;justify-content:space-between;gap:24px;align-items:center;margin-bottom:24px}
.brand{font-size:12px;font-weight:750;letter-spacing:.16em;text-transform:uppercase;color:#3564bc}
h1{font-size:32px;letter-spacing:-.035em;line-height:1.2;margin:8px 0}h2{font-size:22px;line-height:1.35;margin:0}
.subtle{color:#64748b;font-size:13px;margin:6px 0}.summary,.badges,.roi-index{display:flex;flex-wrap:wrap;gap:8px}
.summary{justify-content:flex-end}.pill{display:inline-flex;align-items:center;gap:5px;border:1px solid #dae3ef;border-radius:7px;padding:4px 9px;font-size:12px;background:#f8fafd;color:#50617c}
.pill strong{color:#243b61;font-weight:650}.roi-index{margin:0 0 24px}.roi-index a{text-decoration:none;background:white;border:1px solid #dbe4f0;border-radius:6px;padding:5px 11px;font-size:12px;font-weight:650}
.roi-card{background:white;border:1px solid #dce5ef;border-radius:14px;margin:20px 0;box-shadow:0 4px 18px #24477306;overflow:hidden;scroll-margin-top:16px}
.roi-header{padding:24px 26px 20px;border-bottom:1px solid #e8edf4}.title-row{display:flex;align-items:flex-start;gap:14px;margin-bottom:14px}
.roi-number{background:#eaf1ff;color:#285ec7;padding:6px 10px;border-radius:7px;white-space:nowrap;font-size:12px;font-weight:750;letter-spacing:.04em}
.capture-time{margin-top:12px;color:#8190a5;font-size:11px}.content{padding:22px 26px}.memo{background:#f7f9fc;border:1px solid #e5ebf3;border-radius:10px;padding:16px 18px;margin-bottom:22px}
.memo-heading{display:flex;justify-content:space-between;align-items:center;gap:12px}.section-label{font-size:11px;letter-spacing:.1em;font-weight:750;text-transform:uppercase;color:#657891}
.note{white-space:pre-wrap;margin:10px 0 0;color:#334155}.note:empty:before{content:'No memo';color:#8995a6}
.button{display:inline-flex;align-items:center;justify-content:center;text-decoration:none;border:1px solid #d5dfed;background:white;color:#325b99;border-radius:6px;font:600 12px/1.4 system-ui;min-height:32px;padding:6px 11px;cursor:pointer}
.button:hover{background:#edf3ff;border-color:#b4c8ea}.button:focus-visible,.roi-index a:focus-visible{outline:3px solid #91b8ff;outline-offset:3px}.button:disabled{opacity:.5;cursor:default}
.copy-status{font-size:11px;color:#536f95;min-height:1.6em;margin-top:4px}.crop-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:18px}
figure{min-width:0;margin:0;border:1px solid #e0e7f0;border-radius:10px;overflow:hidden;background:#fff}.image-stage{background:#eef2f7;display:flex;align-items:center;justify-content:center;padding:14px;min-height:100px}
img{display:block;max-width:100%;height:auto;max-height:460px;object-fit:contain}.crop-caption{padding:15px}.source-name{font-size:13px;font-weight:650;margin:0 0 10px;color:#273b57}.source-tag{color:#3564bc;font-weight:500}
.crop-footer{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:12px}.file-type{font-size:11px;color:#8290a3}.statistics{margin-top:20px;padding-top:16px;border-top:1px solid #edf0f5}.footer{font-size:11px;text-align:center;color:#8a98aa;margin-top:26px}
.table-scroll{overflow-x:auto;margin:12px 0 16px}table{min-width:680px;width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;color:#526680;background:#f1f5fb;font-weight:650}th,td{padding:10px 12px;border-bottom:1px solid #e4ebf3;vertical-align:top}tbody tr:nth-child(even){background:#fafbfd}.numeric{font-variant-numeric:tabular-nums;white-space:nowrap}.stat-source{width:30%;max-width:280px}th{white-space:nowrap}h3{font-size:16px;margin:0}
@media(max-width:640px){main{padding:24px 14px}.masthead{display:block}.summary{justify-content:flex-start;margin-top:16px}h1{font-size:27px}.roi-header,.content{padding:18px}.title-row{gap:10px}h2{font-size:19px}.memo{padding:14px}}
@media print{body{background:white}main{padding:0}.roi-card{box-shadow:none}.button,.roi-index,.copy-status{display:none}.crop-grid{grid-template-columns:repeat(2,minmax(0,1fr))}figure,.memo,.roi-header{break-inside:avoid}}
/* V6: visually distinct crops, compact icon actions and source-grouped statistics. */
.crop-grid{gap:14px;align-items:stretch}
.crop-card{background:#fff;border:1px solid #cbd8e9;border-radius:11px;box-shadow:0 2px 8px #1832530c;overflow:hidden}
.crop-card .image-stage{background:#f1f5fa;min-height:124px;padding:12px;border-bottom:1px solid #e2eaf3}
.crop-card .crop-caption{padding:11px 13px}
.crop-card .source-name{font-size:12px;margin:0;line-height:1.5;min-width:0}
.crop-card .crop-footer{margin-top:7px;min-height:27px}
.icon-button{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;flex:0 0 28px;padding:0;background:white;border:1px solid #cbd8e9;border-radius:6px;color:#285b9a;cursor:pointer;text-decoration:none}
.icon-button:hover{background:#e9f1fd;border-color:#a6bfdf}
.icon-button:focus-visible{outline:3px solid #91b8ff;outline-offset:2px}
.icon-button:disabled{opacity:.5;cursor:default}
.icon-button svg{display:block;width:15px;height:15px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.icon-button[data-state="copied"]{background:#e6f4ec;color:#26764a}
.stat-caption{font-size:12px;color:#657891;margin:6px 0 12px}
.stat-psnr{margin:12px 0 16px;background:#f7fafd;border:1px solid #dfe8f4;border-radius:10px;padding:13px 15px}
.stat-psnr-head{display:flex;align-items:baseline;flex-wrap:wrap;gap:9px;font-size:13px;font-weight:700;color:#334b6c}
.stat-psnr-head small{font-size:11px;font-weight:450;color:#64748b}
.stat-psnr-list{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 4px}
.psnr-chip{display:inline-flex;align-items:center;gap:8px;border:1px solid #d3dfef;background:white;border-radius:8px;padding:7px 10px;font-size:12px;max-width:100%}
.psnr-chip strong{font-size:14px;font-variant-numeric:tabular-nums}
.psnr-na{color:#8994a4}
.stat-table-box{margin:12px 0 5px;overflow-x:auto;border:1px solid #dce6f2;border-radius:10px}
.stat-table{width:100%;min-width:840px;border-collapse:collapse;table-layout:auto;font-size:12px}
.stat-table th,.stat-table td{padding:9px 10px;vertical-align:middle;border-bottom:1px solid #e4ebf3}
.stat-table thead th{background:#eef3f9;color:#526680;text-align:center;font-weight:700}
.stat-table thead th:nth-child(-n+2){text-align:left}
.stat-table tbody tr:last-child>*{border-bottom:0}
.stat-table tbody tr.stat-group-start:not(:first-child)>*{border-top:2px solid #cbd8e9}
.stat-table tbody tr.stat-alternate{background:#f8fafd}
.stat-channel{font-size:14px;font-weight:800;vertical-align:top!important;width:48px}
.stat-channel.r{color:#c24b55}.stat-channel.g{color:#258355}.stat-channel.b{color:#356fbc}
.stat-image{min-width:120px;max-width:200px;overflow-wrap:anywhere;font-size:12px;font-weight:650}
.stat-image small{display:block;font-size:10px;color:#7b8da4;font-weight:400}
.stat-cell{text-align:right;white-space:nowrap;min-width:76px;font-variant-numeric:tabular-nums}
.stat-cell .stat-value{display:block;font-size:12px;color:#223047}
.stat-cell .stat-change{display:block;font-size:10px;line-height:1.6;font-weight:700}
.stat-up{color:#cb4f57}.stat-down{color:#2d79b3}.stat-flat{color:#79889e}.stat-na{color:#9aa6b6}
.stat-footer{display:flex;justify-content:flex-end;align-items:center;margin-top:12px}
@media(max-width:640px){.stat-psnr{padding:10px}.stat-table th,.stat-table td{padding:8px 7px}}
@media print{.stat-psnr,.stat-table-box{break-inside:avoid}.stat-table{min-width:0}.stat-table th,.stat-table td{padding:4px}.stat-footer{display:none}}


"""


_DOWNLOAD_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M4 17v4h16v-4"/></svg>'
_COPY_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>'
_CSV_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h7l5 5v13H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"/><path d="M14 3v6h5M9 13h7M9 16h7"/></svg>'


def _url(value: str) -> str:
    return html.escape(quote(value, safe="/"), quote=True)


_METRICS = ("Min", "Max", "Mean", "Std", "P1", "P50", "P99")
_RGB = ("R", "G", "B")


def _stat_number(row: dict[str, str] | None) -> float | None:
    if not row or row.get("State") != "finite":
        return None
    try:
        value = float(row.get("Value") or "")
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _decimal(value: float) -> str:
    """Readable display only: round to at most four decimal places."""
    rounded = f"{value:.4f}".rstrip("0").rstrip(".")
    return "0" if rounded in ("-0", "") else rounded


def _native_comparable(a: dict[str, str] | None, b: dict[str, str] | None) -> bool:
    return (
        a is not None
        and b is not None
        and all(
            a.get(key) == b.get(key)
            for key in ("Domain", "Native dtype", "Effective bits", "Definition")
        )
    )


def _statistics_table(data: bytes) -> str:
    """One channel-grouped table; show native CSV numbers without changing evidence."""
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    sources: dict[tuple[str, str], dict[str, dict[str, dict[str, str]]]] = {}
    for row in rows:
        metric = row.get("Metric")
        if metric not in _METRICS:
            continue
        identity = (row.get("Source") or "", row.get("Image") or "")
        sources.setdefault(identity, {}).setdefault(row.get("Channel") or "", {})[metric] = row
    if not sources:
        return "<p>No saved native ROI measurements.</p>"

    identities = list(sources)
    baseline = sources[identities[0]]
    channels = sorted(
        {channel for groups in sources.values() for channel in groups},
        key=lambda channel: (_RGB.index(channel) if channel in _RGB else 3, channel),
    )
    heads = "".join(f'<th scope="col">{name}</th>' for name in _METRICS)
    body = []
    for channel_index, channel in enumerate(channels):
        for index, identity in enumerate(identities):
            ordinal, name = identity
            metrics = sources[identity].get(channel, {})
            klass = "stat-group-start" if channel_index and index == 0 else ""
            if index % 2:
                klass += " stat-alternate"
            cells = [f'<tr class="{klass.strip()}">']
            if index == 0:
                channel_class = channel.lower() if channel in _RGB else ""
                cells.append(
                    f'<th scope="rowgroup" rowspan="{len(identities)}" '
                    f'class="stat-channel {channel_class}">{html.escape(channel)}</th>'
                )
            cells.append(
                f'<th scope="row" class="stat-image">{html.escape(ordinal)}'
                f"<small>{html.escape(name)}</small></th>"
            )
            for metric in _METRICS:
                record = metrics.get(metric)
                number = _stat_number(record)
                if number is None:
                    cells.append('<td class="stat-cell"><span class="stat-na">—</span></td>')
                    continue
                value = f'<span class="stat-value">{_decimal(number)}</span>'
                if index:
                    reference = baseline.get(channel, {}).get(metric)
                    base_value = _stat_number(reference)
                    if _native_comparable(record, reference) and base_value is not None:
                        delta = number - base_value
                        if math.isfinite(delta):
                            shown_delta = float(f"{delta:.4f}")
                            if shown_delta > 0:
                                arrow, style, sign = "↑", "stat-up", "+"
                            elif shown_delta < 0:
                                arrow, style, sign = "↓", "stat-down", ""
                            else:
                                arrow, style, sign = "→", "stat-flat", ""
                            value += (
                                f'<span class="stat-change {style}" '
                                f'title="Change vs image 01">{arrow} Δ {sign}{_decimal(delta)}</span>'
                            )
                        else:
                            value += '<span class="stat-change stat-na">Δ n/a</span>'
                    else:
                        value += '<span class="stat-change stat-na">Δ n/a</span>'
                cells.append(f'<td class="stat-cell">{value}</td>')
            cells.append("</tr>")
            body.extend(cells)

    metadata = []
    for ordinal, name in identities:
        source_record = next(
            (r for metrics in sources[ordinal, name].values() for r in metrics.values()),
            {},
        )
        bits = source_record.get("Effective bits") or ""
        description = " · ".join(
            part
            for part in (
                f"{ordinal}: {name}",
                source_record.get("Domain") or "",
                source_record.get("Native dtype") or "",
                f"{bits} bits" if bits else "",
                source_record.get("Definition") or "",
            )
            if part
        )
        metadata.append(html.escape(description))
    return (
        '<p class="stat-caption">Native Statistics · image 01 reference · '
        'colored arrows show numerical increase/decrease, not better/worse. '
        'Values rounded for display only.</p>'
        f'<p class="stat-caption">{" &nbsp; | &nbsp; ".join(metadata)}</p>'
        '<div class="stat-table-box" role="region" aria-label="Saved ROI native statistics" tabindex="0">'
        '<table class="stat-table"><thead><tr>'
        f'<th scope="col">Channel</th><th scope="col">Image</th>{heads}'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )


def _preview_psnr(
    archive: MemoArchive, finding: ReviewFindingV1, source_labels: Mapping[str, str]
) -> str:
    """Show PSNR from the exact stored 8-bit crops, never native Statistics."""
    from pixelscope.io.memo_preview_metrics import psnr_8bit_png

    keys = finding.source_keys
    if len(keys) < 2:
        return ""
    reference = archive.crops.get((finding.id, keys[0]))
    chips = []
    for index, key in enumerate(keys[1:], 2):
        target = archive.crops.get((finding.id, key))
        value = (
            psnr_8bit_png(reference, target)
            if reference is not None and target is not None
            else None
        )
        if value is None:
            rendered = "N/A"
            klass = "psnr-na"
        elif math.isinf(value):
            rendered = "∞ dB"
            klass = ""
        else:
            rendered = f"{value:.4f} dB"
            klass = ""
        label = html.escape(source_labels.get(key, str(index)))
        chips.append(
            f'<span class="psnr-chip"><span>01 vs {index:02d} · {label}</span>'
            f'<strong class="{klass}">{rendered}</strong></span>'
        )
    return (
        '<div class="stat-psnr"><div class="stat-psnr-head">'
        '8-bit Preview PSNR <small>Pixel-aligned crop · peak 255 · dB</small></div>'
        f'<div class="stat-psnr-list">{"".join(chips)}</div>'
        '<p class="stat-caption">Computed from the saved 8-bit preview PNG pixels '
        '(RGB channels jointly, grayscale when applicable). No registration or '
        'native RAW bit-depth measurement; N/A means incompatible or missing preview.</p></div>'
    )


def render_memo_report(
    archive: MemoArchive,
    image_paths: Mapping[tuple[str, str], str],
    statistics_paths: Mapping[str, bytes],
    *,
    compact: bool = False,
) -> bytes:
    sources = {s.source_key: s for s in archive.review.sources}
    sections = []
    index = []
    for ordinal, finding in enumerate(archive.review.findings, 1):
        index.append(f'<a href="#roi-{ordinal}">ROI {ordinal:02d}</a>')
        badges = ""
        if finding.roi_ref is not None:
            x, y, width, height = finding.roi_ref
            badges = "".join(
                f'<span class="pill">{label} <strong>{value}</strong></span>'
                for label, value in (("x", x), ("y", y), ("width", width), ("height", height))
            )
        cards = []
        for number, key in enumerate(finding.source_keys, 1):
            if (finding.id, key) not in archive.crops:
                continue
            relative = image_paths[(finding.id, key)]
            basename = html.escape(sources[key].locator.basename)
            tag = sources[key].display_tag
            tag_html = f' <span class="source-tag">· {html.escape(tag)}</span>' if tag else ""
            cards.append(
                '<figure class="crop-card"><div class="image-stage">'
                f'<img src="{_url(relative)}" alt="ROI {ordinal}, image {number}: {basename}"></div>'
                f'<figcaption class="crop-caption"><p class="source-name">{number:02d} · {basename}{tag_html}</p>'
                + ("" if compact else f'<div class="badges">{badges}</div>')
                + '<div class="crop-footer"><span class="file-type">PNG · 8-bit preview</span>'
                f'<a class="icon-button" href="{_url(relative)}" download="{html.escape(PurePosixPath(relative).name, quote=True)}" '
                f'aria-label="Download ROI {ordinal} image {number} PNG" title="Download PNG">{_DOWNLOAD_ICON}</a></div></figcaption></figure>'
            )
        csv = f"statistics/{finding.id}.csv"
        table = _statistics_table(statistics_paths[csv]) if csv in statistics_paths else ""
        psnr = _preview_psnr(
            archive, finding, {key: source.locator.basename for key, source in sources.items()}
        )
        csv_action = (
            '<div class="stat-footer">'
            f'<a class="icon-button" href="{_url(csv)}" download '
            f'title="Download ROI Statistics CSV" '
            f'aria-label="Download ROI {ordinal} Statistics CSV">{_CSV_ICON}</a></div>'
            if csv in statistics_paths
            else ""
        )
        statistics = (
            f'<div class="statistics"><h3>ROI statistics</h3>{psnr}{table}{csv_action}</div>'
            if csv in statistics_paths or psnr
            else ""
        )
        copy = (
            f'<button type="button" class="icon-button" data-copy-note title="Copy memo" aria-label="Copy memo" disabled>{_COPY_ICON}</button>'
            if finding.note
            else ""
        )
        sections.append(
            f'<section class="roi-card" id="roi-{ordinal}"><header class="roi-header"><div class="title-row">'
            f'<span class="roi-number">ROI {ordinal:02d}</span><h2>{html.escape(finding.title)}</h2></div>'
            f'<div class="badges">{badges}<span class="pill">{len(cards)} stored crops</span></div>'
            f'<div class="capture-time">Captured UTC · {html.escape(finding.captured_utc)}</div></header>'
            '<div class="content"><div class="memo"><div class="memo-heading"><span class="section-label">Memo</span>'
            f'{copy}</div><p class="note">{html.escape(finding.note)}</p><div class="copy-status" role="status" aria-live="polite"></div></div>'
            f'<div class="crop-grid">{"".join(cards) or "<p>No stored crop (legacy memo).</p>"}</div>{statistics}</div></section>'
        )
    script_hash = base64.b64encode(hashlib.sha256(_COPY_SCRIPT.encode()).digest()).decode("ascii")
    policy = (
        "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; "
        f"script-src 'sha256-{script_hash}'; base-uri 'none'; form-action 'none'"
    )
    style = _STYLE
    if compact:
        style += ".content{padding:18px 22px}.memo{margin-bottom:16px}.roi-header{padding:18px 22px}.roi-card{margin:16px 0}"
    markup = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="pixelscope-report-version" content="{7 if compact else 4}">'
        f'<meta http-equiv="Content-Security-Policy" content="{html.escape(policy, quote=True)}">'
        f'<title>PixelScope Memo</title><style>{style}</style></head><body><main>'
        '<header class="masthead"><div><div class="brand">PixelScope</div><h1>ROI inspection notes</h1>'
        '<p class="subtle">Saved 8-bit ROI previews and comparison notes</p></div><div class="summary">'
        f'<span class="pill"><strong>{len(archive.review.findings)}</strong> ROIs</span>'
        f'<span class="pill"><strong>{len(sources)}</strong> images</span></div></header>'
        f'<nav class="roi-index" aria-label="ROI index">{"".join(index)}</nav>{"".join(sections)}'
        '<footer class="footer">PixelScope · ROI inspection notebook</footer></main>'
        f'<script>{_COPY_SCRIPT}</script></body></html>'
    )
    return markup.encode("utf-8")
