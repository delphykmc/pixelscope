from dataclasses import replace
from datetime import datetime

import pytest
from test_memo_archive import _notebook

from pixelscope.io import memo_report as module
from pixelscope.io.memo_archive import MemoArchive
from pixelscope.io.memo_report import report_directory, suggested_memo_name, write_memo_report


def notebook(tmp_path):
    library, _, _, crops = _notebook(tmp_path)
    return MemoArchive(library.document, crops)


def identity(png, _name, _coordinates):
    return png


def tree(path):
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in path.rglob("*") if p.is_file()}


def test_default_name_has_source_timestamp_and_windows_safe_basename(tmp_path):
    archive = notebook(tmp_path)
    source = archive.review.sources[0]
    source = replace(source, locator=replace(source.locator, basename="scene.png"))
    archive = MemoArchive(
        replace(archive.review, sources=(source, *archive.review.sources[1:])), archive.crops
    )
    assert (
        suggested_memo_name(archive, datetime(2026, 11, 12, 9, 30, 5))
        == "Memo_scene_20261112_093005.pxmemo"
    )
    assert module.safe_memo_name("bad:<name>? .") == "bad__name__"


def test_long_report_text_is_preserved_with_crop_paths_and_note_line_breaks(tmp_path):
    archive = notebook(tmp_path)
    title = "Inspection_" + "unbroken_identifier_" * 8
    note = "First line\n" + "LongUnbrokenToken" * 30 + "\n<script>literal</script>"
    first = replace(archive.review.findings[0], title=title, note=note)
    updated = MemoArchive(
        replace(archive.review, findings=(first, *archive.review.findings[1:])), archive.crops
    )
    folder = write_memo_report(tmp_path / "long.pxmemo", updated, "long-text", identity)
    report = (folder / "index.html").read_text(encoding="utf-8")
    assert title in report and note.replace("<", "&lt;").replace(">", "&gt;") in report
    assert len(list((folder / "images").glob("*.png"))) == len(archive.crops)
    assert dict(updated.crops) == dict(archive.crops)


def test_report_is_ready_to_use_with_named_images_coordinates_and_no_private_record(tmp_path):
    archive = notebook(tmp_path)
    target = tmp_path / "notes.pxmemo"
    folder = write_memo_report(target, archive, "revision", identity)
    assert folder == report_directory(target)
    report = (folder / "index.html").read_text(encoding="utf-8")
    assert "source0.raw" in report and "width <strong>" in report and "height <strong>" in report
    assert "&lt;script&gt;" in report and "<script>alert(1)</script>" not in report
    assert "review.json" not in tree(folder)
    assert str(tmp_path) not in report
    pngs = list((folder / "images").glob("*.png"))
    assert len(pngs) == len(archive.crops)
    assert all("_x" in p.name and "_w" in p.name and "source" in p.name for p in pngs)
    assert not target.exists()  # Folder writer never mutates the canonical archive.


def test_resave_replaces_only_unmodified_owned_report_and_removes_deleted_roi(tmp_path):
    archive = notebook(tmp_path)
    path = tmp_path / "notes.pxmemo"
    folder = write_memo_report(path, archive, "first", identity)
    kept = archive.review.findings[:1]
    updated = MemoArchive(
        replace(archive.review, findings=kept),
        {key: data for key, data in archive.crops.items() if key[0] == kept[0].id},
    )
    write_memo_report(path, updated, "second", identity)
    assert len(list((folder / "images").glob("*.png"))) == len(updated.crops)
    assert "second" in (folder / module._MARKER).read_text()
    assert not list(tmp_path.glob(".memo-report-*"))


@pytest.mark.parametrize(
    "change", ["unowned", "edited", "added", "bad-marker", "nested-marker", "empty-directory"]
)
def test_report_refuses_to_overwrite_foreign_or_edited_files(tmp_path, change):
    archive = notebook(tmp_path)
    path = tmp_path / "notes.pxmemo"
    folder = write_memo_report(path, archive, "first", identity)
    if change == "unowned":
        (folder / module._MARKER).unlink()
    elif change == "edited":
        (folder / "index.html").write_text("Owner's edited report")
    elif change == "bad-marker":
        (folder / module._MARKER).write_text("[]")
    elif change == "nested-marker":
        (folder / "images" / module._MARKER).write_text("user content")
    elif change == "empty-directory":
        (folder / "my-work").mkdir()
    else:
        (folder / "my-report.docx").write_bytes(b"user work")
    before = tree(folder)
    with pytest.raises(FileExistsError):
        write_memo_report(path, archive, "second", identity)
    assert tree(folder) == before
    if change == "empty-directory":
        assert (folder / "my-work").is_dir()


