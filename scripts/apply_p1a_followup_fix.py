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
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def replace_method(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        if replacement in text:
            return text
        raise RuntimeError(f"method marker not found: {start.strip()}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"end marker not found: {end.strip()}")
    return text[:start_index] + replacement + text[end_index:]


def remove_if_present(text: str, block: str) -> str:
    return text.replace(block, "", 1) if block in text else text


def patch_main_window(text: str) -> str:
    # Re-apply all known pair-plumbing removals idempotently. The original helper
    # intentionally removed the field first, so any missed read becomes fatal.
    text = remove_if_present(
        text,
        "        self._compare_pair: tuple[str, str] | None = None\n",
    )
    text = remove_if_present(
        text,
        "        self.document_list.compare_role_requested.connect(self._set_compare_role)\n",
    )
    text = remove_if_present(
        text,
        "        if self._compare_pair is not None and selected_set.intersection(self._compare_pair):\n"
        "            self._compare_pair = None\n",
    )
    text = remove_if_present(
        text,
        "            self.multi_compare_view.set_compare_pair(None)\n",
    )
    text = remove_if_present(
        text,
        "            self.multi_compare_view.set_compare_pair(self._compare_pair)\n",
    )
    text = remove_if_present(
        text,
        "        self._compare_pair = None\n        self.set_layout_mode(\"Multi View\")\n",
    )

    old_difference_pair = (
        "        difference_pair = self._compare_pair\n"
        "        if difference_pair is None and len(documents) == 2:\n"
        "            difference_pair = (documents[0].document_id, documents[1].document_id)\n"
        "        self.difference_panel.set_documents(\n"
        "            analysis_ready,\n"
        "            difference_pair,\n"
        "            self._shared_roi,\n"
        "        )\n"
    )
    new_difference_pair = (
        "        self.difference_panel.set_documents(\n"
        "            analysis_ready,\n"
        "            None,\n"
        "            self._shared_roi,\n"
        "        )\n"
    )
    if old_difference_pair in text:
        text = text.replace(old_difference_pair, new_difference_pair, 1)

    old_single_role = (
        "            role = \"\"\n"
        "            if self._compare_pair is not None:\n"
        "                if document.document_id == self._compare_pair[0]:\n"
        "                    role = \"A\"\n"
        "                elif document.document_id == self._compare_pair[1]:\n"
        "                    role = \"B\"\n"
        "            self.viewer.set_tile_context(self._current_index + 1, role)\n"
    )
    if old_single_role in text:
        text = text.replace(
            old_single_role,
            "            self.viewer.set_tile_context(self._current_index + 1, \"\")\n",
            1,
        )

    canonical_file_states = '''    def _update_file_states(
        self,
        visible_documents: Sequence[ImageDocument],
        active_document: ImageDocument | None,
    ) -> None:
        visible_ids = {document.document_id for document in visible_documents}
        for document_id, document in self.documents.items():
            self.document_list.set_document_state(
                document_id,
                visible=document_id in visible_ids,
                active=active_document is not None
                and document_id == active_document.document_id,
                loading_state=document.loading_state,
            )

'''
    text = replace_method(
        text,
        "    def _update_file_states(\n",
        "    def show_selected_image(\n",
        canonical_file_states,
    )

    compare_role_start = text.find(
        "    def _set_compare_role(self, document_id: str, role: str) -> None:\n"
    )
    if compare_role_start >= 0:
        compare_role_end = text.find("    def _select_document_ids(\n", compare_role_start)
        if compare_role_end < 0:
            raise RuntimeError("_select_document_ids marker not found")
        text = text[:compare_role_start] + text[compare_role_end:]

    leftovers = [
        f"{line_number}: {line.strip()}"
        for line_number, line in enumerate(text.splitlines(), start=1)
        if "_compare_pair" in line
    ]
    if leftovers:
        raise RuntimeError(
            "MainWindow still contains _compare_pair:\n" + "\n".join(leftovers)
        )
    return text


def patch_tile_header(text: str) -> str:
    if "    QLayout,\n" not in text:
        text = replace_once(
            text,
            "    QHBoxLayout,\n    QLabel,\n",
            "    QHBoxLayout,\n    QLabel,\n    QLayout,\n",
            "QLayout import",
        )
    if "        self.meta.setMinimumWidth(0)\n" not in text:
        text = replace_once(
            text,
            "        self.meta.setObjectName(\"tileMeta\")\n"
            "        self.meta.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)\n",
            "        self.meta.setObjectName(\"tileMeta\")\n"
            "        self.meta.setMinimumWidth(0)\n"
            "        self.meta.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)\n",
            "metadata minimum width",
        )
    if "layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)" not in text:
        text = replace_once(
            text,
            "        layout = QHBoxLayout(self)\n"
            "        layout.setContentsMargins(\n",
            "        layout = QHBoxLayout(self)\n"
            "        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)\n"
            "        layout.setContentsMargins(\n",
            "unconstrained tile-header layout",
        )
    if "def _update_responsive_mode(self, available_width: int | None = None)" not in text:
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
    text = text.replace(
        "    assert all(not viewer.header.focus.isVisible() for viewer in view.occupied_viewers)\n",
        "    assert all(viewer.header.focus.isHidden() for viewer in view.occupied_viewers)\n",
        1,
    )
    text = text.replace(
        "    assert all(viewer.header.focus.isVisible() for viewer in view.occupied_viewers)\n",
        "    assert all(not viewer.header.focus.isHidden() for viewer in view.occupied_viewers)\n",
        1,
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
