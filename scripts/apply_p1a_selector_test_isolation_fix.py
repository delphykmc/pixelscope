from __future__ import annotations

from pathlib import Path

P1A_TESTS = Path("tests/ui/test_p1a_files_statistics_header.py")


def main() -> int:
    original = P1A_TESTS.read_text(encoding="utf-8")
    old = '''    window._select_document_ids([document.document_id for document in documents])

    panel = window.difference_panel
'''
    new = '''    window._select_document_ids([document.document_id for document in documents])
    window.set_layout_mode("Multi View")

    panel = window.difference_panel
'''
    if new in original:
        print("P1-A selector test isolation fix was already applied")
        return 0
    count = original.count(old)
    if count != 1:
        raise RuntimeError(f"expected one selector-authority setup block, found {count}")
    P1A_TESTS.write_text(original.replace(old, new, 1), encoding="utf-8")
    print(f"Applied P1-A selector test isolation fix to {P1A_TESTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
