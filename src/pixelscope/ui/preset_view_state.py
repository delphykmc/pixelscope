"""Revocable, runtime-only W05 view continuity; never durable Review bindings."""
from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, QTimer

from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.image_viewer import ImageViewer


@dataclass(frozen=True)
class SourceViewport:
    document: weakref.ReferenceType[ImageDocument]
    generation: int
    shape: tuple[int, int]
    percent: float
    center: tuple[float, float]

    def matches(self, document: ImageDocument) -> bool:
        return (
            self.document() is document
            and self.generation == document.generation
            and self.shape == document.reference_shape
            and document.error_state is None
        )


class PresetViewState(QObject):
    """MainWindow-owned live geometry, guarded by the existing W04 restore epoch."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self._window = weakref.ref(window)
        self.sources: dict[str, SourceViewport] = {}
        self._binding: tuple[tuple[str, int, int], ...] = ()
        self._epoch: int | None = None
        self._attempts = 0
        self._closed = False
        self.status = "idle"
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._restore)  # type: ignore[attr-defined]
        window.sync_action.toggled.connect(self.cancel)
        for viewer in [window.viewer, *window.multi_compare_view.viewers]:
            viewer.view_box.user_navigation_started.connect(self.cancel)
            viewer.activated.connect(self.cancel)

    def _signature(self) -> tuple[tuple[str, int, int], ...]:
        window = self._window()
        if window is None:
            return ()
        return tuple(
            (d.document_id, id(d), d.generation) for d in window.current_comparison_documents()
        )

    def _viewers(self) -> list[ImageViewer]:
        window = self._window()
        if window is None:
            return []
        if window.central_stack.currentWidget() is window.viewer:
            return [window.viewer]
        return list(window.multi_compare_view.occupied_viewers)

    @staticmethod
    def _capture(viewer: ImageViewer) -> SourceViewport | None:
        document = viewer.document
        if (
            document is None
            or viewer.presented_document is not document
            or document.preview is None
            or document.error_state is not None
            or viewer._geometry_timer.isActive()
            or viewer._display_preview_worker is not None
        ):
            return None
        measurement = viewer.measure_physical_zoom()
        if not measurement.valid or measurement.percent is None:
            return None
        x, y = viewer.view_box.viewRange()
        return SourceViewport(
            weakref.ref(document),
            document.generation,
            document.reference_shape,
            measurement.percent,
            ((x[0] + x[1]) / 2, (y[0] + y[1]) / 2),
        )

    def capture(self) -> None:
        window = self._window()
        if window is None:
            return
        signature = self._signature()
        if signature != self._binding:
            self.cancel()
            self.sources.clear()
            self._binding = signature
        if self._closed or self._epoch is not None:
            return
        page_ids = {row[0] for row in signature}
        page = {d.document_id: d for d in window.current_comparison_documents()}
        self.sources = {
            key: record
            for key, record in self.sources.items()
            if key in page and record.matches(page[key])
        }
        for viewer in self._viewers():
            record = self._capture(viewer)
            document = viewer.document
            if record is not None and document is not None and document.document_id in page_ids:
                self.sources[document.document_id] = record

    def cancel(self, *_args: object) -> None:
        self.timer.stop()
        window = self._window()
        epoch, self._epoch = self._epoch, None
        if epoch is not None:
            self.status = "interrupted"
            if window is not None:
                window.multi_compare_view.cancel_review_restore()

    def request(self) -> None:
        self.cancel()
        window = self._window()
        if self._closed or window is None or self._signature() != self._binding:
            return
        multi = window.multi_compare_view
        epoch = multi._review_restore_epoch + 1
        if not self.sources or not multi.begin_review_restore(epoch):
            return
        self._epoch = epoch
        self._attempts = 0
        self.status = "pending"
        self.timer.start(0)

    def _restore(self) -> None:
        window = self._window()
        epoch = self._epoch
        if self._closed or window is None or epoch is None:
            return
        multi = window.multi_compare_view
        if (
            window._closing
            or self._signature() != self._binding
            or multi._review_restore_pending_epoch != epoch
        ):
            self.cancel()
            return
        viewers = self._viewers()
        is_multi = window.central_stack.currentWidget() is multi
        if (is_multi and multi._layout_refit_active) or any(
            self._capture(v) is None for v in viewers
        ):
            self._attempts += 1
            if self._attempts < 120:
                self.timer.start(16)
            else:
                self.cancel()
                self.status = "unavailable"
                window.statusBar().showMessage(
                    "Preset view restore unavailable: layout/load not settled", 5000
                )
            return
        targets = [
            (v, self.sources[v.document.document_id])
            for v in viewers
            if v.document is not None
            and v.document.document_id in self.sources
            and self.sources[v.document.document_id].matches(v.document)
        ]
        shared: SourceViewport | None = None
        if multi.sync_enabled:
            if targets:
                shared = targets[0][1]
            else:
                for document in window.current_comparison_documents():
                    candidate = self.sources.get(document.document_id)
                    if candidate is not None and candidate.matches(document):
                        shared = candidate
                        break
            if shared is not None:
                # Newly visible originals (and the canonically validated current
                # Difference mapping) must share the anchor, not only old tiles.
                targets = [(viewer, shared) for viewer in viewers]
        if not targets:
            self.cancel()
            self.status = "not-required"
            return
        if is_multi and not multi._begin_review_apply(epoch):
            self.cancel()
            return
        backup = [(v, self._capture(v)) for v, _record in targets]
        prior_syncing = multi._syncing_range
        multi._syncing_range = True
        multi._review_restoring = True
        try:
            for viewer, record in targets:
                if self._epoch != epoch or multi._review_restore_pending_epoch != epoch:
                    return
                target = shared or record
                result = viewer.set_physical_zoom(target.percent, target.center)
                if not result.achieved:
                    raise ValueError("physical zoom not achieved")
            if self._epoch != epoch or multi._review_restore_pending_epoch != epoch:
                return
            multi._finish_review_apply(epoch)
            multi._review_restore_pending_epoch = None
            self._epoch = None
            self.status = "applied"
        except (RuntimeError, ValueError):
            self.cancel()
            if not is_multi:
                for viewer, original in backup:
                    if original is not None:
                        viewer.set_physical_zoom(original.percent, original.center)
            self.status = "unavailable"
            window.statusBar().showMessage(
                "Preset view restore failed; view changes rolled back", 5000
            )
        finally:
            multi._syncing_range = prior_syncing
            multi._review_restoring = False

    def shutdown(self) -> None:
        self.cancel()
        self.sources.clear()
        self._closed = True
