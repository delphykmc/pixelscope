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


def test_report_is_ready_to_use_with_named_images_coordinates_and_no_private_record(tmp_path):
    archive = notebook(tmp_path)
    target = tmp_path / "notes.pxmemo"
    folder = write_memo_report(target, archive, "revision", identity)
    assert folder == report_directory(target)
    report = (folder / "index.html").read_text(encoding="utf-8")
    assert "source0.raw" in report and "width=" in report and "height=" in report
    assert "&lt;script&gt;" in report and "<script>" not in report
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
