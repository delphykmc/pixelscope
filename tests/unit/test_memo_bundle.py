"""Qt-free Memo archive: multiple ROIs, deletion, offline HTML and safety."""
from __future__ import annotations

import base64
import zipfile
from pathlib import Path

import pytest

from pixelscope.io.memo_bundle import (
    MemoCrop,
    MemoRegion,
    export_memo_html_directory,
    open_memo_bundle,
    save_memo_bundle,
)

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/fJkAAAAASUVORK5CYII="
)


def _note(identifier: str, x: int, title: str = "<halo>") -> MemoRegion:
    return MemoRegion(
        region_id=identifier,
        title=title,
        note="<script>not executed</script>\nOriginal may be missing.",
        roi=(x, 2, 1, 1),
        crops=(MemoCrop("source-1", "sensor A", PNG_1X1),),
        center=(100.0 + x, 45.0),
        physical_zoom=1.0,
    )


def test_two_distinct_regions_survive_reopen_with_original_removed(tmp_path: Path) -> None:
    archive = tmp_path / "inspection.pxmemo"
    save_memo_bundle(
        archive,
        (_note("one", 10), _note("two", 20)),
        local_sources={"source-1": "C:/private/original.raw"},
    )
    loaded = open_memo_bundle(archive)
    assert [r.roi for r in loaded.regions] == [(10, 2, 1, 1), (20, 2, 1, 1)]
    assert all(r.crops[0].png_bytes == PNG_1X1 for r in loaded.regions)
    assert loaded.local_sources["source-1"] == "C:/private/original.raw"
    with zipfile.ZipFile(archive) as z:
        html = z.read("index.html").decode("utf-8")
        assert "C:/private" not in html
        assert "<script>not executed</script>" not in html
        assert "&lt;script&gt;" in html
        assert len([n for n in z.namelist() if n.startswith("images/")]) == 2


def test_rebuild_after_deleting_a_region_excludes_its_crop(tmp_path: Path) -> None:
    first = tmp_path / "before.pxmemo"
    second = tmp_path / "after.pxmemo"
    save_memo_bundle(first, (_note("one", 10), _note("two", 20)))
    save_memo_bundle(second, (_note("two", 20),))
    assert len(open_memo_bundle(first).regions) == 2
    assert [r.region_id for r in open_memo_bundle(second).regions] == ["two"]
    with zipfile.ZipFile(second) as archive:
        assert len([n for n in archive.namelist() if n.startswith("images/")]) == 1


def test_html_export_is_portable_and_private_path_free(tmp_path: Path) -> None:
    bundle = tmp_path / "inspection.pxmemo"
    save_memo_bundle(bundle, (_note("one", 10),), local_sources={"source-1": "/private/source.png"})
    output = export_memo_html_directory(bundle, tmp_path / "report")
    markup = (output / "index.html").read_text(encoding="utf-8")
    assert "/private/source.png" not in markup
    assert "&lt;halo&gt;" in markup
    assert len(list((output / "images").glob("*.png"))) == 1
    with pytest.raises(FileExistsError):
        export_memo_html_directory(bundle, output)


def test_no_silent_overwrite_and_invalid_crop_rejected(tmp_path: Path) -> None:
    path = tmp_path / "notes.pxmemo"
    save_memo_bundle(path, (_note("one", 10),))
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        save_memo_bundle(path, (_note("two", 20),))
    assert path.read_bytes() == original
    broken = MemoRegion("bad", "bad", "", (1, 2, 2, 2), (MemoCrop("a", "A", PNG_1X1),))
    with pytest.raises(ValueError, match="dimensions"):
        save_memo_bundle(tmp_path / "broken.pxmemo", (broken,))


def test_reject_unexpected_zip_member(tmp_path: Path) -> None:
    path = tmp_path / "tampered.pxmemo"
    save_memo_bundle(path, (_note("one", 10),))
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("../outside.txt", b"unexpected")
    with pytest.raises(ValueError, match="unsafe"):
        open_memo_bundle(path)
