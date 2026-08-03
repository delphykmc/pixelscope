from __future__ import annotations

from pathlib import Path

MAIN_WINDOW = Path("src/pixelscope/app/main_window.py")
SMOKE_TEST = Path("tests/ui/test_ui_smoke.py")


MAIN_OLD = '''        if show_difference and self._layout_mode != "Single View":
            assert difference_document is not None
            display_documents = [difference_document, *documents]
'''
MAIN_NEW = '''        if show_difference and self._layout_mode != "Single View":
            assert difference_document is not None
            self._promote_multi_document(difference_document.document_id)
            display_documents = [difference_document, *documents]
'''

THREE_DIFF_OLD = '''    assert [viewer.document for viewer in window.multi_compare_view.occupied_viewers] == [
        *documents,
        window._difference_document,
    ]
'''
THREE_DIFF_NEW = '''    assert [viewer.document for viewer in window.multi_compare_view.occupied_viewers] == [
        window._difference_document,
        *documents,
    ]
'''

SINGLE_WAIT_OLD = '''    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.central_stack.currentWidget() is window.multi_compare_view
        and window.multi_compare_view.viewers[0].document is window._difference_document,
        timeout=3000,
    )
'''
SINGLE_WAIT_NEW = '''    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.central_stack.currentWidget() is window.viewer
        and window.viewer.document is window._difference_document,
        timeout=3000,
    )
'''

SINGLE_LAYOUT_OLD = '''    assert window._layout_mode == "Multi View"
    window.set_layout_mode("Single View")
    window._navigate_single_view("difference")
'''
SINGLE_LAYOUT_NEW = '''    assert window._layout_mode == "Single View"
    window._navigate_single_view("difference")
'''

FOLDER_FOCUS_OLD = '''    assert window._focus_document_id == window.selected_documents[1].document_id
    assert window.multi_compare_view.viewers[0].document is window.selected_documents[1]
'''
FOLDER_FOCUS_NEW = '''    assert window._difference_document is not None
    assert window._focus_document_id == window._difference_document.document_id
    assert window.multi_compare_view.viewers[0].document is window._difference_document
'''


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, replacements: tuple[tuple[str, str, str], ...]) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = original
    for old, new, description in replacements:
        updated = replace_once(updated, old, new, description)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    changed_main = patch_file(
        MAIN_WINDOW,
        ((MAIN_OLD, MAIN_NEW, "multi-view Difference promotion block"),),
    )
    changed_tests = patch_file(
        SMOKE_TEST,
        (
            (THREE_DIFF_OLD, THREE_DIFF_NEW, "three-image Difference order assertion"),
            (SINGLE_WAIT_OLD, SINGLE_WAIT_NEW, "Single View Difference wait condition"),
            (SINGLE_LAYOUT_OLD, SINGLE_LAYOUT_NEW, "Single View Difference layout assertion"),
            (FOLDER_FOCUS_OLD, FOLDER_FOCUS_NEW, "folder Difference focus assertion"),
        ),
    )
    if changed_main or changed_tests:
        print("Applied P0-D follow-up implementation and smoke-test updates")
    else:
        print("P0-D follow-up fix was already applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
