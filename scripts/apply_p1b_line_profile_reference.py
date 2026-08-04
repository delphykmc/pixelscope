from __future__ import annotations

from pathlib import Path

LINE_PROFILE_PANEL = Path("src/pixelscope/ui/line_profile_panel.py")
MAIN_WINDOW = Path("src/pixelscope/app/main_window.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_line_profile(text: str) -> str:
    marker = "        self.reference_selector = QComboBox()\n"
    if marker in text:
        print("Line Profile reference selector already applied")
        return text

    text = replace_once(
        text,
        """        self._profile_series: list[
            list[tuple[int, str, NDArray[np.float64], NDArray[np.float64]]]
        ] = [[] for _index in range(6)]

        self.status = QLabel("Alt+drag on an image to set a line profile")
""",
        """        self._profile_series: list[
            list[tuple[int, str, NDArray[np.float64], NDArray[np.float64]]]
        ] = [[] for _index in range(6)]
        self._reference_document_id: str | None = None
        self._reference_priority_ids: tuple[str, ...] = ()
        self._reference_locked = False

        self.status = QLabel("Alt+drag on an image to set a line profile")
""",
        "Line Profile reference state",
    )

    text = replace_once(
        text,
        """        self.x_mode = QComboBox()
        self.x_mode.addItems(("Distance px", "Normalized distance"))
        self.channel_buttons: dict[str, QToolButton] = {}
""",
        """        self.x_mode = QComboBox()
        self.x_mode.addItems(("Distance px", "Normalized distance"))
        self.reference_label = QLabel("Reference")
        self.reference_selector = QComboBox()
        self.reference_selector.setMaximumWidth(280)
        self.reference_label.hide()
        self.reference_selector.hide()
        self.channel_buttons: dict[str, QToolButton] = {}
""",
        "Line Profile reference controls",
    )

    text = replace_once(
        text,
        """            combo.setMaximumWidth(170)
        controls.addWidget(QLabel("Channels"))
""",
        """            combo.setMaximumWidth(170)
        controls.addWidget(self.reference_label)
        controls.addWidget(self.reference_selector)
        controls.addSpacing(TOKENS.spacing_lg)
        controls.addWidget(QLabel("Channels"))
""",
        "Line Profile reference control layout",
    )

    text = replace_once(
        text,
        """        for combo in (self.view_mode, self.y_mode, self.x_mode):
            combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
                self._plot_options_changed
            )
        controls.addStretch(1)
""",
        """        for combo in (self.view_mode, self.y_mode, self.x_mode):
            combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
                self._plot_options_changed
            )
        self.reference_selector.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._reference_changed
        )
        controls.addStretch(1)
""",
        "Line Profile reference signal",
    )

    text = replace_once(
        text,
        """    def set_documents(
        self, documents: list[ImageDocument], selection: LineSelection | None
    ) -> None:
        self._documents = [document for document in documents if document.source is not None]
        self._selection = selection
        self.refresh()
""",
        """    def set_documents(
        self,
        documents: list[ImageDocument],
        selection: LineSelection | None,
        *,
        reference_priority_ids: tuple[str, ...] = (),
    ) -> None:
        self._documents = [document for document in documents if document.source is not None]
        self._selection = selection
        self._reference_priority_ids = reference_priority_ids
        self._sync_reference_selector()
        self.refresh()

    def set_reference_priority_ids(self, document_ids: tuple[str, ...]) -> None:
        previous_id = self._reference_document_id
        self._reference_priority_ids = document_ids
        self._sync_reference_selector()
        if (
            previous_id != self._reference_document_id
            and self.last_results
            and self.y_mode.currentText() == "Difference from reference"
        ):
            self._render(self.last_results)
""",
        "Line Profile set_documents signature",
    )

    text = replace_once(
        text,
        """        self._documents = []
        self._selection = None
        self._request_signature = ()
        self.last_results = ()
        self._clear_plot()
""",
        """        self._documents = []
        self._selection = None
        self._reference_priority_ids = ()
        self._sync_reference_selector()
        self._request_signature = ()
        self.last_results = ()
        self._clear_plot()
""",
        "Line Profile clear reference reset",
    )

    text = replace_once(
        text,
        """    def _plot_options_changed(self, _index: int) -> None:
        if self.last_results:
            self._render(self.last_results)

    def _render(self, results: tuple[LineProfileResult, ...]) -> None:
""",
        """    def _plot_options_changed(self, _index: int) -> None:
        if self.y_mode.currentText() == "Difference from reference":
            self._reference_locked = self._reference_document_id is not None
        self._sync_reference_selector()
        if self.last_results:
            self._render(self.last_results)

    def _reference_changed(self, index: int) -> None:
        if index < 0:
            return
        document_id = self.reference_selector.itemData(index)
        if not isinstance(document_id, str):
            return
        changed = document_id != self._reference_document_id
        self._reference_document_id = document_id
        self._reference_locked = True
        if changed and self.last_results:
            self._render(self.last_results)

    def _sync_reference_selector(self) -> None:
        available_ids = [document.document_id for document in self._documents]
        selected_id = self._reference_document_id
        if selected_id not in available_ids:
            selected_id = None
            self._reference_locked = False
        if selected_id is None or not self._reference_locked:
            selected_id = next(
                (
                    document_id
                    for document_id in self._reference_priority_ids
                    if document_id in available_ids
                ),
                available_ids[0] if available_ids else None,
            )
        self._reference_document_id = selected_id
        if (
            selected_id is not None
            and self.y_mode.currentText() == "Difference from reference"
        ):
            self._reference_locked = True

        self.reference_selector.blockSignals(True)
        self.reference_selector.clear()
        for index, document in enumerate(self._documents):
            label = f"{index + 1} · {self._document_label(document)}"
            self.reference_selector.addItem(label, document.document_id)
        selected_index = self.reference_selector.findData(selected_id)
        if selected_index >= 0:
            self.reference_selector.setCurrentIndex(selected_index)
        self.reference_selector.blockSignals(False)
        self._update_reference_visibility()

    def _update_reference_visibility(self) -> None:
        visible = self.y_mode.currentText() == "Difference from reference"
        self.reference_label.setVisible(visible)
        self.reference_selector.setVisible(visible)
        self.reference_selector.setEnabled(bool(self._documents))

    def _reference_index(
        self, results: tuple[LineProfileResult, ...]
    ) -> int | None:
        if self._reference_document_id is None:
            return None
        for index, document in enumerate(self._documents[: len(results)]):
            if document.document_id == self._reference_document_id:
                return index
        return None

    def _render(self, results: tuple[LineProfileResult, ...]) -> None:
""",
        "Line Profile reference methods",
    )

    text = replace_once(
        text,
        """        elif self.y_mode.currentText() == "Difference from reference" and image_index > 0:
            reference = results[0]
            if channel_name in reference.channel_names:
                reference_index = reference.channel_names.index(channel_name)
                reference_x = reference.positions[reference_index]
                reference_y = reference.values[reference_index]
                y_values = y_values - np.interp(positions, reference_x, reference_y)
""",
        """        elif self.y_mode.currentText() == "Difference from reference":
            reference_result_index = self._reference_index(results)
            if reference_result_index is not None:
                if image_index == reference_result_index:
                    y_values = np.zeros_like(y_values)
                else:
                    reference = results[reference_result_index]
                    if channel_name in reference.channel_names:
                        reference_index = reference.channel_names.index(channel_name)
                        reference_x = reference.positions[reference_index]
                        reference_y = reference.values[reference_index]
                        y_values = y_values - np.interp(
                            positions,
                            reference_x,
                            reference_y,
                        )
""",
        "chosen-reference profile transform",
    )
    return text


def patch_main_window(text: str) -> str:
    marker = "    def _line_reference_priority_ids(\n"
    if marker in text:
        print("MainWindow reference-priority wiring already applied")
        return text

    text = replace_once(
        text,
        """        self.line_profile_panel.set_documents(
            self._line_source_documents(),
            self._shared_line,
        )
        active = self.current_document
        if self._view_capacity > 1 and self._focus_document_id is not None:
            active = next(
                (
                    document
                    for document in visible_state
                    if document.document_id == self._focus_document_id
                ),
                active,
            )
""",
        """        active = self.current_document
        if self._view_capacity > 1 and self._focus_document_id is not None:
            active = next(
                (
                    document
                    for document in visible_state
                    if document.document_id == self._focus_document_id
                ),
                active,
            )
        line_sources = self._line_source_documents()
        self.line_profile_panel.set_documents(
            line_sources,
            self._shared_line,
            reference_priority_ids=self._line_reference_priority_ids(
                visible_state,
                active,
            ),
        )
""",
        "MainWindow Line Profile reference call",
    )

    text = replace_once(
        text,
        """    def _line_source_documents(
        self, visible_documents: list[ImageDocument] | None = None
    ) -> list[ImageDocument]:
        del visible_documents
        return [document for document in self.selected_documents[:6] if document.source is not None]

    def _set_active_document(self, document: object) -> None:
""",
        """    def _line_source_documents(
        self, visible_documents: list[ImageDocument] | None = None
    ) -> list[ImageDocument]:
        del visible_documents
        return [document for document in self.selected_documents[:6] if document.source is not None]

    def _line_reference_priority_ids(
        self,
        visible_documents: Sequence[ImageDocument],
        active_document: ImageDocument | None,
    ) -> tuple[str, ...]:
        source_ids = {
            document.document_id for document in self._line_source_documents()
        }
        first_displayed_id = next(
            (
                document.document_id
                for document in visible_documents
                if document.document_id in source_ids
            ),
            None,
        )
        candidates = (
            self._focus_document_id,
            active_document.document_id if active_document is not None else None,
            first_displayed_id,
        )
        ordered: list[str] = []
        for document_id in candidates:
            if (
                document_id is not None
                and document_id in source_ids
                and document_id not in ordered
            ):
                ordered.append(document_id)
        return tuple(ordered)

    def _set_active_document(self, document: object) -> None:
""",
        "MainWindow Line Profile priority helper",
    )

    text = replace_once(
        text,
        """        visible = [
            viewer.document
            for viewer in self.multi_compare_view.occupied_viewers
            if viewer.document is not None
        ]
        self._update_file_states(visible, document)
""",
        """        visible = [
            viewer.document
            for viewer in self.multi_compare_view.occupied_viewers
            if viewer.document is not None
        ]
        self.line_profile_panel.set_reference_priority_ids(
            self._line_reference_priority_ids(visible, document)
        )
        self._update_file_states(visible, document)
""",
        "active-tile Line Profile priority refresh",
    )
    return text


def apply(path: Path, patcher: object) -> None:
    original = path.read_text(encoding="utf-8")
    updated = patcher(original)  # type: ignore[operator]
    if updated == original:
        print(f"No changes required: {path}")
        return
    path.write_text(updated, encoding="utf-8")
    print(f"Updated: {path}")


def main() -> int:
    apply(LINE_PROFILE_PANEL, patch_line_profile)
    apply(MAIN_WINDOW, patch_main_window)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