def test_failed_publication_restores_old_report_and_cleans_stage(tmp_path, monkeypatch):
    archive = notebook(tmp_path)
    path = tmp_path / "notes.pxmemo"
    folder = write_memo_report(path, archive, "first", identity)
    before = tree(folder)
    original = module.os.rename

    def fail_install(source, destination):
        if source.name.startswith(".memo-report-") and not source.name.endswith("-previous"):
            raise OSError("simulated publish failure")
        return original(source, destination)

    monkeypatch.setattr(module.os, "rename", fail_install)
    with pytest.raises(OSError, match="simulated"):
        write_memo_report(path, archive, "second", identity)
    assert tree(folder) == before
    assert not list(tmp_path.glob(".memo-report-*"))


@pytest.mark.parametrize("changed", ["index.html", module._MARKER])
def test_edit_during_rename_is_preserved_in_restored_report(tmp_path, monkeypatch, changed):
    archive = notebook(tmp_path)
    path = tmp_path / "notes.pxmemo"
    folder = write_memo_report(path, archive, "first", identity)
    original = module.os.rename

    def edit_after_move(source, destination):
        result = original(source, destination)
        if source == folder:
            (destination / changed).write_text("external edit during save")
        return result

    monkeypatch.setattr(module.os, "rename", edit_after_move)
    with pytest.raises((FileExistsError, ValueError)):
        write_memo_report(path, archive, "second", identity)
    assert (folder / changed).read_text() == "external edit during save"
    assert not list(tmp_path.glob(".memo-report-*"))


def test_report_actions_are_scoped_and_script_is_hash_pinned(tmp_path):
    import base64
    import hashlib
    from html.parser import HTMLParser

    from pixelscope.io.memo_archive import memo_html

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []
            self.scripts = []
            self.in_script = False

        def handle_starttag(self, tag, attrs):
            self.tags.append((tag, dict(attrs)))
            self.in_script = tag == "script"

        def handle_endtag(self, tag):
            if tag == "script":
                self.in_script = False

        def handle_data(self, data):
            if self.in_script:
                self.scripts.append(data)

    archive = notebook(tmp_path)
    markup = memo_html(archive).decode()
    parsed = Elements()
    parsed.feed(markup)
    assert len(parsed.scripts) == 1
    script = parsed.scripts[0]
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    policy = next(
        attrs["content"]
        for tag, attrs in parsed.tags
        if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy"
    )
    assert f"script-src 'sha256-{digest}'" in policy
    assert "script-src 'unsafe-inline'" not in policy
    assert "alert(1)" not in script
    assert all(not key.startswith("on") for _, attrs in parsed.tags for key in attrs)
    assert all("src" not in attrs for tag, attrs in parsed.tags if tag == "script")
    images = [attrs["src"] for tag, attrs in parsed.tags if tag == "img"]
    crop_buttons = [
        attrs
        for tag, attrs in parsed.tags
        if tag == "button" and attrs.get("aria-label", "").startswith("Open ROI")
    ]
    assert [attrs["data-open-report-asset"] for attrs in crop_buttons] == images
    assert len(images) == len(archive.crops)
    assert all(attrs.get("type") == "button" and "href" not in attrs for attrs in crop_buttons)
    assert not [
        attrs
        for tag, attrs in parsed.tags
        if tag == "a" and attrs.get("aria-label", "").startswith("Open ROI")
    ]
    folder_buttons = [
        attrs
        for tag, attrs in parsed.tags
        if tag == "button" and attrs.get("class") == "icon-button source-folder-link"
    ]
    assert len(folder_buttons) == 1
    assert folder_buttons[0]["data-open-report-asset"] == "images/"
    assert folder_buttons[0]["type"] == "button"
    assert markup.index('class="report-tools"') < markup.index('class="roi-card"')
    assert "window.open(new URL(relative, document.baseURI).href" in script
    assert "'_blank', 'noopener,noreferrer'" in script
    assert markup.count('class="crop-card"') == len(archive.crops)
    assert 'name="pixelscope-report-version" content="9"' in markup
    assert '<svg viewBox="0 0 24 24" aria-hidden="true">' in markup
    assert markup.count("width <strong>") == len(archive.review.findings)
    assert markup.count("height <strong>") == len(archive.review.findings)
    assert sum(tag == "button" and "data-copy-note" in attrs for tag, attrs in parsed.tags) == sum(
        bool(f.note) for f in archive.review.findings
    )
    assert "button.closest('.memo')" in script
    assert "addEventListener('click'" in script


