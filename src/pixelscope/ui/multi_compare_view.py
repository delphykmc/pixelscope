from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from PySide6.QtCore import Signal
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import QGridLayout, QWidget

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.image_viewer import ImageViewer


@dataclass(frozen=True)
class MultiCompareViewState:
    """Display-only state retained while another workspace page is shown."""

    active_document_id: str | None
    ranges: tuple[tuple[float, float], tuple[float, float]] | None


class MultiCompareView(QWidget):
    """Synchronized 2/4/6-slot viewer for one comparison page."""

    cursor_moved = Signal(object, int, int, object)
    roi_changed = Signal(object)
    roi_cleared = Signal()
    line_changed = Signal(object)
    line_cleared = Signal()
    active_document_changed = Signal(object)
    zoom_changed = Signal(float)
    focus_document_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.capacity = 0
        self._syncing_range = False
        self._setting_documents = False
        self._layout_refit_active = False
        self._document_count = 0
        self._arranged_count = -1
        self._primary_controls_enabled = False
        self._active_viewer: ImageViewer | None = None
        self.sync_enabled = True
        self.layout_kind = "Auto"
        self.focus_document_id: str | None = None
        self.viewers = [ImageViewer() for _ in range(6)]
        self._presentation_viewers = list(self.viewers)
        self._presentation_document_ids: tuple[str, ...] = ()
        self._presentation_has_difference = False
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(3)
        for viewer in self.viewers:
            viewer.cursor_moved.connect(
                lambda x, y, value, active=viewer: self._on_cursor(active, x, y, value)
            )
            viewer.activated.connect(self._activate_viewer)
            viewer.focus_requested.connect(self._request_focus)
            viewer.zoom_changed.connect(self.zoom_changed)
            viewer.roi_changed.connect(self.roi_changed)
            viewer.roi_cleared.connect(self.roi_cleared)
            viewer.line_changed.connect(self.line_changed)
            viewer.line_cleared.connect(self.line_cleared)
            viewer.view_box.sigRangeChanged.connect(
                lambda _box, ranges, _changed=None, active=viewer: self._sync_range(active, ranges)
            )
        self.set_capacity(2)

    @property
    def visible_viewers(self) -> list[ImageViewer]:
        return self._presentation_viewers[: self.capacity]

    @property
    def occupied_viewers(self) -> list[ImageViewer]:
        return [
            viewer
            for viewer in self.visible_viewers
            if viewer.document is not None and not viewer.isHidden()
        ]

    def set_capacity(self, capacity: int) -> None:
        if capacity not in (2, 4, 6):
            raise ValueError("comparison capacity must be 2, 4, or 6")
        if capacity == self.capacity:
            return
        shrinking_diff_presentation = (
            capacity < self.capacity and self._presentation_has_difference
        )
        self.capacity = capacity
        if shrinking_diff_presentation:
            # MainWindow immediately follows a Difference capacity change with
            # set_documents(). Deferring the hide step prevents a retained source
            # from briefly leaving the active set and releasing its gained preview.
            self._arranged_count = -1
            return
        self._arrange_viewers(min(self._document_count, capacity))

    def set_documents(
        self,
        documents: list[ImageDocument],
        start_index: int,
        total: int,
        roi: RoiBounds | None,
        line: LineSelection | None,
        preserve_view: bool = False,
        slot_by_id: dict[str, int] | None = None,
        fixed_geometry_count: int | None = None,
        local_slots: bool = False,
    ) -> None:
        previous_active_id = (
            self._active_viewer.document.document_id
            if preserve_view
            and self._active_viewer is not None
            and self._active_viewer.document is not None
            else None
        )
        requires_refit = not preserve_view or self._layout_refit_active
        self._layout_refit_active = requires_refit
        for viewer in self.viewers:
            if requires_refit:
                viewer.begin_layout_refit()
            else:
                viewer.end_layout_refit()
        anchor_range = self._current_shared_range() if not requires_refit else None
        self._prepare_viewers_for_documents(documents)
        self._setting_documents = True
        self._document_count = min(len(documents), self.capacity)
        geometry_count = min(
            fixed_geometry_count if fixed_geometry_count is not None else self._document_count,
            self.capacity,
        )
        displayed_documents = documents[: self._document_count]
        # Every multi-image representation, including split-channel views,
        # exposes the same explicit Primary interaction. MainWindow owns the
        # semantic mapping for source comparisons versus derived channel views.
        self._primary_controls_enabled = self._document_count > 1
        displayed_ids = {document.document_id for document in displayed_documents}
        if self._primary_controls_enabled and self.focus_document_id not in displayed_ids:
            self.focus_document_id = displayed_documents[0].document_id
        elif not self._primary_controls_enabled:
            self.focus_document_id = None
        updates_were_enabled = self.updatesEnabled()
        if updates_were_enabled:
            self.setUpdatesEnabled(False)
        try:
            self._arrange_viewers(geometry_count)
            self._layout.activate()
            controls_realized = self.isVisible() or geometry_count in (3, 5)
            for slot, viewer in enumerate(self.visible_viewers):
                document = documents[slot] if slot < len(documents) else None
                role = ""
                if document is not None and document.channel_layout == "DIFFERENCE":
                    role = "Diff"
                logical_slot = (
                    slot_by_id.get(document.document_id, start_index + slot + 1)
                    if document is not None and slot_by_id is not None
                    else start_index + slot + 1
                )
                viewer.set_tile_context(logical_slot, role)
                viewer.set_focus(
                    document is not None and document.document_id == self.focus_document_id
                )
                viewer.set_focus_control_visible(
                    document is not None and self._primary_controls_enabled and controls_realized
                )
                viewer.set_document(document, fit=not preserve_view)
                if document is None:
                    viewer.set_header("")
                else:
                    if role == "Diff":
                        position = "Diff"
                    elif local_slots:
                        position = str(logical_slot)
                    else:
                        position = f"{logical_slot}/{total}"
                    viewer.set_header(f"[{position}] {document.display_name}")
                viewer.set_roi_bounds(roi)
                viewer.set_line_selection(line)
        finally:
            if updates_were_enabled:
                self.setUpdatesEnabled(True)
            self._setting_documents = False
        if updates_were_enabled:
            self.update()
        active = next(
            (
                viewer
                for viewer in self.visible_viewers
                if viewer.document is not None and viewer.document.document_id == previous_active_id
            ),
            None,
        ) or next((viewer for viewer in self.visible_viewers if viewer.document), None)
        if active is not None:
            self._activate_viewer(active)
        if anchor_range is not None:
            self._apply_range(anchor_range)
        elif documents and all(document.preview is not None for document in documents):
            self.fit_images()
            self._finish_layout_refit()
        elif not documents or all(
            document.loading_state not in ("pending", "loading") for document in documents
        ):
            self._finish_layout_refit()

    def _prepare_viewers_for_documents(self, documents: list[ImageDocument]) -> None:
        target_documents = documents[: self.capacity]
        target_ids = tuple(document.document_id for document in target_documents)
        target_has_difference = any(
            document.channel_layout == "DIFFERENCE" for document in target_documents
        )
        if target_ids == self._presentation_document_ids:
            return

        if target_has_difference != self._presentation_has_difference:
            self._reuse_viewers_for_documents(target_documents)
        else:
            self._set_presentation_viewers(list(self.viewers))
        self._presentation_document_ids = target_ids
        self._presentation_has_difference = target_has_difference

    def _set_presentation_viewers(self, viewers: list[ImageViewer]) -> None:
        previous_ids = tuple(id(viewer) for viewer in self._presentation_viewers)
        next_ids = tuple(id(viewer) for viewer in viewers)
        if next_ids == previous_ids:
            return
        self._presentation_viewers = viewers
        self._arranged_count = -1

    def _reuse_viewers_for_documents(self, documents: list[ImageDocument]) -> None:
        """Keep retained sources on their viewers while Difference membership changes."""

        by_document_id: dict[str, ImageViewer] = {}
        for viewer in self.viewers:
            presented = viewer.presented_document
            if presented is not None and presented.document_id not in by_document_id:
                by_document_id[presented.document_id] = viewer

        used_viewer_ids: set[int] = set()
        ordered: list[ImageViewer | None] = []
        for document in documents:
            reusable = by_document_id.get(document.document_id)
            if reusable is None or id(reusable) in used_viewer_ids:
                ordered.append(None)
                continue
            ordered.append(reusable)
            used_viewer_ids.add(id(reusable))

        remaining = [viewer for viewer in self.viewers if id(viewer) not in used_viewer_ids]
        filled: list[ImageViewer] = []
        for reusable in ordered:
            filled.append(remaining.pop(0) if reusable is None else reusable)
        self._set_presentation_viewers([*filled, *remaining])

    def set_shared_roi(self, bounds: RoiBounds | None) -> None:
        for viewer in self.visible_viewers:
            viewer.set_roi_bounds(bounds)

    def refresh_document(self, document: ImageDocument) -> bool:
        """Upload a changed preview only to the tile currently displaying it."""

        viewer = next(
            (
                candidate
                for candidate in self.occupied_viewers
                if candidate.document is document
                or (
                    candidate.document is not None
                    and candidate.document.document_id == document.document_id
                )
            ),
            None,
        )
        if viewer is None:
            return False
        viewer.set_document(document, fit=False)
        viewer.set_header(document.display_name)
        return True

    def set_shared_line(self, selection: LineSelection | None) -> None:
        for viewer in self.visible_viewers:
            viewer.set_line_selection(selection)

    def fit_images(self) -> None:
        anchor = next(
            (viewer for viewer in self.visible_viewers if viewer.document is not None),
            None,
        )
        if anchor is None:
            return
        self._syncing_range = True
        try:
            anchor.fit_image()
            self._apply_range(anchor.view_box.viewRange())
        finally:
            self._syncing_range = False

    def zoom_100_percent(self) -> None:
        anchor = next(
            (viewer for viewer in self.visible_viewers if viewer.document is not None),
            None,
        )
        if anchor is None:
            return
        self._syncing_range = True
        try:
            anchor.zoom_100_percent()
            self._apply_range(anchor.view_box.viewRange())
        finally:
            self._syncing_range = False

    def zoom_by(self, factor: float) -> None:
        anchor = self._active_viewer or next(
            (viewer for viewer in self.visible_viewers if viewer.document is not None),
            None,
        )
        if anchor is not None:
            anchor.zoom_by(factor)

    def clear_roi(self) -> None:
        for viewer in self.visible_viewers:
            viewer.set_roi_bounds(None)

    def clear_line(self) -> None:
        for viewer in self.visible_viewers:
            viewer.set_line_selection(None)

    def set_sync_enabled(self, enabled: bool) -> None:
        self.sync_enabled = enabled

    def set_layout_kind(self, kind: str, focus_document_id: str | None = None) -> None:
        self.layout_kind = kind
        self.focus_document_id = focus_document_id

    def capture_view_state(self) -> MultiCompareViewState:
        ranges = self._current_shared_range()
        active_document_id = (
            self._active_viewer.document.document_id
            if self._active_viewer is not None and self._active_viewer.document is not None
            else None
        )
        return MultiCompareViewState(
            active_document_id=active_document_id,
            ranges=(
                (float(ranges[0][0]), float(ranges[0][1])),
                (float(ranges[1][0]), float(ranges[1][1])),
            )
            if ranges is not None
            else None,
        )

    def restore_view_state(self, state: MultiCompareViewState) -> None:
        if state.ranges is not None:
            self._apply_range(state.ranges)
        if state.active_document_id is not None:
            active = next(
                (
                    viewer
                    for viewer in self.occupied_viewers
                    if viewer.document is not None
                    and viewer.document.document_id == state.active_document_id
                ),
                None,
            )
            if active is not None:
                self._activate_viewer(active)

    def enable_cursor(self, enabled: bool) -> None:
        for viewer in self.viewers:
            viewer.enable_cursor(enabled)

    def set_interaction_mode(self, mode: str) -> None:
        for viewer in self.viewers:
            viewer.set_interaction_mode(mode)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_primary_control_visibility(True)

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._sync_primary_control_visibility(False)
        super().hideEvent(event)

    def _sync_primary_control_visibility(self, workspace_visible: bool) -> None:
        for viewer in self.viewers:
            viewer.set_focus_control_visible(
                workspace_visible
                and self._primary_controls_enabled
                and viewer.document is not None
                and not viewer.isHidden()
            )

    def _on_cursor(self, viewer: ImageViewer, x: int, y: int, value: object) -> None:
        document = viewer.document
        if document is None:
            return
        for candidate in self.visible_viewers:
            if candidate.document is not None:
                candidate.show_cursor(x, y)
        self.cursor_moved.emit(document, x, y, value)

    def _sync_range(self, source: ImageViewer, ranges: Any) -> None:
        if self._syncing_range or self._setting_documents:
            return
        if self._layout_refit_active:
            return
        if not isinstance(ranges, list | tuple) or len(ranges) != 2:
            return
        self._syncing_range = True
        try:
            if self.sync_enabled:
                self._apply_range(ranges, source)
        finally:
            self._syncing_range = False

    def _current_shared_range(self) -> list[list[float]] | None:
        for viewer in self.visible_viewers:
            if viewer.document is not None and viewer.document.preview is not None:
                return cast(list[list[float]], viewer.view_box.viewRange())
        return None

    def _finish_layout_refit(self) -> None:
        self._layout_refit_active = False
        for viewer in self.viewers:
            viewer.end_layout_refit()

    def _apply_range(self, ranges: Any, source: ImageViewer | None = None) -> None:
        anchor = source or next(
            (viewer for viewer in self.visible_viewers if viewer.document is not None),
            None,
        )
        if anchor is None:
            return
        pixel_width, pixel_height = anchor.view_box.viewPixelSize()
        center_x = (float(ranges[0][0]) + float(ranges[0][1])) / 2.0
        center_y = (float(ranges[1][0]) + float(ranges[1][1])) / 2.0
        for viewer in self.visible_viewers:
            if viewer is not source and viewer.document is not None:
                view_width = max(float(viewer.view_box.width()), 1.0)
                view_height = max(float(viewer.view_box.height()), 1.0)
                half_width = pixel_width * view_width / 2.0
                half_height = pixel_height * view_height / 2.0
                viewer.view_box.setRange(
                    xRange=(center_x - half_width, center_x + half_width),
                    yRange=(center_y - half_height, center_y + half_height),
                    padding=0,
                )

    def _activate_viewer(self, viewer: object) -> None:
        if not isinstance(viewer, ImageViewer) or viewer.document is None:
            return
        self._active_viewer = viewer
        for candidate in self.viewers:
            candidate.set_active(candidate is viewer)
        self.active_document_changed.emit(viewer.document)

    def _request_focus(self, viewer: object) -> None:
        if isinstance(viewer, ImageViewer) and viewer.document is not None:
            self.focus_document_requested.emit(viewer.document)

    def _arrange_viewers(self, count: int) -> None:
        if count == self._arranged_count:
            return
        self._arranged_count = count
        for viewer in self.viewers:
            self._layout.removeWidget(viewer)
        if count <= 0:
            for viewer in self.viewers:
                viewer.hide()
            return

        active = self.visible_viewers[:count]
        active_ids = {id(viewer) for viewer in active}
        for viewer in self.viewers:
            if id(viewer) not in active_ids and not viewer.isHidden():
                viewer.hide()

        placements, row_stretches, column_stretches = self._fixed_geometry(count)
        for viewer, (row, column, row_span, column_span) in zip(active, placements, strict=False):
            self._layout.addWidget(viewer, row, column, row_span, column_span)
            if viewer.isHidden():
                viewer.show()
        for row in range(3):
            self._layout.setRowStretch(row, row_stretches[row] if row < len(row_stretches) else 0)
        for column in range(3):
            self._layout.setColumnStretch(
                column,
                column_stretches[column] if column < len(column_stretches) else 0,
            )

    @staticmethod
    def _fixed_geometry(
        count: int,
    ) -> tuple[
        tuple[tuple[int, int, int, int], ...],
        tuple[int, ...],
        tuple[int, ...],
    ]:
        if count == 1:
            return ((0, 0, 1, 1),), (1,), (1,)
        if count == 2:
            return ((0, 0, 1, 1), (0, 1, 1, 1)), (1,), (1, 1)
        if count == 3:
            return (
                ((0, 0, 2, 1), (0, 1, 1, 1), (1, 1, 1, 1)),
                (1, 1),
                (1, 1),
            )
        if count == 4:
            return (
                tuple((index // 2, index % 2, 1, 1) for index in range(4)),
                (1, 1),
                (1, 1),
            )
        if count == 5:
            return (
                (
                    (0, 0, 2, 1),
                    (0, 1, 1, 1),
                    (1, 1, 1, 1),
                    (2, 0, 1, 1),
                    (2, 1, 1, 1),
                ),
                (1, 1, 1),
                (1, 1),
            )
        return (
            tuple((index // 2, index % 2, 1, 1) for index in range(6)),
            (1, 1, 1),
            (1, 1),
        )
