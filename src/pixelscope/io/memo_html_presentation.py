# ruff: noqa: E501  # Keep trusted HTML/CSS/JavaScript template fragments together.
"""Offline report presentation. No source loading or numerical computation."""
from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import quote

if TYPE_CHECKING:
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
    button.textContent = copied ? 'Copied' : 'Copy memo';
    button.disabled = false;
    window.setTimeout(() => { button.textContent = 'Copy memo'; }, 1600);
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
"""


def _url(value: str) -> str:
    return html.escape(quote(value, safe="/"), quote=True)


def _statistics_table(data: bytes) -> str:
    """Present the saved CSV values verbatim; never recalculate statistics."""
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    columns = ("Channel", "Metric", "Value", "Samples", "State")
    headings = (
        '<th scope="col">Image</th>'
        + "".join(f'<th scope="col">{html.escape(name)}</th>' for name in columns)
        + '<th scope="col">Native context</th>'
    )
    body_rows = []
    for row in rows:
        image = f'<td class="stat-source"><strong>{html.escape(row.get("Source", ""))}</strong> · {html.escape(row.get("Image", ""))}</td>'
        cells = "".join(
            f'<td class="numeric">{html.escape(row.get(name, ""))}</td>' for name in columns
        )
        context = "<br>".join(
            html.escape(row.get(name, "")) for name in ("Domain", "Native dtype", "Definition")
        )
        context += f'<br>{html.escape(row.get("Effective bits", ""))} effective bits'
        body_rows.append(f"<tr>{image}{cells}<td>{context}</td></tr>")
    body = "".join(body_rows)
    return f'<div class="table-scroll" role="region" aria-label="Saved ROI statistics" tabindex="0"><table><thead><tr>{headings}</tr></thead><tbody>{body}</tbody></table></div>'


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
                '<figure><div class="image-stage">'
                f'<img src="{_url(relative)}" alt="ROI {ordinal}, image {number}: {basename}"></div>'
                f'<figcaption class="crop-caption"><p class="source-name">{number:02d} · {basename}{tag_html}</p>'
                + ("" if compact else f'<div class="badges">{badges}</div>')
                + '<div class="crop-footer"><span class="file-type">PNG · 8-bit preview</span>'
                f'<a class="button" href="{_url(relative)}" download="{html.escape(PurePosixPath(relative).name, quote=True)}" '
                f'aria-label="Download ROI {ordinal} image {number} PNG">Download PNG</a></div></figcaption></figure>'
            )
        csv = f"statistics/{finding.id}.csv"
        table = _statistics_table(statistics_paths[csv]) if csv in statistics_paths else ""
        statistics = (
            f'<div class="statistics"><h3>ROI statistics</h3>{table}<a class="button" href="{_url(csv)}" download>ROI Statistics CSV</a></div>'
            if csv in statistics_paths
            else ""
        )
        copy = (
            '<button type="button" class="button" data-copy-note disabled>Copy memo</button>'
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
        style += "figure{border:0;border-radius:0;background:transparent}.image-stage{padding:0;min-height:0;background:transparent}.crop-caption{padding:8px 0 0}.source-name{margin:0;font-size:12px}.crop-footer{margin-top:5px}.crop-grid{gap:14px}.content{padding:18px 22px}.memo{margin-bottom:16px}.roi-header{padding:18px 22px}.roi-card{margin:16px 0}"
    markup = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="pixelscope-report-version" content="{5 if compact else 4}">'
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
