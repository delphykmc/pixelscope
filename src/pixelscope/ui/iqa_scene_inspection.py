"""Viewer-linked schema-v2 Scene inspection without a second source/viewer authority."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Slot
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGraphicsItem,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixelscope.io.path_discovery import ImageInput
from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_explorer import ABSOLUTE_REFERENCE_ID
from pixelscope.remote.iqa_scene_inspection import (
    SceneVerificationOutcome,
    inspect_unavailable_reason,
    verify_scene_sources,
)
from pixelscope.remote.iqa_spatial import (
    SpatialCellDetail,
    SpatialSceneField,
    derive_spatial_scene,
    hit_test_spatial_cell,
    source_polygons_for_variant,
    spatial_cell_detail,
)
from pixelscope.remote.iqa_v2_domain import ResultV2
from pixelscope.remote.iqa_v2_reader import load_grid_scene
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.image_viewer import ImageViewer
from pixelscope.workers.task_worker import TaskError, TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool


@dataclass(frozen=True)
class IqaReturnSnapshot:
    selected_ids: tuple[str, ...]
    page_anchor_id: str | None
    active_id: str | None
    primary_id: str | None
    layout_mode: str


@dataclass(frozen=True)
class _SpatialRequest:
    result_identity: tuple[str, int]
    scene_id: str
    attribute_id: str
    reference_variant_id: str | None
    aggregation_mode: str


@dataclass(frozen=True)
class _SpatialPayload:
    request: _SpatialRequest
    field: SpatialSceneField | None
    status: LoadStatus
    reason: str | None = None


def _load_spatial_payload(
    result: ResultV2,
    request: _SpatialRequest,
) -> _SpatialPayload:
    outcome = load_grid_scene(result, request.scene_id)
    if not outcome.succeeded or outcome.data is None:
        return _SpatialPayload(
            request=request,
            field=None,
            status=outcome.status,
            reason=outcome.reason or "Scene grid is unavailable",
        )
    try:
        field = derive_spatial_scene(
            result,
            request.scene_id,
            outcome.data,
            request.attribute_id,
            request.reference_variant_id,
        )
    except (KeyError, StopIteration, ValueError) as exc:
        return _SpatialPayload(
            request=request,
            field=None,
            status=LoadStatus.CORRUPT,
            reason=str(exc),
        )
    return _SpatialPayload(request=request, field=field, status=LoadStatus.SUCCESS)


class _SpatialOverlayItem(QGraphicsItem):
    """One vector overlay in native source coordinates; no image buffer is allocated."""

    def __init__(self) -> None:
        super().__init__()
        self.setZValue(15)
        self._cells: tuple[tuple[tuple[QPointF, ...], float], ...] = ()
        self._bounds = QRectF()
        self._scale = (-1.0, 1.0)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return self._bounds

    def clear(self) -> None:
        if not self._cells:
            return
        self.prepareGeometryChange()
        self._cells = ()
        self._bounds = QRectF()
        self.hide()
        self.update()

    def set_field(
        self,
        result: ResultV2,
        field: SpatialSceneField,
        variant_id: str,
    ) -> None:
        values = field.variant(variant_id).values
        cells: list[tuple[tuple[QPointF, ...], float]] = []
        bounds: QRectF | None = None
        for row, column, polygon in source_polygons_for_variant(result, field, variant_id):
            points = tuple(QPointF(x, y) for x, y in polygon)
            value = float(values[row, column])
            cells.append((points, value))
            for point in points:
                point_rect = QRectF(point, point)
                bounds = point_rect if bounds is None else bounds.united(point_rect)
        self.prepareGeometryChange()
        self._cells = tuple(cells)
        self._bounds = bounds or QRectF()
        self._scale = (field.scale_min, field.scale_max)
        self.setVisible(bool(cells))
        self.update()

    def paint(self, painter: QPainter, _option: object, _widget: object = None) -> None:
        if not self._cells:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for points, value in self._cells:
            color = _overlay_color(value, *self._scale)
            pen_color = QColor(color)
            pen_color.setAlpha(190)
            painter.setPen(QPen(pen_color, 0.0))
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF(points))


def _overlay_color(value: float, minimum: float, maximum: float) -> QColor:
    span = maximum - minimum
    normalized = 0.5 if span <= 0.0 else max(0.0, min(1.0, (value - minimum) / span))
    color = QColor.fromHsvF((1.0 - normalized) * 0.66, 0.78, 0.98, 0.34)
    return color


class IqaSceneInspectionController(QObject):
    """Compose explicit IQA Scene Inspect/Return with the canonical MainWindow workflow."""

    def __init__(self, window: Any) -> None:
        super().__init__(window)
        self.window = window
        self.workspace = window.iqa_workspace
        self.result_controller = window.iqa_controller
        self._pool = analysis_thread_pool()
        self._active = True
        self._inspect_generation = 0
        self._spatial_generation = 0
        self._inspect_worker: TaskWorker | None = None
        self._spatial_worker: TaskWorker | None = None
        self._inspect_scene_id: str | None = None
        self._inspected_result: ResultV2 | None = None
        self._inspected_document_variants: dict[str, str] = {}
        self._return_snapshot: IqaReturnSnapshot | None = None
        self._return_valid = False
        self._owned_mutation_depth = 0
        self._field: SpatialSceneField | None = None
        self._spatial_request: _SpatialRequest | None = None
        self._overlay_items: dict[ImageViewer, _SpatialOverlayItem] = {}
        self._original_select_document_ids = window._select_document_ids
        self._original_remove_document_ids = window._remove_document_ids
        self._original_open_result = self.result_controller.open_result
        self._original_shutdown = self.result_controller.shutdown
        self._build_controls()
        self._install_mutation_boundaries()
        self._connect_workspace()
        self._connect_viewers()
        self._sync_controls()

    @property
    def return_valid(self) -> bool:
        return self._return_valid and self._return_snapshot is not None

    @property
    def inspected_scene_id(self) -> str | None:
        return self._inspect_scene_id

    def inspect_selected_scene(self) -> None:
        if not self._active:
            return
        scene_id = self.workspace.selected_scene_id
        result = self.workspace.result
        if scene_id is None:
            self._set_status("Select a Scene first")
            return
        if not isinstance(result, ResultV2):
            self._set_status("Native Inspect requires a schema-v2 result")
            return
        review = getattr(self.window, "review_selection_controller", None)
        if bool(getattr(review, "active", False)):
            self._set_status("Commit or clear temporary Picks before Inspect")
            return
        reason = inspect_unavailable_reason(
            result,
            scene_id,
            self.window.application_settings.remote_iqa,
        )
        if reason is not None:
            self._set_status(reason)
            self._sync_controls()
            return
        self._start_scene_verification(result, scene_id)

    def return_to_local_workspace(self) -> None:
        snapshot = self._return_snapshot
        if not self.return_valid or snapshot is None:
            self._set_status("Return is unavailable because local comparison intent changed")
            return
        if any(document_id not in self.window.documents for document_id in snapshot.selected_ids):
            self._invalidate_return("Return invalidated because a captured source was removed")
            return
        self._cancel_inspect_worker()
        self._cancel_spatial_worker()
        self._clear_spatial_overlay()
        with self._owned_mutation():
            self._original_select_document_ids(list(snapshot.selected_ids), preserve_view=False)
            if snapshot.page_anchor_id in snapshot.selected_ids:
                anchor_index = snapshot.selected_ids.index(snapshot.page_anchor_id)
                self.window._page_start = (anchor_index // 6) * 6
                self.window._current_index = anchor_index
            page_ids = {
                document.document_id for document in self.window.current_comparison_documents()
            }
            self.window._focus_document_id = (
                snapshot.primary_id if snapshot.primary_id in page_ids else None
            )
            self.window.set_layout_mode(snapshot.layout_mode)
            if snapshot.active_id in page_ids:
                self.window._set_active_document(self.window.documents[snapshot.active_id])
        self._inspect_scene_id = None
        self._inspected_result = None
        self._inspected_document_variants.clear()
        self._return_snapshot = None
        self._return_valid = False
        self._field = None
        self._set_status("Returned to the pre-Inspect local comparison")
        self._sync_controls()

    def shutdown(self) -> None:
        if not self._active:
            return
        self._active = False
        self._cancel_inspect_worker()
        self._cancel_spatial_worker()
        self._clear_spatial_overlay()

    def _build_controls(self) -> None:
        scene_layout = self.workspace.scene_page.layout()
        if not isinstance(scene_layout, QVBoxLayout):
            raise RuntimeError("IQA Scene inspection requires the Scene page layout")
        panel = QFrame(self.workspace.scene_page)
        panel.setObjectName("iqaSceneInspectionPanel")
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(
            TOKENS.spacing_sm,
            TOKENS.spacing_sm,
            TOKENS.spacing_sm,
            TOKENS.spacing_sm,
        )
        outer.setSpacing(TOKENS.spacing_xs)

        row = QWidget(panel)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(TOKENS.spacing_sm)
        self.inspect_button = QPushButton("Inspect in Viewer", row)
        self.inspect_button.setObjectName("iqaInspectScene")
        self.return_button = QPushButton("Return", row)
        self.return_button.setObjectName("iqaReturnFromInspect")
        self.attribute_combo = QComboBox(row)
        self.attribute_combo.setObjectName("iqaSpatialAttribute")
        row_layout.addWidget(self.inspect_button)
        row_layout.addWidget(self.return_button)
        row_layout.addWidget(QLabel("Spatial attribute", row))
        row_layout.addWidget(self.attribute_combo, 1)
        outer.addWidget(row)

        self.inspect_status = QLabel("Passive result browsing does not change Selected.", panel)
        self.inspect_status.setObjectName("iqaInspectStatus")
        self.inspect_status.setWordWrap(True)
        outer.addWidget(self.inspect_status)
        self.legend_label = QLabel("Spatial overlay inactive", panel)
        self.legend_label.setObjectName("iqaSpatialLegend")
        self.legend_label.setWordWrap(True)
        self.legend_label.setStyleSheet(f"color: {TOKENS.text_secondary};")
        outer.addWidget(self.legend_label)
        self.block_label = QLabel("Block inspector: hover or click an overlaid source cell.", panel)
        self.block_label.setObjectName("iqaBlockInspector")
        self.block_label.setWordWrap(True)
        self.block_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.block_label)
        scene_layout.addWidget(panel)
        self.panel = panel

        self.inspect_button.clicked.connect(self.inspect_selected_scene)  # type: ignore[attr-defined]
        self.return_button.clicked.connect(self.return_to_local_workspace)  # type: ignore[attr-defined]
        self.attribute_combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._spatial_control_changed
        )

    def _install_mutation_boundaries(self) -> None:
        def select_document_ids(
            document_ids: list[str],
            *args: object,
            **kwargs: object,
        ) -> Any:
            if self._owned_mutation_depth == 0:
                self._invalidate_return("Return invalidated by a newer local Selected change")
            return self._original_select_document_ids(document_ids, *args, **kwargs)

        def remove_document_ids(
            document_ids: list[str],
            *args: object,
            **kwargs: object,
        ) -> Any:
            if self._owned_mutation_depth == 0 and self._return_snapshot is not None:
                captured = set(self._return_snapshot.selected_ids)
                if captured.intersection(str(item) for item in document_ids):
                    self._invalidate_return("Return invalidated because a captured source was removed")
                elif self._inspect_scene_id is not None:
                    self._invalidate_return("Return invalidated by a newer local Files change")
            return self._original_remove_document_ids(document_ids, *args, **kwargs)

        def open_result(root: object) -> int:
            self._new_result_opening()
            return self._original_open_result(root)

        def shutdown() -> None:
            self.shutdown()
            self._original_shutdown()

        self.window._select_document_ids = select_document_ids
        self.window._remove_document_ids = remove_document_ids
        self.result_controller.open_result = open_result
        self.result_controller.shutdown = shutdown
        self.window.document_list.selection_changing.connect(self._files_selection_changing)
        self.window.document_list.itemSelectionChanged.connect(self._files_selection_changed)
        self.window.document_list.remove_changing.connect(self._files_remove_changing)

    def _connect_workspace(self) -> None:
        self.workspace.scene_requested.connect(self._scene_requested)
        self.workspace.reference_combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._spatial_control_changed
        )
        self.workspace.mode_combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._spatial_control_changed
        )
        self.workspace.hierarchy.currentItemChanged.connect(  # type: ignore[attr-defined]
            lambda _current, _previous: self._sync_attribute_from_workspace()
        )
        self.result_controller.outcome_ready.connect(self._result_outcome)

    def _connect_viewers(self) -> None:
        for viewer in self._all_viewers():
            item = _SpatialOverlayItem()
            item.hide()
            viewer.view_box.addItem(item)
            self._overlay_items[viewer] = item
            viewer.document_changed.connect(
                lambda _document, current=viewer: self._sync_viewer_overlay(current)
            )
            scene = viewer.view_box.scene()
            if scene is not None:
                scene.sigMouseMoved.connect(
                    lambda position, current=viewer: self._viewer_hovered(current, position)
                )
                scene.sigMouseClicked.connect(
                    lambda event, current=viewer: self._viewer_clicked(current, event)
                )

    @Slot(str)
    def _scene_requested(self, scene_id: str) -> None:
        self._sync_controls()
        if self._inspect_scene_id is None:
            return
        result = self.workspace.result
        if not isinstance(result, ResultV2):
            return
        self._start_scene_verification(result, scene_id)

    @Slot(object)
    def _result_outcome(self, _outcome: object) -> None:
        self._populate_attribute_combo()
        self._sync_controls()

    @Slot()
    def _spatial_control_changed(self) -> None:
        self._sync_controls()
        if self._inspect_scene_id is not None and self._inspected_result is not None:
            self._request_spatial_overlay()

    def _sync_attribute_from_workspace(self) -> None:
        attribute_id = self.workspace.selected_attribute_id
        if attribute_id is None:
            return
        index = self.attribute_combo.findData(attribute_id)
        if index >= 0 and index != self.attribute_combo.currentIndex():
            self.attribute_combo.setCurrentIndex(index)

    def _populate_attribute_combo(self) -> None:
        result = self.workspace.result
        previous = self.attribute_combo.currentData()
        self.attribute_combo.blockSignals(True)
        self.attribute_combo.clear()
        if isinstance(result, ResultV2):
            for attribute in result.attributes:
                self.attribute_combo.addItem(attribute.name, attribute.attribute_id)
            preferred = self.workspace.selected_attribute_id or previous
            index = self.attribute_combo.findData(preferred)
            self.attribute_combo.setCurrentIndex(max(0, index))
        self.attribute_combo.blockSignals(False)

    def _start_scene_verification(self, result: ResultV2, scene_id: str) -> None:
        self._cancel_inspect_worker()
        self._inspect_generation += 1
        generation = self._inspect_generation
        self._set_status(f"Verifying published sources for {scene_id}…")
        worker = TaskWorker(
            verify_scene_sources,
            result,
            scene_id,
            self.window.application_settings.remote_iqa,
            generation=generation,
        )
        worker.signals.succeeded.connect(self._verification_succeeded)
        worker.signals.failed.connect(self._verification_failed)
        worker.signals.finished.connect(self._verification_finished)
        self._inspect_worker = worker
        self._pool.start(worker)
        self._sync_controls()

    @Slot(str, object, int, object)
    def _verification_succeeded(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if not self._active or generation != self._inspect_generation:
            return
        if not isinstance(value, SceneVerificationOutcome):
            self._set_status("Source verification returned no Scene outcome")
            return
        if not value.succeeded:
            suffix = f" · {value.failed_source_id}" if value.failed_source_id else ""
            self._set_status(f"{value.reason or 'Inspect unavailable'}{suffix}")
            self._sync_controls()
            return
        result = self.workspace.result
        if not isinstance(result, ResultV2) or result.result_id != self.workspace.result.result_id:
            return
        if self.workspace.selected_scene_id != value.scene_id:
            return
        review = getattr(self.window, "review_selection_controller", None)
        if bool(getattr(review, "active", False)):
            self._set_status("Commit or clear temporary Picks before Inspect")
            return
        self._apply_verified_scene(result, value)

    @Slot(str, object, int, object)
    def _verification_failed(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        error: object,
    ) -> None:
        if not self._active or generation != self._inspect_generation:
            return
        message = error.message if isinstance(error, TaskError) else str(error)
        self._set_status(f"Source verification failed · {message}")

    @Slot(str)
    def _verification_finished(self, task_id: str) -> None:
        if self._inspect_worker is not None and self._inspect_worker.task_id == task_id:
            self._inspect_worker = None
        self._sync_controls()

    def _apply_verified_scene(
        self,
        result: ResultV2,
        outcome: SceneVerificationOutcome,
    ) -> None:
        if self._return_snapshot is None:
            self._return_snapshot = self._capture_return_snapshot()
            self._return_valid = True
        inputs = tuple(ImageInput(item.local_path) for item in outcome.sources)
        with self._owned_mutation():
            document_ids = self.window._register_inputs(inputs, resolve_raw_profiles=False)
            if len(document_ids) != len(outcome.sources):
                self._set_status("Scene registration failed; Selected was not changed")
                return
            self.window._select_document_ids(document_ids)
        self._inspect_scene_id = outcome.scene_id
        self._inspected_result = result
        self._inspected_document_variants = {
            document_id: source.variant_id
            for document_id, source in zip(document_ids, outcome.sources, strict=True)
        }
        self._clear_spatial_overlay()
        self._set_status(f"Inspecting {outcome.scene_id} in the native PixelScope viewer")
        self._request_spatial_overlay()
        self._sync_controls()

    def _capture_return_snapshot(self) -> IqaReturnSnapshot:
        selected_ids = tuple(document.document_id for document in self.window.selected_documents)
        page = self.window.current_comparison_documents()
        page_anchor_id = page[0].document_id if page else None
        selected_set = set(selected_ids)
        active_id = self.window._active_document_id
        if active_id not in selected_set:
            active_id = None
        page_ids = {document.document_id for document in page}
        primary_id = self.window._focus_document_id
        if primary_id not in page_ids:
            primary_id = None
        return IqaReturnSnapshot(
            selected_ids=selected_ids,
            page_anchor_id=page_anchor_id,
            active_id=active_id,
            primary_id=primary_id,
            layout_mode=self.window._layout_mode,
        )

    def _request_spatial_overlay(self) -> None:
        result = self._inspected_result
        scene_id = self._inspect_scene_id
        attribute_id = self.attribute_combo.currentData()
        if result is None or scene_id is None or not isinstance(attribute_id, str):
            return
        reference = self.workspace.reference_variant_id
        reference_variant_id = (
            None if reference == ABSOLUTE_REFERENCE_ID else reference
        )
        request = _SpatialRequest(
            result_identity=(result.result_id, id(result)),
            scene_id=scene_id,
            attribute_id=attribute_id,
            reference_variant_id=reference_variant_id,
            aggregation_mode=self.workspace.aggregation_mode.value,
        )
        self._cancel_spatial_worker()
        self._spatial_generation += 1
        generation = self._spatial_generation
        self._spatial_request = request
        worker = TaskWorker(
            _load_spatial_payload,
            result,
            request,
            generation=generation,
        )
        worker.signals.succeeded.connect(self._spatial_succeeded)
        worker.signals.failed.connect(self._spatial_failed)
        worker.signals.finished.connect(self._spatial_finished)
        self._spatial_worker = worker
        self._pool.start(worker)
        self.legend_label.setText("Loading current Scene grid…")

    @Slot(str, object, int, object)
    def _spatial_succeeded(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if not self._active or generation != self._spatial_generation:
            return
        if not isinstance(value, _SpatialPayload) or value.request != self._spatial_request:
            return
        if value.status is not LoadStatus.SUCCESS or value.field is None:
            self.legend_label.setText(
                f"Spatial overlay unavailable · {value.reason or value.status.value}"
            )
            return
        result = self._inspected_result
        if result is None or value.request.result_identity != (result.result_id, id(result)):
            return
        if value.request.scene_id != self._inspect_scene_id:
            return
        self._field = value.field
        self._sync_all_overlays()
        self._sync_legend()

    @Slot(str, object, int, object)
    def _spatial_failed(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        error: object,
    ) -> None:
        if not self._active or generation != self._spatial_generation:
            return
        message = error.message if isinstance(error, TaskError) else str(error)
        self.legend_label.setText(f"Spatial overlay unavailable · {message}")

    @Slot(str)
    def _spatial_finished(self, task_id: str) -> None:
        if self._spatial_worker is not None and self._spatial_worker.task_id == task_id:
            self._spatial_worker = None

    def _sync_legend(self) -> None:
        field = self._field
        result = self._inspected_result
        if field is None or result is None:
            self.legend_label.setText("Spatial overlay inactive")
            return
        spec = result.attribute(field.attribute_id)
        if field.reference_variant_id is None:
            mode = "Absolute"
            reference_text = ""
        else:
            mode = "Relative"
            reference_text = f" · Reference {result.variant(field.reference_variant_id).label}"
        self.legend_label.setText(
            f"{spec.name} · {field.unit} · {mode}{reference_text} · "
            f"scale [{field.scale_min:.5g}, {field.scale_max:.5g}] · "
            f"per-cell raw field; Scene scalar '{self.workspace.mode_combo.currentText()}' is a reduction"
        )

    def _sync_all_overlays(self) -> None:
        for viewer in self._all_viewers():
            self._sync_viewer_overlay(viewer)

    def _sync_viewer_overlay(self, viewer: ImageViewer) -> None:
        item = self._overlay_items[viewer]
        document = viewer.document
        field = self._field
        result = self._inspected_result
        if document is None or field is None or result is None:
            item.clear()
            return
        variant_id = self._inspected_document_variants.get(document.document_id)
        if variant_id is None:
            item.clear()
            return
        try:
            field.variant(variant_id)
        except StopIteration:
            item.clear()
            return
        item.set_field(result, field, variant_id)

    def _viewer_hovered(self, viewer: ImageViewer, scene_position: QPointF) -> None:
        self._inspect_viewer_position(viewer, scene_position)

    def _viewer_clicked(self, viewer: ImageViewer, event: object) -> None:
        button_method = getattr(event, "button", None)
        if callable(button_method) and button_method() != Qt.MouseButton.LeftButton:
            return
        position_method = getattr(event, "scenePos", None)
        if callable(position_method):
            self._inspect_viewer_position(viewer, position_method())

    def _inspect_viewer_position(self, viewer: ImageViewer, scene_position: QPointF) -> None:
        field = self._field
        result = self._inspected_result
        document = viewer.document
        if field is None or result is None or document is None:
            return
        variant_id = self._inspected_document_variants.get(document.document_id)
        if variant_id is None or not viewer.view_box.sceneBoundingRect().contains(scene_position):
            return
        source_point = viewer.view_box.mapSceneToView(scene_position)
        cell = hit_test_spatial_cell(
            field,
            variant_id,
            float(source_point.x()),
            float(source_point.y()),
        )
        if cell is None:
            return
        detail = spatial_cell_detail(result, field, variant_id, *cell)
        self._show_block_detail(detail)

    def _show_block_detail(self, detail: SpatialCellDetail) -> None:
        mean = "—" if detail.cell_mean is None else f"{detail.cell_mean:.7g}"
        valid = "valid" if detail.valid else "invalid"
        lines = [
            f"Scene {detail.scene_id} · {detail.attribute_id} · {detail.variant_id} / {detail.source_id}",
            f"cell [{detail.row}, {detail.column}] · {valid}",
            f"W={detail.weight_sum:.7g} · S1={detail.weighted_sum:.7g} · "
            f"S2={detail.weighted_square_sum:.7g} · valid_count={detail.valid_count} · mean={mean}",
        ]
        if detail.reference_variant_id is not None:
            relative = "—" if detail.relative_value is None else f"{detail.relative_value:.7g}"
            reference_mean = (
                "—" if detail.reference_cell_mean is None else f"{detail.reference_cell_mean:.7g}"
            )
            lines.append(
                f"Reference {detail.reference_variant_id} / {detail.reference_source_id} · "
                f"pair_valid={detail.pair_valid} · target={mean} · reference={reference_mean} · "
                f"raw relative={relative}"
            )
        x, y, width, height = detail.analysis_bounds
        lines.append(
            f"analysis bounds x={x:.4g}, y={y:.4g}, w={width:.4g}, h={height:.4g} · "
            f"source polygon={detail.source_polygon}"
        )
        self.block_label.setText("\n".join(lines))

    def _new_result_opening(self) -> None:
        self._cancel_inspect_worker()
        self._cancel_spatial_worker()
        self._clear_spatial_overlay()
        self._inspect_scene_id = None
        self._inspected_result = None
        self._inspected_document_variants.clear()
        self._field = None
        self._spatial_request = None
        self._set_status("Opening another IQA result · native Inspect is passive until requested")
        self._sync_controls()

    def _files_selection_changing(self) -> None:
        if self._owned_mutation_depth == 0 and self._inspect_scene_id is not None:
            self._invalidate_return("Return invalidated by a newer local Selected change")

    def _files_selection_changed(self) -> None:
        if self._owned_mutation_depth != 0 or self._inspect_scene_id is None:
            return
        current = tuple(document.document_id for document in self.window.selected_documents)
        expected = tuple(self._inspected_document_variants)
        if current != expected:
            self._invalidate_return("Return invalidated by a newer local Selected change")

    def _files_remove_changing(self, document_ids: object) -> None:
        if self._owned_mutation_depth != 0 or not isinstance(document_ids, list):
            return
        snapshot = self._return_snapshot
        if snapshot is None:
            return
        captured = set(snapshot.selected_ids)
        if captured.intersection(str(item) for item in document_ids):
            self._invalidate_return("Return invalidated because a captured source was removed")

    def _invalidate_return(self, reason: str) -> None:
        if self._return_snapshot is None:
            return
        self._return_valid = False
        self._return_snapshot = None
        self._cancel_inspect_worker()
        self._cancel_spatial_worker()
        self._clear_spatial_overlay()
        self._inspect_scene_id = None
        self._inspected_result = None
        self._inspected_document_variants.clear()
        self._field = None
        self._set_status(reason)
        self._sync_controls()

    @contextmanager
    def _owned_mutation(self) -> Iterator[None]:
        self._owned_mutation_depth += 1
        try:
            yield
        finally:
            self._owned_mutation_depth -= 1

    def _cancel_inspect_worker(self) -> None:
        self._inspect_generation += 1
        if self._inspect_worker is not None:
            self._inspect_worker.cancel()
        self._inspect_worker = None

    def _cancel_spatial_worker(self) -> None:
        self._spatial_generation += 1
        if self._spatial_worker is not None:
            self._spatial_worker.cancel()
        self._spatial_worker = None

    def _clear_spatial_overlay(self) -> None:
        for item in self._overlay_items.values():
            item.clear()
        self.block_label.setText("Block inspector: hover or click an overlaid source cell.")
        self.legend_label.setText("Spatial overlay inactive")

    def _sync_controls(self) -> None:
        result = self.workspace.result
        scene_id = self.workspace.selected_scene_id
        review = getattr(self.window, "review_selection_controller", None)
        picks_active = bool(getattr(review, "active", False))
        reason: str | None = None
        if isinstance(result, ResultV2) and scene_id is not None:
            reason = inspect_unavailable_reason(
                result,
                scene_id,
                self.window.application_settings.remote_iqa,
            )
        elif result is not None and scene_id is not None:
            reason = "Native Inspect requires a schema-v2 result"
        enabled = (
            self._active
            and self._inspect_worker is None
            and isinstance(result, ResultV2)
            and scene_id is not None
            and reason is None
            and not picks_active
        )
        self.inspect_button.setEnabled(enabled)
        self.return_button.setEnabled(self.return_valid)
        self.attribute_combo.setEnabled(isinstance(result, ResultV2))
        if picks_active:
            self.inspect_button.setToolTip("Commit or clear temporary Picks before Inspect")
        elif reason is not None:
            self.inspect_button.setToolTip(reason)
        else:
            self.inspect_button.setToolTip(
                "Verify all published Scene sources, then show them through Current Comparison Page"
            )

    def _set_status(self, text: str) -> None:
        self.inspect_status.setText(text)

    def _all_viewers(self) -> tuple[ImageViewer, ...]:
        return (self.window.viewer, *tuple(self.window.multi_compare_view.viewers))


def install_iqa_scene_inspection(window: Any) -> IqaSceneInspectionController:
    """Install P5-D viewer-linked Scene inspection once per production MainWindow."""

    existing = getattr(window, "iqa_scene_inspection_controller", None)
    if isinstance(existing, IqaSceneInspectionController):
        return existing
    controller = IqaSceneInspectionController(window)
    window.iqa_scene_inspection_controller = controller
    return controller
