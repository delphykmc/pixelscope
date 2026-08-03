from __future__ import annotations

from pathlib import Path

TARGET = Path("src/pixelscope/app/main_window.py")

OLD = '''        if show_difference and self._layout_mode != "Single View":
            assert difference_document is not None
            self._promote_multi_document(difference_document.document_id)
            display_documents = [difference_document, *documents]
'''

NEW = '''        if show_difference and self._layout_mode != "Single View":
            assert difference_document is not None
            if self._focus_document_id in (None, difference_document.document_id):
                self._promote_multi_document(difference_document.document_id)
            display_documents = [difference_document, *documents]
'''


def main() -> int:
    original = TARGET.read_text(encoding="utf-8")
    if NEW in original:
        print("P0-D focus-priority fix was already applied")
        return 0
    count = original.count(OLD)
    if count != 1:
        raise RuntimeError(f"expected one Difference promotion block, found {count}")
    TARGET.write_text(original.replace(OLD, NEW, 1), encoding="utf-8")
    print(f"Applied P0-D focus-priority fix to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
