import json
from dataclasses import replace

import pytest
from test_memo_archive import _notebook

from pixelscope.io import memo_folder as module
from pixelscope.io.memo_archive import MemoArchive, load_memo_archive


def notebook_setup(tmp_path):
    library, _, _, crops = _notebook(tmp_path)
    return tmp_path / "notes" / "notes.pxmemo", MemoArchive(library.document, crops)


def render(data, _name, _coordinates):
    return data


def test_metadata_only_folder_roundtrip_move_and_update(tmp_path):
    path, archive = notebook_setup(tmp_path)
    revision = module.save_folder_memo(path, archive, None, render)
    obj = json.loads(path.read_bytes())
    assert obj["kind"] == module.KIND and "base64" not in path.read_text()
    assert all(name.startswith("src/") or name == "index.html" for name in obj["assets"])
    assert (path.parent / "index.html").is_file()
    loaded, actual = load_memo_archive(path)
    assert dict(loaded.crops) == dict(archive.crops) and actual == revision
    moved = tmp_path / "relocated"
    path.parent.rename(moved)
    path = moved / path.name
    assert load_memo_archive(path)[1] == revision
    edited = replace(
        archive.review,
        findings=(replace(archive.review.findings[0], note="edited"), *archive.review.findings[1:]),
    )
    new_revision = module.save_folder_memo(
        path, MemoArchive(edited, archive.crops), revision, render
    )
    assert new_revision != revision
    assert load_memo_archive(path)[0].review.findings[0].note == "edited"


@pytest.mark.parametrize("change", ["asset", "foreign", "revision", "directory"])
def test_changed_or_foreign_folder_is_not_overwritten(tmp_path, change):
    path, archive = notebook_setup(tmp_path)
    revision = module.save_folder_memo(path, archive, None, render)
    if change == "asset":
        (path.parent / "index.html").write_text("user edit")
    elif change == "foreign":
        (path.parent / "user.txt").write_text("keep")
    elif change == "directory":
        (path.parent / "my-work").mkdir()
    else:
        revision = "wrong"
    before = {p: p.read_bytes() for p in path.parent.rglob("*") if p.is_file()}
    with pytest.raises((OSError, ValueError)):
        module.save_folder_memo(path, archive, revision, render)
    assert all(p.read_bytes() == data for p, data in before.items())


def test_failed_publication_restores_previous_generation(tmp_path, monkeypatch):
    path, archive = notebook_setup(tmp_path)
    revision = module.save_folder_memo(path, archive, None, render)
    rename = module.os.rename

    def fail(source, target):
        if source.name == "notes" and source.parent.name.startswith(".memo-report-"):
            raise OSError("publish failed")
        return rename(source, target)

    monkeypatch.setattr(module.os, "rename", fail)
    with pytest.raises(OSError, match="publish failed"):
        module.save_folder_memo(path, archive, revision, render)
    assert load_memo_archive(path)[1] == revision
    assert not list(tmp_path.glob(".memo-report-*"))


def test_failed_rollback_retains_recoverable_previous_copy(tmp_path, monkeypatch):
    path, archive = notebook_setup(tmp_path)
    revision = module.save_folder_memo(path, archive, None, render)
    rename = module.os.rename

    def fail(source, target):
        if source.name == "previous" or (
            source.name == "notes" and source.parent.name.startswith(".memo-report-")
        ):
            raise OSError("cannot install or restore")
        return rename(source, target)

    monkeypatch.setattr(module.os, "rename", fail)
    with pytest.raises(OSError, match="recovery copy retained"):
        module.save_folder_memo(path, archive, revision, render)
    previous = list(tmp_path.glob(".memo-report-*/previous/notes.pxmemo"))
    assert len(previous) == 1
    assert load_memo_archive(previous[0])[1] == revision


@pytest.mark.parametrize(
    "relative", ["../outside.png", "src/../../outside.png", "C:/outside.png", "src\\outside.png"]
)
def test_metadata_cannot_escape_its_folder(tmp_path, relative):
    path, archive = notebook_setup(tmp_path)
    module.save_folder_memo(path, archive, None, render)
    obj = json.loads(path.read_bytes())
    obj["assets"][relative] = "0" * 64
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError, match="relative asset"):
        load_memo_archive(path)
