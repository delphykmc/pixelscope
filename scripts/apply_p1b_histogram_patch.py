from __future__ import annotations

from pathlib import Path

PANEL = Path("src/pixelscope/ui/comparison_analysis_panel.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_panel(text: str) -> str:
    old_spec = '''def automatic_histogram_spec(
    document: ImageDocument,
) -> tuple[int, tuple[float, float] | None]:
    """Select exact integer code bins from effective bit depth, capped at 16 bits."""

    source = document.source
    if source is None:
        raise ValueError("histogram requires a loaded document")
    effective_depth = min(max(document.bit_depth, 1), 16)
    bins = 1 << effective_depth
    if np.issubdtype(source.dtype, np.unsignedinteger):
        return bins, (0.0, float(1 << effective_depth))
    if np.issubdtype(source.dtype, np.signedinteger):
        limit = 1 << (effective_depth - 1)
        return bins, (float(-limit), float(limit))
    return min(bins, 4096), None
'''
    new_spec = '''def automatic_histogram_spec(
    document: ImageDocument,
    requested_bins: int | None = None,
) -> tuple[int, tuple[float, float] | None]:
    """Select UI histogram bins while preserving the document's native code range."""

    source = document.source
    if source is None:
        raise ValueError("histogram requires a loaded document")
    if requested_bins is not None and requested_bins not in (256, 1024, 4096):
        raise ValueError(f"unsupported histogram bin count: {requested_bins}")
    effective_depth = min(max(document.bit_depth, 1), 16)
    native_bins = 1 << effective_depth
    bins = min(native_bins, 4096) if requested_bins is None else requested_bins
    if np.issubdtype(source.dtype, np.unsignedinteger):
        return bins, (0.0, float(native_bins))
    if np.issubdtype(source.dtype, np.signedinteger):
        limit = 1 << (effective_depth - 1)
        return bins, (float(-limit), float(limit))
    return bins, None


def histogram_display_values(
    counts: NDArray[np.generic],
    mode: str,
) -> NDArray[np.float64]:
    """Transform histogram counts for display without changing cached raw counts."""

    values = counts.astype(np.float64, copy=False)
    if mode == "Normalized":
        total = float(np.sum(values))
        return values / total if total > 0 else values
    if mode == "Log count":
        return np.log10(values + 1.0)
    return values
'''
    text = replace_once(text, old_spec, new_spec, "automatic histogram specification")

    text = replace_once(
        text,
        '        self.histogram_units.addItems(("Count", "Normalized"))\n',
        '        self.histogram_units.addItems(("Count", "Normalized", "Log count"))\n',
        "histogram Y modes",
    )
    text = replace_once(
        text,
        '''        self.histogram_range = QComboBox()
        self.histogram_range.addItems(("Native range", "Normalized 0–1"))
        histogram_controls = QHBoxLayout()
''',
        '''        self.histogram_range = QComboBox()
        self.histogram_range.addItems(("Native range", "Normalized 0–1"))
        self.histogram_bins = QComboBox()
        self.histogram_bins.addItems(("Auto", "256", "1024", "4096"))
        histogram_controls = QHBoxLayout()
''',
        "histogram Bins selector",
    )
    text = replace_once(
        text,
        '''        histogram_controls.addWidget(self.histogram_range)
        histogram_controls.addSpacing(TOKENS.spacing_lg)
        histogram_controls.addLayout(channel_controls)
''',
        '''        histogram_controls.addWidget(self.histogram_range)
        histogram_controls.addSpacing(TOKENS.spacing_lg)
        histogram_controls.addWidget(QLabel("Bins"))
        histogram_controls.addWidget(self.histogram_bins)
        histogram_controls.addSpacing(TOKENS.spacing_lg)
        histogram_controls.addLayout(channel_controls)
''',
        "histogram Bins controls",
    )
    text = replace_once(
        text,
        '''        for combo in (self.histogram_mode, self.histogram_units, self.histogram_range):
            combo.setMaximumWidth(170)
            combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
                self._histogram_options_changed
            )
''',
        '''        for combo in (
            self.histogram_mode,
            self.histogram_units,
            self.histogram_range,
            self.histogram_bins,
        ):
            combo.setMaximumWidth(170)
        for combo in (self.histogram_mode, self.histogram_units, self.histogram_range):
            combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
                self._histogram_options_changed
            )
        self.histogram_bins.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._histogram_bins_changed
        )
''',
        "histogram option signal routing",
    )
    text = replace_once(
        text,
        '        histogram_specs = [automatic_histogram_spec(document) for document in documents]\n',
        '''        requested_bins = self._selected_histogram_bins()
        histogram_specs = [
            automatic_histogram_spec(document, requested_bins) for document in documents
        ]
''',
        "selected histogram bin use",
    )
    text = replace_once(
        text,
        '''    def _histogram_options_changed(self, _index: int) -> None:
        if self.last_results and self._histogram_specs:
            self._render(self.last_results, self._histogram_specs)

''',
        '''    def _histogram_options_changed(self, _index: int) -> None:
        if self.last_results and self._histogram_specs:
            self._render(self.last_results, self._histogram_specs)

    def _histogram_bins_changed(self, _index: int) -> None:
        if not self._documents:
            return
        self.status.setText("Preparing histogram...")
        self.busy.show()
        self._refresh_timer.start()

    def _selected_histogram_bins(self) -> int | None:
        text = self.histogram_bins.currentText()
        return None if text == "Auto" else int(text)

''',
        "histogram bin-change handlers",
    )
    text = replace_once(
        text,
        '''                y_values = counts.astype(np.float64, copy=False)
                if self.histogram_units.currentText() == "Normalized":
                    total = float(np.sum(y_values))
                    if total > 0:
                        y_values = y_values / total
''',
        '''                y_mode = self.histogram_units.currentText()
                y_values = histogram_display_values(counts, y_mode)
''',
        "histogram display value transform",
    )
    text = replace_once(
        text,
        '''            plot.setLabel(
                "left",
                "Normalized" if self.histogram_units.currentText() == "Normalized" else "Count",
            )
''',
        '''            y_mode = self.histogram_units.currentText()
            plot.setLabel(
                "left",
                "Normalized"
                if y_mode == "Normalized"
                else "Log count"
                if y_mode == "Log count"
                else "Count",
            )
''',
        "histogram Y-axis label",
    )
    return text


def main() -> int:
    original = PANEL.read_text(encoding="utf-8")
    updated = patch_panel(original)
    if updated == original:
        print("P1-B histogram patch already applied")
        return 0
    PANEL.write_text(updated, encoding="utf-8")
    print(f"Applied P1-B histogram patch to {PANEL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