def test_statistics_table_preserves_saved_values_and_escapes_text():
    from pixelscope.io.memo_html_presentation import _statistics_table

    data = (
        b"Source,Image,Channel,Metric,Value,State,Samples,Domain,"
        b"Native dtype,Effective bits,Definition\n"
        b"1,<img onerror=alert(1)>,R,Mean,23.125,finite,20,native,uint16,12,native-v1\n"
    )
    table = _statistics_table(data)
    assert '<table class="stat-table">' in table and '<th scope="col">Mean</th>' in table
    assert "23.125" in table
    assert "uint16" not in table and "native-v1" not in table
    assert b"uint16" in data and b"native-v1" in data
    assert "&lt;img onerror=alert(1)&gt;" in table and "<img " not in table


def test_statistics_pivots_seven_metrics_and_compares_rgb_means():
    import csv
    import io

    from pixelscope.io.memo_html_presentation import _statistics_table

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        (
            "Source",
            "Image",
            "Channel",
            "Metric",
            "Value",
            "State",
            "Samples",
            "Domain",
            "Native dtype",
            "Effective bits",
            "Definition",
        )
    )
    values = {"R": (10, 12), "G": (20, 19), "B": (30, 30)}
    for source in (1, 2):
        for channel, pair in values.items():
            for metric in ("Min", "Max", "Mean", "Std", "P1", "P50", "P99"):
                writer.writerow(
                    (
                        source,
                        f"image{source}.raw",
                        channel,
                        metric,
                        pair[source - 1],
                        "finite",
                        40,
                        "native",
                        "uint8",
                        8,
                        "native-v1",
                    )
                )
    table = _statistics_table(output.getvalue().encode())
    assert table.count('<table class="stat-table">') == 1
    assert table.count('<th scope="col">Mean</th>') == 1
    assert table.count('<th scope="col">P99</th>') == 1
    assert table.count("<tr class=") == 6  # R 01/02, G 01/02, B 01/02
    assert 'rowspan="2"' in table
    assert "↑ Δ +2" in table and "↓ Δ -1" in table and "→ Δ 0" in table
    assert 'class="stat-change stat-up"' in table
    assert 'class="stat-change stat-down"' in table
    assert "image1.raw" in table and "image2.raw" in table
    assert "RGB mean comparison" not in table


def test_rgb_difference_refuses_cross_bitdepth_native_comparison():
    from pixelscope.io.memo_html_presentation import _statistics_table

    data = (
        b"Source,Image,Channel,Metric,Value,State,Samples,Domain,"
        b"Native dtype,Effective bits,Definition\n"
        b"1,first,R,Mean,127,finite,16,native,uint8,8,native-v1\n"
        b"2,second,R,Mean,512,finite,16,native,uint16,10,native-v1\n"
    )
    report = _statistics_table(data)
    assert "Δ n/a" in report
    assert "Δ +385" not in report


