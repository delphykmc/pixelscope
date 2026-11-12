import ctypes
import json
import os
from dataclasses import replace

import pytest
from test_memo_archive import _notebook

from pixelscope.io import memo_folder as module
from pixelscope.io.memo_archive import MemoArchive, load_memo_archive


def notebook_setup(tmp_path):
    library, _, _, crops = _notebook(tmp_path)
    return tmp_path / "notes" / "notes.pxmemo", MemoArchive(library.document, crops)


@pytest.mark.skipif(os.name != "nt", reason="Windows directory sharing contract")
@pytest.mark.parametrize("locked", ["directory", "index.html", "crop"])
def test_resave_while_output_directory_is_open_without_delete_share(tmp_path, locked):
    path, archive = notebook_setup(tmp_path)
    revision = module.save_folder_memo(path, archive, None).revision
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
    ]
    create.restype = ctypes.c_void_p
    close = kernel.CloseHandle
    close.argtypes = [ctypes.c_void_p]
    target = (
        path.parent
        if locked == "directory"
        else (
            next((path.parent / "src/crops").glob("*.png"))
            if locked == "crop"
            else path.parent / locked
        )
    )
    handle = create(
        str(target),
        0x80000000,
        0x1 if locked == "crop" else 0x1 | 0x2,
        None,
        3,
        0x02000000 if locked == "directory" else 0x80,
        None,
    )
    assert handle not in (None, ctypes.c_void_p(-1).value), ctypes.get_last_error()
    try:
        edited = replace(
            archive.review,
            findings=(
                replace(archive.review.findings[0], note="edited with open directory"),
                *archive.review.findings[1:],
            ),
        )
        result = module.save_folder_memo(path, MemoArchive(edited, archive.crops), revision)
        assert load_memo_archive(path)[1] == result.revision
    finally:
        close(handle)


def test_metadata_only_folder_roundtrip_move_and_update(tmp_path):
    path, archive = notebook_setup(tmp_path)
    revision = module.save_folder_memo(path, archive, None).revision
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
        path, MemoArchive(edited, archive.crops), revision
    ).revision
    assert new_revision != revision
    assert load_memo_archive(path)[0].review.findings[0].note == "edited"


@pytest.mark.parametrize("change", ["asset", "foreign", "revision", "directory"])
def test_changed_or_foreign_folder_is_not_overwritten(tmp_path, change):
    path, archive = notebook_setup(tmp_path)
    revision = module.save_folder_memo(path, archive, None).revision
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
        module.save_folder_memo(path, archive, revision)
    assert all(p.read_bytes() == data for p, data in before.items())


def test_failed_publication_restores_previous_generation(tmp_path, monkeypatch):
    path, archive = notebook_setup(tmp_path)
    revision = module.save_folder_memo(path, archive, None).revision
    replace_file = module.os.replace
    edited = MemoArchive(
        replace(
            archive.review,
            findings=tuple(replace(f, note="changed") for f in archive.review.findings),
        ),
        archive.crops,
    )

    def fail(source, target):
        if target == path:
            raise OSError("publish failed")
        return replace_file(source, target)

    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError, match="publish failed"):
        module.save_folder_memo(path, edited, revision)
    assert load_memo_archive(path)[1] == revision
    assert not list(tmp_path.glob(".memo-report-*"))


def test_failed_rollback_retains_recoverable_previous_copy(tmp_path, monkeypatch):
    path, archive = notebook_setup(tmp_path)
    revision = module.save_folder_memo(path, archive, None).revision
    replace_data = module._replace_data
    old_html = (path.parent / "index.html").read_bytes()
    edited = MemoArchive(
        replace(
            archive.review,
            findings=tuple(replace(f, note="changed") for f in archive.review.findings),
        ),
        archive.crops,
    )

    def fail(destination, data, temporary):
        if destination == path or (destination.name == "index.html" and data == old_html):
            raise OSError("cannot install or restore")
        return replace_data(destination, data, temporary)

    monkeypatch.setattr(module, "_replace_data", fail)
    with pytest.raises(OSError, match="recovery copy retained"):
        module.save_folder_memo(path, edited, revision)
    previous = list(tmp_path.glob(".memo-report-*/previous/notes.pxmemo"))
    assert len(previous) == 1
    assert load_memo_archive(previous[0])[1] == revision


@pytest.mark.parametrize(
    "relative", ["../outside.png", "src/../../outside.png", "C:/outside.png", "src\\outside.png"]
)
def test_metadata_cannot_escape_its_folder(tmp_path, relative):
    path, archive = notebook_setup(tmp_path)
    module.save_folder_memo(path, archive, None)
    obj = json.loads(path.read_bytes())
    obj["assets"][relative] = "0" * 64
    path.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ValueError, match="relative asset"):
        load_memo_archive(path)


@pytest.mark.parametrize("name", ["previous", "presentation_report", "next"])
def test_user_folder_name_cannot_collide_with_internal_staging(tmp_path, name):
    _, archive = notebook_setup(tmp_path)
    path = tmp_path / name / f"{name}.pxmemo"
    revision = module.save_folder_memo(path, archive, None).revision
    module.save_folder_memo(path, archive, revision)
    assert load_memo_archive(path)[0].review == archive.review


@pytest.mark.parametrize("existing", [False, True])
def test_cleanup_failure_keeps_committed_revision_and_allows_retry(tmp_path, monkeypatch, existing):
    path, archive = notebook_setup(tmp_path)
    old_revision = module.save_folder_memo(path, archive, None).revision if existing else None
    cleanup = module._remove_staging

    def fail_cleanup(*_args):
        raise PermissionError("backup held open")

    with monkeypatch.context() as patch:
        patch.setattr(module, "_remove_staging", fail_cleanup)
        result = module.save_folder_memo(path, archive, old_revision)
    assert "cleanup pending" in result.cleanup_warning
    assert load_memo_archive(path)[1] == result.revision
    retry = module.save_folder_memo(path, archive, result.revision)
    assert not retry.cleanup_warning
    assert load_memo_archive(path)[1] == retry.revision
    assert cleanup is module._remove_staging
