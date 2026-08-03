from __future__ import annotations

import argparse
from pathlib import Path

TARGET = Path("src/pixelscope/app/main_window.py")


def _replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count == 0 and new in text:
        return text
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
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
    applied_markers = (
        "    menu_style,\n" in text,
        'self.split_channels_action.setIcon(toolbar_icon("split_channels"))' in text,
        "def _split_display_documents(" in text,
        "stay_single = force_single or self._layout_mode == \"Single View\"" in text,
        "if count <= 1:\n            return (\"Grid 2x2\", 4) if self._split_channels" in text,
    )
    if all(applied_markers):
        return text
    if any(applied_markers):
        raise RuntimeError("main_window.py contains a partial P0-D patch")

    text = _replace_once(
        text,
        "from pixelscope.ui.design_tokens import TOKENS, panel_heading_style, toolbar_style\n",
        "from pixelscope.ui.design_tokens import (\n"
        "    TOKENS,\n"
        "    menu_style,\n"
        "    panel_heading_style,\n"
        "    toolbar_style,\n"
        ")\n",
        "design token imports",
    )
    text = _replace_once(
        text,
        "        menu_bar = self.menuBar()\n        menus = {\n",
        "        menu_bar = self.menuBar()\n"
        "        menu_bar.setStyleSheet(menu_style())\n"
        "        menus = {\n",
        "menu style setup",
    )

    old_split_action = '''        split_channels = add_action(
            "View",
            "Split Channels",
            self._set_split_channels,
        )
        split_channels.setCheckable(True)
'''
    new_split_action = '''        self.split_channels_action = add_action(
            "View",
            "Split Channels",
            self._set_split_channels,
        )
        self.split_channels_action.setCheckable(True)
        self.split_channels_action.setIcon(toolbar_icon("split_channels"))
        self.split_channels_action.setIconText("Split")
        self.split_channels_action.setToolTip(
            "Split the selected RGB or Bayer image into channel views"
        )
        self.split_channels_action.setStatusTip(self.split_channels_action.toolTip())
'''
    text = _replace_once(text, old_split_action, new_split_action, "Split Channels action")

    old_redock = '''        self.redock_plots_action = add_action("View", "Dock Plots", self._redock_plots)
        self.redock_plots_action.setEnabled(False)
'''
    new_redock = '''        self.redock_plots_action = add_action("View", "Dock Plots", self._redock_plots)
        self.redock_plots_action.setIcon(toolbar_icon("dock"))
        self.redock_plots_action.setToolTip("Dock the floating Plots panel")
        self.redock_plots_action.setStatusTip(self.redock_plots_action.toolTip())
        self.redock_plots_action.setEnabled(False)
'''
    text = _replace_once(text, old_redock, new_redock, "Dock Plots action")

    text = _replace_once(
        text,
        "        toolbar.addWidget(layout_group)\n\n        fit_action = self.action_map[\"Fit Image\"]\n",
        "        toolbar.addWidget(layout_group)\n"
        "        toolbar.addAction(self.split_channels_action)\n"
        "        toolbar.addSeparator()\n\n"
        "        fit_action = self.action_map[\"Fit Image\"]\n",
        "Split Channels toolbar insertion",
    )

    old_split_state = '''        split_action = self.action_map.get("Split Channels")
        if split_action is not None:
            split_action.setEnabled(
                len(documents) == 1 and documents[0].channel_layout in ("RGB", "RGBA", "BAYER")
            )
'''
    new_split_state = '''        split_action = self.action_map.get("Split Channels")
        if split_action is not None:
            split_available = (
                len(documents) == 1
                and documents[0].source is not None
                and documents[0].channel_layout in ("RGB", "RGBA", "BAYER")
            )
            split_action.setEnabled(split_available)
            if split_available and split_action.isChecked():
                split_tooltip = "Return to the combined image view"
            elif split_available:
                split_tooltip = "Split the selected RGB or Bayer image into channel views"
            elif len(documents) != 1:
                split_tooltip = "Split Channels requires exactly one selected image"
            elif documents[0].source is None:
                split_tooltip = "Split Channels will be available when the image finishes loading"
            else:
                split_tooltip = "Split Channels supports RGB, RGBA, and Bayer images"
            split_action.setToolTip(split_tooltip)
            split_action.setStatusTip(split_tooltip)
'''
    text = _replace_once(text, old_split_state, new_split_state, "Split Channels action state")

    old_difference_order = '''        if show_difference and self._layout_mode != "Single View":
            assert difference_document is not None
            if (
                len(documents) == 2
                and difference_document.document_id not in self._multi_display_order
                and self._focus_document_id not in {document.document_id for document in documents}
            ):
                self._promote_multi_document(difference_document.document_id)
            display_documents = (
                [difference_document, *documents]
                if len(documents) == 2
                else [*documents, difference_document]
            )
'''
    new_difference_order = '''        if show_difference and self._layout_mode != "Single View":
            assert difference_document is not None
            display_documents = [difference_document, *documents]
'''
    text = _replace_once(
        text,
        old_difference_order,
        new_difference_order,
        "multi-view Difference ordering",
    )

    old_split_branch = '''        elif (
            self._view_capacity == 4
            and self._split_channels
            and len(documents) == 1
            and documents[0].source is not None
        ):
            document = documents[0]
            cache_key = (document.document_id, document.generation)
            channel_documents = self._channel_view_cache.get(cache_key)
            if channel_documents is None:
                channel_documents = split_document_channels(document)
                self._channel_view_cache = {cache_key: channel_documents}
            self._channel_split_active = bool(channel_documents)
            self.multi_compare_view.set_capacity(4)
            self.multi_compare_view.set_compare_pair(None)
            self.multi_compare_view.set_documents(
                channel_documents,
                0,
                len(channel_documents),
                None,
                None,
                preserve_view,
            )
            self.central_stack.setCurrentWidget(self.multi_compare_view)
            visible_state = [document]
'''
    new_split_branch = '''        elif self._view_capacity == 4 and self._split_channels and len(documents) == 1:
            document = documents[0]
            channel_documents, split_active = self._split_display_documents(document)
            self._channel_split_active = split_active
            self.multi_compare_view.set_capacity(4)
            self.multi_compare_view.set_compare_pair(None)
            self.multi_compare_view.set_documents(
                channel_documents,
                0,
                len(channel_documents),
                None,
                None,
                preserve_view,
            )
            self.central_stack.setCurrentWidget(self.multi_compare_view)
            visible_state = [document]
'''
    text = _replace_once(
        text,
        old_split_branch,
        new_split_branch,
        "split-channel rendering branch",
    )

    split_helpers = '''    def _split_display_documents(
        self,
        document: ImageDocument,
    ) -> tuple[list[ImageDocument], bool]:
        """Return real channel views or stable loading placeholders for split mode."""

        if document.source is not None:
            cache_key = (document.document_id, document.generation)
            channel_documents = self._channel_view_cache.get(cache_key)
            if channel_documents is None:
                channel_documents = split_document_channels(document)
                self._channel_view_cache = {cache_key: channel_documents}
            if channel_documents:
                return channel_documents, True
            return [document], False

        profile = document.raw_profile or self._raw_profiles.get(document.document_id)
        is_bayer = document.channel_layout == "BAYER" or getattr(
            profile,
            "channel_layout",
            None,
        ) == "BAYER"
        labels = ("R", "Gr", "Gb", "B") if is_bayer else ("R", "G", "B")
        placeholders = [
            ImageDocument(
                source_path=document.source_path,
                display_name=f"{document.display_name} · {label}",
                source=None,
                channel_layout=f"CHANNEL_{label}",
                bit_depth=document.bit_depth,
                raw_profile=profile,
                display_transform=document.display_transform,
                document_id=f"{document.document_id}:split:{label}",
                loading_state=document.loading_state,
                error_state=document.error_state,
                generation=document.generation,
            )
            for label in labels
        ]
        return placeholders, False

    def _set_split_channels(self, enabled: bool) -> None:
        self._split_channels = enabled
        if enabled:
            self._layout_mode = "Multi View"
            self._view_capacity = 4
        self._reset_pixel_status()
        self._render_selection(preserve_view=False)

'''
    text = _replace_between(
        text,
        "    def _set_split_channels(self, enabled: bool) -> None:\n",
        "    def compare_selection(self) -> None:\n",
        split_helpers,
    )

    effective_layout = '''    def _effective_layout(self, count: int) -> tuple[str, int]:
        if self._layout_mode == "Single View":
            return "Single", 1
        if count <= 1:
            return ("Grid 2x2", 4) if self._split_channels else ("Single", 1)
        if count == 2:
            return "Side by Side", 2
        if count == 3:
            return "Focus + 2", 4
        if count == 4:
            return "Grid 2x2", 4
        return "Grid 3x2", 6

'''
    text = _replace_between(
        text,
        "    def _effective_layout(self, count: int) -> tuple[str, int]:\n",
        "    def _update_layout_options(self, count: int) -> None:\n",
        effective_layout,
    )

    difference_visible = '''    def _set_difference_visible(self, enabled: bool) -> None:
        if enabled:
            cached = self.difference_panel.cached_display_for_current()
            if cached is None:
                self.diff_action.blockSignals(True)
                self.diff_action.setChecked(False)
                self.diff_action.blockSignals(False)
                return
            self._store_difference_document(*cached, switch_to_result=False)
            if len(self.selected_documents) >= 6:
                self._capture_six_image_diff_restore_state()
                self._navigate_single_view("difference")
                self._update_action_states()
                return
            if self._layout_mode == "Single View":
                self._navigate_single_view("difference")
                if self._difference_document is not None:
                    self._set_active_document(self._difference_document)
                self._update_action_states()
                return
            self._layout_mode = "Multi View"
            if self._difference_document is not None:
                self._focus_document_id = self._difference_document.document_id
                self._promote_multi_document(self._difference_document.document_id)
            self.layout_selector.blockSignals(True)
            self.layout_selector.setCurrentText("Multi View")
            self.layout_selector.blockSignals(False)
        elif self._six_image_diff_restore_state is not None:
            self._restore_six_image_diff_workspace()
            return
        elif self.viewer.document is self._difference_document:
            self._current_index = 0
        self._render_selection(preserve_view=True)
        self._update_action_states()

'''
    text = _replace_between(
        text,
        "    def _set_difference_visible(self, enabled: bool) -> None:\n",
        "    def _capture_six_image_diff_restore_state(self) -> None:\n",
        difference_visible,
    )

    old_cycle_candidates = '''            candidates = (
                [self._difference_document, *documents]
                if len(documents) == 2
                else [*documents, self._difference_document]
            )
'''
    text = _replace_once(
        text,
        old_cycle_candidates,
        "            candidates = [self._difference_document, *documents]\n",
        "visible focus Difference ordering",
    )

    difference_ready = '''    def _difference_panel_ready(
        self,
        title: object,
        numerical: object,
        preview: object,
    ) -> None:
        if (
            not isinstance(title, str)
            or not isinstance(numerical, np.ndarray)
            or not isinstance(preview, np.ndarray)
        ):
            return
        force_single = len(self.selected_documents) >= 6
        if force_single:
            self._capture_six_image_diff_restore_state()
        stay_single = force_single or self._layout_mode == "Single View"
        self._store_difference_document(
            title,
            numerical,
            preview,
            switch_to_result=stay_single,
        )
        self.diff_action.blockSignals(True)
        self.diff_action.setChecked(True)
        self.diff_action.blockSignals(False)
        if stay_single:
            self._set_single_navigation("difference")
            if self._difference_document is not None:
                self._set_active_document(self._difference_document)
            self._update_action_states()
            self.statusBar().showMessage(f"Ready: {title}", 4000)
            return

        self._layout_mode = "Multi View"
        if self._difference_document is not None:
            self._focus_document_id = self._difference_document.document_id
            self._promote_multi_document(self._difference_document.document_id)
        self._pending_pair_focus = None
        self.layout_selector.blockSignals(True)
        self.layout_selector.setCurrentText("Multi View")
        self.layout_selector.blockSignals(False)
        self._render_selection(preserve_view=True)
        self.statusBar().showMessage(f"Ready: {title}", 4000)

'''
    text = _replace_between(
        text,
        "    def _difference_panel_ready(\n",
        "    def _difference_preview_updated(\n",
        difference_ready,
    )

    text = _replace_once(
        text,
        "        self.central_stack.setCurrentWidget(self.viewer)\n"
        "        self.statusBar().showMessage(f\"Ready: {title}\", 4000)\n\n"
        "    def fit_image(self) -> None:\n",
        "        self.central_stack.setCurrentWidget(self.viewer)\n"
        "        self._set_active_document(difference)\n"
        "        self.statusBar().showMessage(f\"Ready: {title}\", 4000)\n\n"
        "    def fit_image(self) -> None:\n",
        "single Difference active-document update",
    )
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the reviewed P0-D workspace patch")
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
            raise SystemExit("P0-D workspace patch is not applied")
        print("P0-D workspace patch is applied")
        return 0
    if not changed:
        print("P0-D workspace patch was already applied")
        return 0
    TARGET.write_text(updated, encoding="utf-8")
    print(f"Applied P0-D workspace patch to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
