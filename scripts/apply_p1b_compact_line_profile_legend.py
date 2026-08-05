from __future__ import annotations

from pathlib import Path

LINE_PROFILE_PANEL = Path("src/pixelscope/ui/line_profile_panel.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_line_profile(text: str) -> str:
    text = replace_once(
        text,
        '''                    short_name = self._documents[image_index].display_name
                    if len(short_name) > 24:
                        short_name = f"{short_name[:11]}…{short_name[-10:]}"
                    if view_mode == "Separate by image":
                        legend_name = channel_name
                    elif view_mode == "Separate by channel":
                        legend_name = f"{image_index + 1} · {short_name}"
                    else:
                        legend_name = f"{image_index + 1} · {short_name} · {channel_name}"
                    curve_name = legend_name if view_mode == "Separate by image" else None
''',
        '''                    legend_name = f"{image_index + 1} · {channel_name}"
                    curve_name = legend_name if view_mode == "Separate by image" else None
''',
        "compact Line Profile legend labels",
    )
    return replace_once(
        text,
        "                            size=5.0,\n",
        "                            size=7.0,\n",
        "larger Line Profile identity markers",
    )


def main() -> int:
    original = LINE_PROFILE_PANEL.read_text(encoding="utf-8")
    updated = patch_line_profile(original)
    if updated == original:
        print(f"No changes required: {LINE_PROFILE_PANEL}")
        return 0
    LINE_PROFILE_PANEL.write_text(updated, encoding="utf-8")
    print(f"Updated: {LINE_PROFILE_PANEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
