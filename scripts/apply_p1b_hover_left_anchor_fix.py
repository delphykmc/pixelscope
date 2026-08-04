from __future__ import annotations

from pathlib import Path

HISTOGRAM_PANEL = Path("src/pixelscope/ui/comparison_analysis_panel.py")
LINE_PROFILE_PANEL = Path("src/pixelscope/ui/line_profile_panel.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_histogram(text: str) -> str:
    old = '''        hint.setAnchor(
            (
                1 if point.x() > sum(view_range[0]) / 2 else 0,
                0 if point.y() > sum(view_range[1]) / 2 else 1,
            )
        )
'''
    new = '''        y_anchor = 0 if point.y() > sum(view_range[1]) / 2 else 1
        hint.setAnchor((1, y_anchor))
'''
    return replace_once(text, old, new, "histogram hover anchor")


def patch_line_profile(text: str) -> str:
    text = replace_once(
        text,
        '''        x_anchor = 1 if point.x() > sum(view_range[0]) / 2 else 0
        y_anchor = 0 if point.y() > sum(view_range[1]) / 2 else 1
''',
        '''        y_anchor = 0 if point.y() > sum(view_range[1]) / 2 else 1
''',
        "line-profile horizontal anchor selection",
    )
    return replace_once(
        text,
        "        hint.setAnchor((x_anchor, y_anchor))\n",
        "        hint.setAnchor((1, y_anchor))\n",
        "line-profile hover anchor",
    )


def apply(path: Path, patcher: object) -> None:
    original = path.read_text(encoding="utf-8")
    updated = patcher(original)  # type: ignore[operator]
    if updated == original:
        print(f"No changes required: {path}")
        return
    path.write_text(updated, encoding="utf-8")
    print(f"Updated: {path}")


def main() -> int:
    apply(HISTOGRAM_PANEL, patch_histogram)
    apply(LINE_PROFILE_PANEL, patch_line_profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
