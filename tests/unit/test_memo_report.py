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
    downloads = [
        attrs["href"]
        for tag, attrs in parsed.tags
        if tag == "a" and attrs.get("aria-label", "").startswith("Download ROI")
    ]
    assert downloads == images and len(images) == len(archive.crops)
    assert markup.count('class="crop-card"') == len(archive.crops)
    assert 'name="pixelscope-report-version" content="6"' in markup
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
    assert "<table>" in table and '<th scope="col">Mean</th>' in table
    assert "23.125" in table and "uint16" in table and "native-v1" in table
    assert "&lt;img onerror=alert(1)&gt;" in table and "<img " not in table


def test_statistics_pivots_seven_metrics_and_compares_rgb_means():
    import csv
    import io

    from pixelscope.io.memo_html_presentation import _statistics_table

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("Source", "Image", "Channel", "Metric", "Value", "State", "Samples",
                     "Domain", "Native dtype", "Effective bits", "Definition"))
    values = {"R": (10, 12), "G": (20, 19), "B": (30, 30)}
    for source in (1, 2):
        for channel, pair in values.items():
            for metric in ("Min", "Max", "Mean", "Std", "P1", "P50", "P99"):
                writer.writerow((source, f"image{source}.raw", channel, metric,
                                 pair[source - 1], "finite", 40, "native", "uint8", 8, "native-v1"))
    table = _statistics_table(output.getvalue().encode())
    assert table.count('<th scope="col">Mean</th>') == 2
    assert table.count('<th scope="col">P99</th>') == 2
    assert table.count('<tr><th scope="row"') == 6  # RGB once per image, not 42 metric rows
    assert "Δ +2" in table and "Δ -1" in table and "Δ +0" in table
    assert "image1.raw" in table and "image2.raw" in table
    assert "RGB mean comparison" in table


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
