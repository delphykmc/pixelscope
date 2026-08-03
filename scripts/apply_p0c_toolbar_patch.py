from __future__ import annotations

import argparse
from pathlib import Path

TARGET = Path("src/pixelscope/app/main_window.py")


def _replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description} block, found {count}")
    return text.replace(old, new, 1)


def _replace_between(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise RuntimeError(f"start marker not found: {start.strip()}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise RuntimeError(f"end marker not found: {end.strip()}")
    return text[:start_index] + replacement + text[end_index:]


def patched_text(text: str) -> str:
    marker = "from pixelscope.ui.toolbar_icons import toolbar_icon"
    applied_markers = (
        marker in text,
        'fit_action.setIcon(toolbar_icon("fit"))' in text,
        'self.diff_action.setToolTip(diff_tooltip)' in text,
    )
    if all(applied_markers):
        return text
    if any(applied_markers):
        raise RuntimeError("main_window.py contains a partial P0-C toolbar patch")

    text = _replace_once(
        text,
        "    QSplitter,\n    QStackedWidget,\n    QStyle,\n    QTabWidget,\n",
        "    QSplitter,\n    QStackedWidget,\n    QTabWidget,\n",
        "QStyle import",
    )
    text = _replace_once(
        text,
        "from pixelscope.ui.structured_status_bar import StructuredStatusBar\n",
        "from pixelscope.ui.structured_status_bar import StructuredStatusBar\n"
        "from pixelscope.ui.toolbar_icons import toolbar_icon\n",
        "toolbar icon import insertion",
    )

    create_toolbar = '''    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setObjectName("mainToolbar")
        toolbar.setAccessibleName("PixelScope main toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(TOKENS.icon_size, TOKENS.icon_size))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        toolbar.setStyleSheet(toolbar_style())
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        self.main_toolbar = toolbar

        self.layout_selector = QComboBox()
        self.layout_selector.addItems(("Auto", "Single View", "Multi View"))
        self.layout_selector.setFixedHeight(TOKENS.control_height)
        self.layout_selector.currentTextChanged.connect(  # type: ignore[attr-defined]
            self.set_layout_mode
        )
        layout_group = QWidget()
        layout_group_layout = QHBoxLayout(layout_group)
        layout_group_layout.setContentsMargins(
            TOKENS.spacing_sm,
            0,
            TOKENS.spacing_md,
            0,
        )
        layout_group_layout.setSpacing(TOKENS.spacing_sm)
        layout_group_layout.addWidget(QLabel("Layout"))
        layout_group_layout.addWidget(self.layout_selector)
        toolbar.addWidget(layout_group)

        fit_action = self.action_map["Fit Image"]
        fit_action.setIcon(toolbar_icon("fit"))
        fit_action.setIconText("Fit")
        fit_action.setToolTip("Fit the active image to the current view (F)")
        fit_action.setStatusTip(fit_action.toolTip())
        toolbar.addAction(fit_action)

        zoom_100 = self.action_map["100% Zoom"]
        zoom_100.setIcon(toolbar_icon("actual_size"))
        zoom_100.setIconText("1:1")
        zoom_100.setToolTip("Show the active image at one image pixel per screen pixel (Ctrl+0)")
        zoom_100.setStatusTip(zoom_100.toolTip())
        toolbar.addAction(zoom_100)

        self.zoom_in_action = QAction(toolbar_icon("zoom_in"), "Zoom In", self)
        self.zoom_in_action.setIconText("Zoom +")
        self.zoom_in_action.setToolTip("Zoom in around the current view center")
        self.zoom_in_action.setStatusTip(self.zoom_in_action.toolTip())
        self.zoom_in_action.triggered.connect(  # type: ignore[attr-defined]
            lambda: self.zoom_by(0.8)
        )
        toolbar.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction(toolbar_icon("zoom_out"), "Zoom Out", self)
        self.zoom_out_action.setIconText("Zoom −")
        self.zoom_out_action.setToolTip("Zoom out around the current view center")
        self.zoom_out_action.setStatusTip(self.zoom_out_action.toolTip())
        self.zoom_out_action.triggered.connect(  # type: ignore[attr-defined]
            lambda: self.zoom_by(1.25)
        )
        toolbar.addAction(self.zoom_out_action)
        toolbar.addSeparator()

        self.sync_action = QAction(toolbar_icon("sync"), "Sync View", self)
        self.sync_action.setIconText("Sync")
        self.sync_action.setCheckable(True)
        self.sync_action.setChecked(True)
        self.sync_action.toggled.connect(  # type: ignore[attr-defined]
            self.multi_compare_view.set_sync_enabled
        )
        self.sync_action.toggled.connect(  # type: ignore[attr-defined]
            lambda _checked: self._update_action_states()
        )
        toolbar.addAction(self.sync_action)

        self.diff_action = QAction(toolbar_icon("difference"), "Diff", self)
        self.diff_action.setIconText("Diff")
        self.diff_action.setCheckable(True)
        self.diff_action.setEnabled(False)
        self.diff_action.toggled.connect(self._set_difference_visible)  # type: ignore[attr-defined]
        toolbar.addAction(self.diff_action)

        self.plots_action.setIcon(toolbar_icon("plots"))
        self.plots_action.setIconText("Plots")
        self.plots_action.setText("Plots")
        toolbar.addAction(self.plots_action)
        toolbar.addSeparator()

        self.export_toolbar_action = QAction(toolbar_icon("export"), "Export", self)
        self.export_toolbar_action.setIconText("Export")
        self.export_toolbar_action.triggered.connect(  # type: ignore[attr-defined]
            self.export_statistics
        )
        toolbar.addAction(self.export_toolbar_action)

        for selector in (self.difference_panel.a_selector, self.difference_panel.b_selector):
            selector.currentIndexChanged.connect(  # type: ignore[attr-defined]
                lambda _index: self._update_action_states()
            )
        self._update_action_states()

'''
    text = _replace_between(
        text,
        "    def _create_toolbar(self) -> None:\n",
        "    def _escape_action(self) -> None:\n",
        create_toolbar,
    )

    action_states = '''    def _update_action_states(self) -> None:
        documents = self.selected_documents
        six_image_diff = self._six_image_diff_locked()
        split_action = self.action_map.get("Split Channels")
        if split_action is not None:
            split_action.setEnabled(
                len(documents) == 1
                and documents[0].channel_layout in ("RGB", "RGBA", "BAYER")
            )

        current_widget = self.central_stack.currentWidget()
        visible_viewers = self.multi_compare_view.occupied_viewers
        view_ready = (
            current_widget is self.viewer and self.viewer.document is not None
        ) or (current_widget is self.multi_compare_view and bool(visible_viewers))
        for name in ("Fit Image", "100% Zoom"):
            action = self.action_map.get(name)
            if action is not None:
                action.setEnabled(view_ready)
        for name in ("zoom_in_action", "zoom_out_action"):
            action = getattr(self, name, None)
            if isinstance(action, QAction):
                action.setEnabled(view_ready)

        if hasattr(self, "sync_action"):
            sync_available = current_widget is self.multi_compare_view and len(visible_viewers) >= 2
            self.sync_action.setEnabled(sync_available)
            if not sync_available:
                sync_tooltip = "Sync View is available in Multi View with two or more images"
            elif self.sync_action.isChecked():
                sync_tooltip = "Disable synchronized zoom, pan, and cursor"
            else:
                sync_tooltip = "Synchronize zoom, pan, and cursor across visible images"
            self.sync_action.setToolTip(sync_tooltip)
            self.sync_action.setStatusTip(sync_tooltip)

        statistics_available = (
            bool(documents) and self.comparison_analysis_panel.table.columnCount() > 0
        )
        menu_export = self.action_map.get("Export Statistics CSV...")
        if menu_export is not None:
            menu_export.setEnabled(statistics_available)
            menu_export.setToolTip(
                "Export the current Statistics table as CSV"
                if statistics_available
                else "No statistics are available to export"
            )
        if hasattr(self, "export_toolbar_action"):
            self.export_toolbar_action.setEnabled(statistics_available)
            export_tooltip = (
                "Export the current Statistics table as CSV"
                if statistics_available
                else "No statistics are available to export"
            )
            self.export_toolbar_action.setToolTip(export_tooltip)
            self.export_toolbar_action.setStatusTip(export_tooltip)

        if hasattr(self, "diff_action"):
            pair = self.difference_panel.selected_documents()
            pair_ids = (
                frozenset((pair[0].document_id, pair[1].document_id))
                if pair is not None
                else None
            )
            result_ids = (
                frozenset(self._difference_source_ids)
                if self._difference_source_ids is not None
                else None
            )
            cached = pair_ids is not None and self.difference_panel.has_cached_map()
            checked = self.diff_action.isChecked()
            self.diff_action.setEnabled(checked or cached)
            if checked and (cached or pair_ids == result_ids):
                diff_tooltip = "Hide Difference"
            elif checked or (
                pair_ids is not None and result_ids is not None and pair_ids != result_ids
            ):
                diff_tooltip = "Difference is not calculated for the selected pair"
            elif cached:
                diff_tooltip = "Show the cached Difference for the selected image pair"
            else:
                diff_tooltip = "Calculate Difference in Analysis first"
            self.diff_action.setToolTip(diff_tooltip)
            self.diff_action.setStatusTip(diff_tooltip)

        if hasattr(self, "plots_action"):
            plots_visible = not self.bottom_dock.isHidden()
            plots_tooltip = (
                "Hide Histogram and Line Profile plots"
                if plots_visible
                else "Show Histogram and Line Profile plots"
            )
            self.plots_action.setToolTip(plots_tooltip)
            self.plots_action.setStatusTip(plots_tooltip)

        multi_action = self.action_map.get("Multi View")
        if multi_action is not None:
            multi_action.setEnabled(not six_image_diff)
        if hasattr(self, "layout_selector"):
            model = self.layout_selector.model()
            for mode in ("Auto", "Multi View"):
                index = self.layout_selector.findText(mode)
                item = model.item(index) if index >= 0 and hasattr(model, "item") else None
                if item is not None:
                    item.setEnabled(not six_image_diff)

'''
    text = _replace_between(
        text,
        "    def _update_action_states(self) -> None:\n",
        "    def _six_image_diff_locked(self) -> bool:\n",
        action_states,
    )

    plots_visibility = '''    def _plots_visibility_changed(self, visible: bool) -> None:
        self.plots_action.blockSignals(True)
        self.plots_action.setChecked(visible)
        self.plots_action.blockSignals(False)
        self._update_action_states()

'''
    text = _replace_between(
        text,
        "    def _plots_visibility_changed(self, visible: bool) -> None:\n",
        "    def _plots_top_level_changed(self, floating: bool) -> None:\n",
        plots_visibility,
    )
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the reviewed P0-C MainWindow patch")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify whether the patch is already applied without writing",
    )
    args = parser.parse_args()

    original = TARGET.read_text(encoding="utf-8")
    updated = patched_text(original)
    changed = updated != original
    if args.check:
        if changed:
            raise SystemExit("P0-C toolbar patch is not applied")
        print("P0-C toolbar patch is applied")
        return 0
    if not changed:
        print("P0-C toolbar patch was already applied")
        return 0
    TARGET.write_text(updated, encoding="utf-8")
    print(f"Applied P0-C toolbar patch to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