def test_statistics_rounding_and_all_metric_deltas_without_changing_csv():
    from pixelscope.io.memo_html_presentation import _statistics_table

    columns = (
        "Source,Image,Channel,Metric,Value,State,Samples,Domain,"
        "Native dtype,Effective bits,Definition"
    )
    raw = "\n".join(
        [
            columns,
            "1,a,R,Mean,1.1234567,finite,20,native,uint16,12,native-v1",
            "2,b,R,Mean,2.9876543,finite,20,native,uint16,12,native-v1",
            "1,a,R,Std,0.1234567,finite,20,native,uint16,12,native-v1",
            "2,b,R,Std,0.2234567,finite,20,native,uint16,12,native-v1",
            "1,a,R,P99,14.9999999,finite,20,native,uint16,12,native-v1",
            "2,b,R,P99,13.9999999,finite,20,native,uint16,12,native-v1",
        ]
    ).encode()
    html = _statistics_table(raw)
    assert "1.1235" in html and "2.9877" in html
    assert "1.1234567" not in html and "2.9876543" not in html
    assert "↑ Δ +1.8642" in html  # Mean delta, not only mean heatmap
    assert "↑ Δ +0.1" in html  # Std delta
    assert "↓ Δ -1" in html  # P99 delta
    assert raw.endswith(b"native-v1")


def test_preview_psnr_uses_stored_8bit_pixels_only_and_handles_missing_types():
    import math

    import cv2
    import numpy as np
    from test_memo_archive import _png

    from pixelscope.io.memo_preview_metrics import psnr_8bit_png

    reference = _png((0, 0, 2, 2), 50)
    same = _png((0, 0, 2, 2), 50)
    plus_ten = _png((0, 0, 2, 2), 60)
    assert psnr_8bit_png(reference, same) == math.inf
    assert psnr_8bit_png(reference, plus_ten) == pytest.approx(20 * math.log10(255.0 / 10.0))
    assert psnr_8bit_png(reference, _png((0, 0, 3, 2), 60)) is None
    assert psnr_8bit_png(reference, b"not a png") is None
    rgba = np.zeros((2, 2, 4), dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", rgba)
    assert ok
    assert psnr_8bit_png(reference, encoded.tobytes()) is None


def test_generated_report_has_one_channel_table_csv_icon_right_and_preview_psnr(tmp_path):
    from pixelscope.io.memo_html_presentation import render_memo_report

    archive = notebook(tmp_path)
    finding = archive.review.findings[0]
    first, second = finding.source_keys
    columns = (
        "Source,Image,Channel,Metric,Value,State,Samples,Domain,"
        "Native dtype,Effective bits,Definition\n"
    )
    csv = (
        columns
        + "1,first,R,Mean,50,finite,4,native,uint8,8,native-v1\n"
        + "2,second,R,Mean,51,finite,4,native,uint8,8,native-v1\n"
    ).encode()
    paths = {
        (finding.id, first): "images/first.png",
        (finding.id, second): "images/second.png",
    }
    only_first = MemoArchive(
        replace(archive.review, findings=(finding,)),
        {key: data for key, data in archive.crops.items() if key[0] == finding.id},
    )
    report = render_memo_report(
        only_first, paths, {f"statistics/{finding.id}.csv": csv}, compact=True
    ).decode()
    assert report.count('<table class="stat-table">') == 1
    assert 'class="stat-footer"' in report and "justify-content:flex-end" in report
    assert 'aria-label="Download ROI 1 Statistics CSV"' in report
    assert 'title="Download ROI Statistics CSV"' in report
    assert 'href="statistics/' in report
    assert "8-bit Preview PSNR" in report and "48.1308 dB" in report
    assert report.index("8-bit Preview PSNR") < report.index('<table class="stat-table">')
    assert "Native Statistics" not in report
    assert "8-bit Preview PSNR" in report
    assert 'aria-label="Image 01 vs 02' in report
    assert 'class="stat-psnr-note"' in report
    assert 'class="stat-head"' in report
    assert '<h3>ROI statistics</h3><div class="stat-psnr">' in report
    assert ".stat-psnr{display:grid;" in report
    assert "background:#eef0ff;border:1px solid #c9d0ff" in report
    assert "font-variant-numeric:tabular-nums;color:#3949ab}" in report
    assert "background:#f7fafd;border:1px solid #dfe8f4" not in report
    assert ".copy-status:empty{display:none}" in report
    assert ".stat-table-box{margin:0 0 4px" in report
    assert "Stored 8-bit crop · pixel-aligned · peak 255" in report
    assert "Image 01 reference · not native RAW PSNR" in report
    assert ">01 vs 02 ·" not in report
    assert "colored arrows show numerical increase" not in report
    assert "Values rounded for display only." not in report
    assert "native-v1</p>" not in report
    assert csv.endswith(b"native-v1\n")  # Original evidence is not reformatted.
