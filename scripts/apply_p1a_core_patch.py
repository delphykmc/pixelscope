from __future__ import annotations

from pathlib import Path

MAIN_WINDOW = Path("src/pixelscope/app/main_window.py")
MULTI_COMPARE_VIEW = Path("src/pixelscope/ui/multi_compare_view.py")
ANALYSIS_PANEL = Path("src/pixelscope/ui/comparison_analysis_panel.py")
SMOKE_TESTS = Path("tests/ui/test_ui_smoke.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def remove_once(text: str, old: str, description: str) -> str:
    count = text.count(old)
    if count == 0:
        return text
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, "", 1)


def patch_main_window(text: str) -> str:
    removals = (
        (
            "        self._compare_pair: tuple[str, str] | None = None\n",
            "MainWindow compare-pair field",
        ),
        (
            "        self.document_list.compare_role_requested.connect(self._set_compare_role)\n",
            "Files compare-role connection",
        ),
        (
            "        if self._compare_pair is not None and selected_set.intersection(self._compare_pair):\n"
            "            self._compare_pair = None\n",
            "selection compare-pair reset",
        ),
        (
            "            self.multi_compare_view.set_compare_pair(None)\n",
            "split compare-pair reset",
        ),
        (
            "            self.multi_compare_view.set_compare_pair(self._compare_pair)\n",
            "multi-view compare-pair setup",
        ),
        (
            "        self._compare_pair = None\n        self.set_layout_mode(\"Multi View\")\n",
            "compare-selection pair reset",
        ),
    )
    for block, description in removals:
        if description == "compare-selection pair reset":
            text = replace_once(
                text,
                block,
                "        self.set_layout_mode(\"Multi View\")\n",
                description,
            )
        else:
            text = remove_once(text, block, description)

    text = replace_once(
        text,
        "        difference_pair = self._compare_pair\n"
        "        if difference_pair is None and len(documents) == 2:\n"
        "            difference_pair = (documents[0].document_id, documents[1].document_id)\n"
        "        self.difference_panel.set_documents(\n"
        "            analysis_ready,\n"
        "            difference_pair,\n"
        "            self._shared_roi,\n"
        "        )\n",
        "        self.difference_panel.set_documents(\n"
        "            analysis_ready,\n"
        "            None,\n"
        "            self._shared_roi,\n"
        "        )\n",
        "Difference selector authority block",
    )
    text = replace_once(
        text,
        "            role = \"\"\n"
        "            if self._compare_pair is not None:\n"
        "                if document.document_id == self._compare_pair[0]:\n"
        "                    role = \"A\"\n"
        "                elif document.document_id == self._compare_pair[1]:\n"
        "                    role = \"B\"\n"
        "            self.viewer.set_tile_context(self._current_index + 1, role)\n",
        "            self.viewer.set_tile_context(self._current_index + 1, \"\")\n",
        "single-view visible A/B role block",
    )
    text = replace_once(
        text,
        "        roles = (\n"
        "            {self._compare_pair[0]: \"A\", self._compare_pair[1]: \"B\"}\n"
        "            if self._compare_pair is not None\n"
        "            else {}\n"
        "        )\n",
        "",
        "Files A/B role map",
    )
    text = replace_once(
        text,
        "                role=roles.get(document_id, \"\"),\n",
        "",
        "Files role state argument",
    )

    start = text.find("    def _set_compare_role(self, document_id: str, role: str) -> None:\n")
    end = text.find("    def _select_document_ids(\n", start)
    if start >= 0:
        if end < 0:
            raise RuntimeError("_select_document_ids marker not found")
        text = text[:start] + text[end:]
    return text


def patch_multi_compare_view(text: str) -> str:
    text = remove_once(
        text,
        "        self.compare_pair: tuple[str, str] | None = None\n",
        "MultiCompareView compare-pair field",
    )
    text = remove_once(
        text,
        "                if document is not None and self.compare_pair is not None:\n"
        "                    if document.document_id == self.compare_pair[0]:\n"
        "                        role = \"A\"\n"
        "                    elif document.document_id == self.compare_pair[1]:\n"
        "                        role = \"B\"\n",
        "multi-view visible A/B role block",
    )
    text = remove_once(
        text,
        "    def set_compare_pair(self, pair: tuple[str, str] | None) -> None:\n"
        "        self.compare_pair = pair\n\n",
        "MultiCompareView set_compare_pair",
    )
    return text


def patch_analysis_panel(text: str) -> str:
    text = replace_once(
        text,
        '        self.roi_label = QLabel("Full image")\n',
        '        self.roi_label = QLabel("")\n'
        "        self.roi_label.setFixedHeight(\n"
        "            self.roi_label.fontMetrics().height() + TOKENS.spacing_xs * 2\n"
        "        )\n",
        "fixed Region detail row",
    )
    text = replace_once(
        text,
        '        self.image_summary.setHorizontalHeaderLabels(("Id", "Image", "Samples"))\n',
        '        self.image_summary.setHorizontalHeaderLabels(("Id", "Image", "Pixels"))\n',
        "Statistics summary Pixels header",
    )
    text = replace_once(
        text,
        "        if bounds is None:\n"
        "            self.roi_label.setText(\"Full image\")\n"
        "            self.region_scope.setCurrentText(region_name or \"Full image\")\n"
        "        else:\n"
        "            self.roi_label.setText(\n"
        "                f\"{region_name or 'Active ROI'} · x={bounds.x}, y={bounds.y}, \"\n"
        "                f\"{bounds.width} x {bounds.height}\"\n"
        "            )\n"
        "            self.region_scope.setCurrentText(region_name or \"Active ROI\")\n",
        "        if bounds is None:\n"
        "            self.roi_label.clear()\n"
        "            self.region_scope.setCurrentText(region_name or \"Full image\")\n"
        "        else:\n"
        "            self.roi_label.setText(\n"
        "                f\"x={bounds.x}, y={bounds.y}, width={bounds.width}, \"\n"
        "                f\"height={bounds.height}\"\n"
        "            )\n"
        "            self.region_scope.setCurrentText(region_name or \"Active ROI\")\n",
        "Region detail content",
    )
    text = replace_once(
        text,
        '        self.roi_label.setText("Full image")\n',
        "        self.roi_label.clear()\n",
        "Statistics clear Region detail",
    )
    return text


def patch_smoke_tests(text: str) -> str:
    text = replace_once(
        text,
        '    assert child.text(1) == ""\n',
        '    assert window.document_list.columnCount() == 2\n'
        '    assert child.text(1) == "PNG"\n',
        "Files two-column expectation",
    )
    text = remove_once(
        text,
        "    window._compare_pair = None\n",
        "obsolete test compare-pair reset",
    )
    text = replace_once(
        text,
        '    assert window.comparison_analysis_panel.roi_label.text() == "Full image"\n',
        '    assert window.comparison_analysis_panel.roi_label.text() == ""\n',
        "full-image Region detail expectation",
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
        MULTI_COMPARE_VIEW: patch_file(MULTI_COMPARE_VIEW, patch_multi_compare_view),
        ANALYSIS_PANEL: patch_file(ANALYSIS_PANEL, patch_analysis_panel),
        SMOKE_TESTS: patch_file(SMOKE_TESTS, patch_smoke_tests),
    }
    changed = [str(path) for path, was_changed in changes.items() if was_changed]
    if changed:
        print("Applied P1-A core patch:")
        for path in changed:
            print(f"  {path}")
    else:
        print("P1-A core patch was already applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
