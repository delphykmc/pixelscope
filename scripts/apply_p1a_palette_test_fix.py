from __future__ import annotations

from pathlib import Path

SMOKE_TESTS = Path("tests/ui/test_ui_smoke.py")


def main() -> int:
    original = SMOKE_TESTS.read_text(encoding="utf-8")
    old = '''def test_layout_tool_and_file_state_models(qtbot: object, tmp_path: Path) -> None:
    window = MainWindow()
'''
    new = '''def test_layout_tool_and_file_state_models(qtbot: object, tmp_path: Path) -> None:
    assert isinstance(create_application([]), QApplication)
    window = MainWindow()
'''
    if new in original:
        print("P1-A palette test fix was already applied")
        return 0
    count = original.count(old)
    if count != 1:
        raise RuntimeError(f"expected one layout/file-state test header, found {count}")
    SMOKE_TESTS.write_text(original.replace(old, new, 1), encoding="utf-8")
    print(f"Applied P1-A palette test fix to {SMOKE_TESTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
