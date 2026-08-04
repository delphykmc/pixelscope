from __future__ import annotations

from pathlib import Path

DOCUMENT_LIST = Path("src/pixelscope/ui/document_list.py")
P1A_TESTS = Path("tests/ui/test_p1a_files_statistics_header.py")
SMOKE_TESTS = Path("tests/ui/test_ui_smoke.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise RuntimeError(f"could not find {description}")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_document_list(text: str) -> str:
    old_core_import = (
        "from PySide6.QtCore import QModelIndex, QPoint, QRect, Qt, Signal\n"
    )
    new_core_import = (
        "from PySide6.QtCore import (\n"
        "    QModelIndex,\n"
        "    QPersistentModelIndex,\n"
        "    QPoint,\n"
        "    QRect,\n"
        "    Qt,\n"
        "    Signal,\n"
        ")\n"
    )
    text = replace_once(
        text,
        old_core_import,
        new_core_import,
        "document-list QtCore imports",
    )
    text = text.replace("    QWidget,\n", "", 1)
    text = replace_once(
        text,
        "        index: QModelIndex,\n",
        "        index: QModelIndex | QPersistentModelIndex,\n",
        "delegate index type",
    )
    old_accent = '''        accent = QRect(
            option.rect.left(),
            option.rect.top() + 2,
            3,
            max(0, option.rect.height() - 4),
        )
'''
    new_accent = '''        rect = getattr(option, "rect")
        accent = QRect(
            rect.left(),
            rect.top() + 2,
            3,
            max(0, rect.height() - 4),
        )
'''
    return replace_once(
        text,
        old_accent,
        new_accent,
        "delegate active-accent rectangle",
    )


def patch_p1a_tests(text: str) -> str:
    text = text.replace("from PySide6.QtCore import QSettings, Qt\n", "", 1)
    old_badges = '''    assert [
        viewer.header.badge.text() for viewer in window.multi_compare_view.occupied_viewers
    ] == ["1", "2", "3"]
'''
    new_badges = '''    visible_viewers = window.multi_compare_view.viewers[:3]
    assert [viewer.document for viewer in visible_viewers] == documents
    assert [viewer.header.badge.text() for viewer in visible_viewers] == ["1", "2", "3"]
'''
    return replace_once(
        text,
        old_badges,
        new_badges,
        "role-free tile badge assertion",
    )


def patch_smoke_tests(text: str) -> str:
    text = replace_once(
        text,
        '    assert [group.child(index).text(1) for index in range(3)] == ["", "", ""]\n',
        '    assert [group.child(index).text(1) for index in range(3)] == [\n'
        '        "PNG",\n'
        '        "PNG",\n'
        '        "PNG",\n'
        '    ]\n',
        "Files Type-column comparison expectation",
    )
    text = replace_once(
        text,
        '    assert window.document_list.topLevelItem(0).child(0).text(1) == ""\n',
        '    assert window.document_list.topLevelItem(0).child(0).text(1) == "PNG"\n',
        "Files Type-column drop expectation",
    )
    old_error = '''    assert error.loading_state == "error"
    assert window.document_list.currentItem().text(0) == "bad.png"
    assert "!" in window.document_list.currentItem().text(1)
'''
    new_error = '''    assert error.loading_state == "error"
    item = window.document_list.currentItem()
    assert item.text(0) == "bad.png"
    assert item.text(1) == "PNG"
    assert not item.icon(0).isNull()
    assert "Load failed" in item.toolTip(0)
'''
    return replace_once(
        text,
        old_error,
        new_error,
        "error-document Files presentation expectation",
    )


def patch_file(path: Path, patcher: object) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = patcher(original)  # type: ignore[operator]
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    changes = {
        DOCUMENT_LIST: patch_file(DOCUMENT_LIST, patch_document_list),
        P1A_TESTS: patch_file(P1A_TESTS, patch_p1a_tests),
        SMOKE_TESTS: patch_file(SMOKE_TESTS, patch_smoke_tests),
    }
    changed = [str(path) for path, was_changed in changes.items() if was_changed]
    print("Applied P1-A validation fix:" if changed else "P1-A validation fix already applied")
    for path in changed:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
