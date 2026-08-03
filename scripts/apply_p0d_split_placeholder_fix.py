from __future__ import annotations

from pathlib import Path

TARGET = Path("src/pixelscope/ui/image_viewer.py")

OLD = '''        if document.preview is None:
            self._pending_document = document
            if previous is None or previous.preview is None:
                self._document = None
                self.image_item.clear()
                self._displayed_preview = None
'''

NEW = '''        if document.preview is None:
            self._pending_document = document
            clear_previous = document.channel_layout.startswith("CHANNEL_")
            if clear_previous or previous is None or previous.preview is None:
                self._document = None
                self.image_item.clear()
                self._displayed_preview = None
'''


def main() -> int:
    original = TARGET.read_text(encoding="utf-8")
    if NEW in original:
        print("P0-D split placeholder fix was already applied")
        return 0
    count = original.count(OLD)
    if count != 1:
        raise RuntimeError(f"expected one pending-document block, found {count}")
    TARGET.write_text(original.replace(OLD, NEW, 1), encoding="utf-8")
    print(f"Applied P0-D split placeholder fix to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
