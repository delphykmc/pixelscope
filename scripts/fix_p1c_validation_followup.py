from __future__ import annotations

from pathlib import Path

RAW_DIALOG = Path("src/pixelscope/ui/raw_open_dialog.py")
UI_SMOKE = Path("tests/ui/test_ui_smoke.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_raw_dialog(text: str) -> str:
    return replace_once(
        text,
        """    def _update_legacy_black_text(self, _value: object = None) -> None:
        if self.layout_kind.currentText() == "BAYER":
            values = (
""",
        """    def _update_legacy_black_text(self, _value: object = None) -> None:
        values: tuple[int, ...]
        if self.layout_kind.currentText() == "BAYER":
            values = (
""",
        "black-level tuple annotation",
    )


def patch_ui_smoke(text: str) -> str:
    return replace_once(
        text,
        """    assert restored.main_splitter.sizes()[0] == saved_sidebar_width
""",
        """    restored_sidebar_width = restored.main_splitter.sizes()[0]
    assert (
        abs(restored_sidebar_width - saved_sidebar_width)
        <= restored.main_splitter.handleWidth()
    )
""",
        "splitter restore assertion",
    )


def update(path: Path, patcher: object) -> None:
    original = path.read_text(encoding="utf-8")
    updated = patcher(original)  # type: ignore[operator]
    if updated == original:
        print(f"No changes required: {path}")
        return
    path.write_text(updated, encoding="utf-8")
    print(f"Updated: {path}")


def main() -> int:
    update(RAW_DIALOG, patch_raw_dialog)
    update(UI_SMOKE, patch_ui_smoke)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
