from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QGridLayout, QWidget

from pixelscope.core.image_document import ImageDocument
from pixelscope.core.line_profile import LineSelection
from pixelscope.core.roi import RoiBounds
from pixelscope.ui.image_viewer import ImageViewer


class MultiCompareView(QWidget):
    """Synchronized 2/4/6-slot viewer for one comparison page."""

    cursor_moved = Signal(object, int, int, object)
    roi_changed = Signal(object)
    roi_cleared = Signal()
    line_changed = Signal(object)
    line_cleared = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.capacity = 0
        self._syncing_range = False
        self._setting_documents = False
        self._fit_request = 0
        self.viewers = [ImageViewer() for _ in range(6)]
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(3)
        for viewer in self.viewers:
            viewer.cursor_moved.connect(
                lambda x, y, value, active=viewer: self._on_cursor(active, x, y, value)
            )
            viewer.roi_changed.connect(self.roi_changed)
            viewer.roi_cleared.connect(self.roi_cleared)
            viewer.line_changed.connect(self.line_changed)
            viewer.line_cleared.connect(self.line_cleared)
            viewer.view_box.sigRangeChanged.connect(
                lambda _box, ranges, active=viewer: self._sync_range(active, ranges)
            )
        self.set_capacity(2)

    @property
    def visible_viewers(self) -> list[ImageViewer]:
        return self.viewers[: self.capacity]

    def set_capacity(self, capacity: int) -> None:
        if capacity not in (2, 4, 6):
            raise ValueError("comparison capacity must be 2, 4, or 6")
        if capacity == self.capacity:
            return
        self.capacity = capacity
        rows = capacity // 2
        for viewer in self.viewers:
            self._layout.removeWidget(viewer)
            viewer.hide()
        for index, viewer in enumerate(self.visible_viewers):
            self._layout.addWidget(viewer, index // 2, index % 2)
            viewer.show()
        for row in range(3):
            self._layout.setRowStretch(row, 1 if row < rows else 0)
        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 1)

    def set_documents(
        self,
        documents: list[ImageDocument],
        start_index: int,
        total: int,
        roi: RoiBounds | None,
        line: LineSelection | None,
        preserve_view: bool = False,
    ) -> None:
        self._fit_request += 1
        fit_request = self._fit_request
        anchor_range = self._current_shared_range() if preserve_view else None
        self._setting_documents = True
        try:
            for slot, viewer in enumerate(self.visible_viewers):
                document = documents[slot] if slot < len(documents) else None
                viewer.set_document(document, fit=not preserve_view)
                if document is None:
                    viewer.set_header("")
                else:
                    viewer.set_header(f"[{start_index + slot + 1}/{total}] {document.display_name}")
                viewer.set_roi_bounds(roi)
                viewer.set_line_selection(line)
        finally:
            self._setting_documents = False
        if anchor_range is not None:
            self._apply_range(anchor_range)
        elif documents:
            QTimer.singleShot(0, lambda: self._run_scheduled_fit(fit_request))

    def set_shared_roi(self, bounds: RoiBounds | None) -> None:
        for viewer in self.visible_viewers:
            viewer.set_roi_bounds(bounds)

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

    def clear_roi(self) -> None:
        for viewer in self.visible_viewers:
            viewer.set_roi_bounds(None)

    def clear_line(self) -> None:
        for viewer in self.visible_viewers:
            viewer.set_line_selection(None)

    def _on_cursor(self, viewer: ImageViewer, x: int, y: int, value: object) -> None:
        document = viewer.document
        if document is None:
            return
        for candidate in self.visible_viewers:
            if candidate.document is not None:
                candidate.show_cursor(x, y)
        self.cursor_moved.emit(document, x, y, value)

    def _sync_range(self, source: ImageViewer, ranges: Any) -> None:
        if (
            self._syncing_range
            or self._setting_documents
            or not isinstance(ranges, list | tuple)
            or len(ranges) != 2
        ):
            return
        self._syncing_range = True
        try:
            self._apply_range(ranges, source)
        finally:
            self._syncing_range = False

    def _current_shared_range(self) -> list[list[float]] | None:
        for viewer in self.visible_viewers:
            if viewer.document is not None and viewer.document.preview is not None:
                return cast(list[list[float]], viewer.view_box.viewRange())
        return None

    def _run_scheduled_fit(self, request: int) -> None:
        if request == self._fit_request:
            self.fit_images()

    def _apply_range(self, ranges: Any, source: ImageViewer | None = None) -> None:
        for viewer in self.visible_viewers:
            if viewer is not source and viewer.document is not None:
                viewer.view_box.setRange(xRange=ranges[0], yRange=ranges[1], padding=0)
