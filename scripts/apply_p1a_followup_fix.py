from __future__ import annotations

from pathlib import Path

MAIN_WINDOW = Path("src/pixelscope/app/main_window.py")
TILE_HEADER = Path("src/pixelscope/ui/tile_header.py")
P1A_TESTS = Path("tests/ui/test_p1a_files_statistics_header.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if old not in text:
        if new and new in text:
            return text
        raise RuntimeError(f"could not find {description}")
    if text.count(old) != 1:
        raise RuntimeError(f"expected one {description}, found {text.count(old)}")
    return text.replace(old, new, 1)


def patch_main_window(text: str) -> str:
    text = replace_once(
        text,
        "        roles = (\n"
        "            {self._compare_pair[0]: \"A\", self._compare_pair[1]: \"B\"}\n"
        "            if self._compare_pair is not None\n"
        "            else {}\n"
        "        )\n",
        "",
        "remaining Files A/B role map",
    )
    text = replace_once(
        text,
        "                role=roles.get(document_id, \"\"),\n",
        "",
        "remaining Files role argument",
    )
    if "_compare_pair" in text:
        raise RuntimeError("MainWindow still contains _compare_pair after follow-up patch")
    return text


def patch_tile_header(text: str) -> str:
    text = replace_once(
        text,
        "    QHBoxLayout,\n    QLabel,\n",
        "    QHBoxLayout,\n    QLabel,\n    QLayout,\n",
        "QLayout import",
    )
    text = replace_once(
        text,
        "        self.meta.setObjectName(\"tileMeta\")\n"
        "        self.meta.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)\n",
        "        self.meta.setObjectName(\"tileMeta\")\n"
        "        self.meta.setMinimumWidth(0)\n"
        "        self.meta.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)\n",
        "metadata minimum width",
    )
    text = replace_once(
        text,
        "        layout = QHBoxLayout(self)\n"
        "        layout.setContentsMargins(\n",
        "        layout = QHBoxLayout(self)\n"
        "        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)\n"
        "        layout.setContentsMargins(\n",
        "unconstrained tile-header layout",
    )
    text = replace_once(
        text,
        "    def resizeEvent(self, event: object) -> None:  # noqa: N802\n"
        "        super().resizeEvent(event)  # type: ignore[arg-type]\n"
        "        self._update_responsive_mode()\n\n"
        "    def _update_responsive_mode(self) -> None:\n"
        "        compact = self.width() < self.COMPACT_WIDTH\n",
        "    def resizeEvent(self, event: object) -> None:  # noqa: N802\n"
        "        super().resizeEvent(event)  # type: ignore[arg-type]\n"
        "        size = getattr(event, \"size\", None)\n"
        "        event_width = size().width() if callable(size) else self.width()\n"
        "        self._update_responsive_mode(event_width)\n\n"
        "    def _update_responsive_mode(self, available_width: int | None = None) -> None:\n"
        "        width = self.width() if available_width is None else available_width\n"
        "        compact = width < self.COMPACT_WIDTH\n",
        "responsive resize handling",
    )
    return text


def patch_tests(text: str) -> str:
    text = replace_once(
        text,
        "    assert all(not viewer.header.focus.isVisible() for viewer in view.occupied_viewers)\n",
        "    assert all(viewer.header.focus.isHidden() for viewer in view.occupied_viewers)\n",
        "four-tile focus-pin assertion",
    )
    text = replace_once(
        text,
        "    assert all(viewer.header.focus.isVisible() for viewer in view.occupied_viewers)\n",
        "    assert all(not viewer.header.focus.isHidden() for viewer in view.occupied_viewers)\n",
        "five-tile focus-pin assertion",
    )
    return text


def patch_file(path: Path, patcher: object) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = patcher(original)  # type: ignore[operator]
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    changes = {
        MAIN_WINDOW: patch_file(MAIN_WINDOW, patch_main_window),
        TILE_HEADER: patch_file(TILE_HEADER, patch_tile_header),
        P1A_TESTS: patch_file(P1A_TESTS, patch_tests),
    }
    changed = [str(path) for path, was_changed in changes.items() if was_changed]
    print("Applied P1-A follow-up fix:" if changed else "P1-A follow-up was already applied")
    for path in changed:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
