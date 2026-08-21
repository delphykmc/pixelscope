"""Non-modal local exploration UI for published Remote IQA results."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QObject, QPointF, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor, QCursor, QFont, QIcon, QPen, QPixmap, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDockWidget,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pixelscope.remote.iqa_domain import (
    ComparisonMode,
    LoadStatus,
    ScalarStatistic,
    ValueKind,
)
from pixelscope.remote.iqa_explorer import ABSOLUTE_REFERENCE_ID, IqaExplorerModel
from pixelscope.remote.iqa_result_reader import load_result
from pixelscope.remote.iqa_v2_domain import VersionedResultLoadOutcome
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar
from pixelscope.workers.task_worker import TaskError, TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool

MODE_LABELS = {
    ComparisonMode.RATIO_OF_WEIGHTED_MEANS: "Ratio of weighted means",
    ComparisonMode.MEAN_OF_GRID_LOG_RATIOS: "Mean of grid log ratios",
}
IQA_FLOATING_GEOMETRY_SETTING = "ui/iqa_floating_geometry"
_VARIANT_SYMBOLS = ("o", "s", "t", "d", "+", "x", "star", "p", "h")


@dataclass(frozen=True)
class _WorkspaceLoadPayload:
    outcome: VersionedResultLoadOutcome
    model: IqaExplorerModel | None = None


class IqaWorkspaceWidget(QWidget):
    """Summary-first N-way IQA explorer with lazy relative-grid preparation."""

    scene_requested = Signal(str)
    relative_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("iqaWorkspace")
        self._model: IqaExplorerModel | None = None
        self._dock_title: PlotsDockTitleBar | None = None
        self._selected_attribute_id: str | None = None
        self._selected_scene_id: str | None = None
        self._relative_loading = False
        self._selected_scene_line: pg.InfiniteLine | None = None
        self._hover_scene_line: pg.InfiniteLine | None = None
        self._overview_hover_texts: tuple[str, ...] = ()
        self._scene_hover_texts: tuple[str, ...] = ()
        self._last_overview_hover_index: int | None = None
        self._last_scene_hover_index: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            TOKENS.spacing_sm,
            TOKENS.spacing_sm,
            TOKENS.spacing_sm,
            0,
        )
        layout.setSpacing(TOKENS.spacing_sm)

        self.status_label = QLabel("Open a complete PixelScope IQA result.", self)
        self.status_label.setObjectName("iqaStatus")
        self.result_label = QLabel("No result", self)
        self.result_label.setObjectName("iqaResultOverview")
        self.dataset_label = QLabel("", self)
        self.dataset_label.setObjectName("iqaDatasetOverview")
        layout.addWidget(self.status_label)
        layout.addWidget(self.result_label)
        layout.addWidget(self.dataset_label)

        controls = QWidget(self)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(TOKENS.spacing_sm)
        controls_layout.addWidget(QLabel("Reference", controls))
        self.reference_combo = QComboBox(controls)
        self.reference_combo.setObjectName("iqaReference")
        self.reference_combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._display_mode_changed
        )
        controls_layout.addWidget(self.reference_combo, 1)
        controls_layout.addWidget(QLabel("Comparison", controls))
        self.mode_combo = QComboBox(controls)
        self.mode_combo.setObjectName("iqaAggregationMode")
        for mode, label in MODE_LABELS.items():
            self.mode_combo.addItem(label, mode.value)
        self.mode_combo.currentIndexChanged.connect(  # type: ignore[attr-defined]
            self._display_mode_changed
        )
        controls_layout.addWidget(self.mode_combo, 1)
        layout.addWidget(controls)

        self.pages = QTabWidget(self)
        self.pages.setObjectName("iqaWorkspacePages")
        self.overview_page = QWidget(self.pages)
        self.scene_page = QWidget(self.pages)
        self.pages.addTab(self.overview_page, "Overview")
        self.pages.addTab(self.scene_page, "Scene Trend")
        layout.addWidget(self.pages, 1)

        self._build_overview_page()
        self._build_scene_page()
        self._set_controls_enabled(False)

    def _build_overview_page(self) -> None:
        layout = QVBoxLayout(self.overview_page)
        layout.setContentsMargins(0, TOKENS.spacing_sm, 0, 0)
        layout.setSpacing(0)
        self.overview_splitter = QSplitter(
            Qt.Orientation.Vertical,
            self.overview_page,
        )
        self.overview_splitter.setObjectName("iqaOverviewSplitter")

        self.overview_chart_panel = QWidget(self.overview_splitter)
        self.overview_chart_panel.setObjectName("iqaAttributeOverviewChartPanel")
        self.overview_chart_layout = QVBoxLayout(self.overview_chart_panel)
        self.overview_chart_layout.setContentsMargins(0, 0, 0, TOKENS.spacing_xs)
        self.overview_chart_layout.setSpacing(0)

        self.overview_plot = pg.PlotWidget(self.overview_chart_panel)
        self.overview_plot.setObjectName("iqaAttributeOverviewPlot")
        self.overview_plot.setMinimumHeight(130)
        self.overview_plot.setBackground(TOKENS.workspace_background)
        self.overview_plot.showGrid(x=False, y=True, alpha=0.2)
        self.overview_plot.scene().sigMouseMoved.connect(self._overview_plot_hovered)
        self.overview_chart_layout.addWidget(self.overview_plot, 1)

        self.overview_legend = pg.LegendItem(
            offset=None,
            frame=False,
            labelTextColor=TOKENS.text_secondary,
            colCount=4,
        )
        self.overview_legend.setParentItem(self.overview_plot.plotItem)
        self.overview_plot.plotItem.layout.addItem(self.overview_legend, 4, 1)
        self.overview_plot.plotItem.layout.setRowSpacing(4, TOKENS.spacing_xs)

        self.overview_detail_panel = QWidget(self.overview_splitter)
        self.overview_detail_panel.setObjectName("iqaAttributeDetailPanel")
        detail_layout = QVBoxLayout(self.overview_detail_panel)
        detail_layout.setContentsMargins(0, TOKENS.spacing_sm, 0, 0)
        detail_layout.setSpacing(TOKENS.spacing_xs)
        self.overview_detail_heading = QLabel(
            "Absolute Value Details",
            self.overview_detail_panel,
        )
        self.overview_detail_heading.setObjectName("iqaAttributeDetailHeading")
        heading_font = self.overview_detail_heading.font()
        heading_font.setBold(True)
        self.overview_detail_heading.setFont(heading_font)
        self.overview_detail_heading.setStyleSheet(
            f"color: {TOKENS.text_secondary};"
        )
        detail_layout.addWidget(self.overview_detail_heading)

        self.hierarchy = QTreeWidget(self.overview_detail_panel)
        self.hierarchy.setObjectName("iqaAttributeSceneHierarchy")
        self.hierarchy.setAlternatingRowColors(True)
        self.hierarchy.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.hierarchy.setUniformRowHeights(True)
        self.hierarchy.currentItemChanged.connect(  # type: ignore[attr-defined]
            self._hierarchy_selection_changed
        )
        detail_layout.addWidget(self.hierarchy, 1)

        self.overview_splitter.addWidget(self.overview_chart_panel)
        self.overview_splitter.addWidget(self.overview_detail_panel)
        self.overview_splitter.setStretchFactor(0, 2)
        self.overview_splitter.setStretchFactor(1, 3)
        self.overview_splitter.setSizes([280, 420])
        layout.addWidget(self.overview_splitter, 1)
        self.overview_table = self.hierarchy

    def _build_scene_page(self) -> None:
        layout = QVBoxLayout(self.scene_page)
        layout.setContentsMargins(0, TOKENS.spacing_sm, 0, 0)
        layout.setSpacing(0)
        self.scene_splitter = QSplitter(Qt.Orientation.Vertical, self.scene_page)
        self.scene_splitter.setObjectName("iqaSceneSplitter")

        trend_panel = QWidget(self.scene_splitter)
        trend_layout = QVBoxLayout(trend_panel)
        trend_layout.setContentsMargins(0, 0, 0, TOKENS.spacing_sm)
        trend_layout.setSpacing(TOKENS.spacing_sm)
        self.trend_label = QLabel("All attributes across Scenes", trend_panel)
        self.trend_label.setObjectName("iqaTrendLabel")
        self.series_hint = QLabel(
            "Attribute = color · variant = marker",
            trend_panel,
        )
        self.series_hint.setStyleSheet(f"color: {TOKENS.text_secondary};")
        trend_layout.addWidget(self.trend_label)
        trend_layout.addWidget(self.series_hint)

        trend_splitter = QSplitter(Qt.Orientation.Horizontal, trend_panel)
        trend_splitter.setObjectName("iqaTrendHorizontalSplitter")
        attribute_panel = QWidget(trend_splitter)
        attribute_layout = QVBoxLayout(attribute_panel)
        attribute_layout.setContentsMargins(0, 0, TOKENS.spacing_sm, 0)
        attribute_layout.setSpacing(TOKENS.spacing_xs)
        attribute_layout.addWidget(QLabel("Attributes", attribute_panel))
        self.attribute_filter = QListWidget(attribute_panel)
        self.attribute_filter.setObjectName("iqaAttributeFilter")
        self.attribute_filter.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.attribute_filter.setMinimumWidth(150)
        self.attribute_filter.setMaximumWidth(230)
        self.attribute_filter.setStyleSheet(
            "QListWidget { border: 1px solid palette(mid); border-radius: 4px; }"
            "QListWidget::item { padding: 4px 6px; margin: 1px 0; "
            "border-radius: 3px; }"
            "QListWidget::item:hover { background: palette(alternate-base); }"
        )
        self.attribute_filter.itemChanged.connect(  # type: ignore[attr-defined]
            self._attribute_filter_changed
        )
        attribute_layout.addWidget(self.attribute_filter, 1)

        self.scene_trend_plot = pg.PlotWidget(trend_splitter)
        self.scene_trend_plot.setObjectName("iqaSceneTrendPlot")
        self.scene_trend_plot.setMinimumHeight(170)
        self.scene_trend_plot.setBackground(TOKENS.workspace_background)
        self.scene_trend_plot.showGrid(x=True, y=True, alpha=0.2)
        self.scene_trend_plot.scene().sigMouseClicked.connect(
            self._scene_plot_clicked
        )
        self.scene_trend_plot.scene().sigMouseMoved.connect(
            self._scene_plot_hovered
        )
        trend_splitter.addWidget(attribute_panel)
        trend_splitter.addWidget(self.scene_trend_plot)
        trend_splitter.setStretchFactor(0, 0)
        trend_splitter.setStretchFactor(1, 1)
        trend_splitter.setSizes([180, 720])
        trend_layout.addWidget(trend_splitter, 1)

        preview_panel = QWidget(self.scene_splitter)
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, TOKENS.spacing_sm, 0, 0)
        preview_layout.setSpacing(TOKENS.spacing_sm)
        self.preview_caption = QLabel(
            "Click a Scene in the trend plot to inspect its published source "
            "identities.",
            preview_panel,
        )
        self.preview_caption.setObjectName("iqaScenePreviewCaption")
        preview_layout.addWidget(self.preview_caption)
        self.preview_scroll = QScrollArea(preview_panel)
        self.preview_scroll.setObjectName("iqaScenePreview")
        self.preview_scroll.setWidgetResizable(True)
        self.preview_container = QWidget(self.preview_scroll)
        self.preview_layout = QGridLayout(self.preview_container)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.setSpacing(TOKENS.spacing_sm)
        self.preview_scroll.setWidget(self.preview_container)
        preview_layout.addWidget(self.preview_scroll, 1)

        self.scene_splitter.addWidget(trend_panel)
        self.scene_splitter.addWidget(preview_panel)
        self.scene_splitter.setStretchFactor(0, 3)
        self.scene_splitter.setStretchFactor(1, 2)
        self.scene_splitter.setSizes([430, 300])
        layout.addWidget(self.scene_splitter, 1)

    @property
    def model(self) -> IqaExplorerModel | None:
        return self._model

    @property
    def result(self) -> object | None:
        return self._model.result if self._model is not None else None

    @property
    def aggregation_mode(self) -> ComparisonMode:
        data = self.mode_combo.currentData()
        try:
            return ComparisonMode(str(data))
        except ValueError:
            return ComparisonMode.RATIO_OF_WEIGHTED_MEANS

    @property
    def reference_variant_id(self) -> str:
        value = self.reference_combo.currentData()
        return str(value) if value is not None else ABSOLUTE_REFERENCE_ID

    @property
    def selected_attribute_id(self) -> str | None:
        return self._selected_attribute_id

    @property
    def selected_scene_id(self) -> str | None:
        return self._selected_scene_id

    @property
    def enabled_attribute_ids(self) -> tuple[str, ...]:
        enabled: list[str] = []
        for row in range(self.attribute_filter.count()):
            item = self.attribute_filter.item(row)
            attribute_id = item.data(Qt.ItemDataRole.UserRole)
            if (
                isinstance(attribute_id, str)
                and item.checkState() == Qt.CheckState.Checked
            ):
                enabled.append(attribute_id)
        return tuple(enabled)

    def showEvent(self, event: QShowEvent) -> None:
        self._install_dock_title()
        super().showEvent(event)

    def show_loading(self, root: Path) -> None:
        self.status_label.setText(f"Opening {root.name}...")

    def show_relative_loading(self, reference_variant_id: str) -> None:
        if self._model is None:
            return
        label = next(
            item.label
            for item in self._model.variants
            if item.variant_id == reference_variant_id
        )
        self.status_label.setText(
            f"Loading Scene grids for Reference {label}..."
        )
        self._relative_loading = True
        self.reference_combo.setEnabled(False)
        self.mode_combo.setEnabled(False)

    def show_open_error(self, status: LoadStatus, reason: str) -> None:
        self.status_label.setText(f"{status.value.upper()}: {reason}")
        self._relative_loading = False
        self._set_controls_enabled(self._model is not None)

    def set_model(
        self,
        model: IqaExplorerModel,
        *,
        preserve_reference: bool = False,
    ) -> VersionedResultLoadOutcome:
        previous_model = self._model
        previous_attribute = self._selected_attribute_id
        previous_scene = self._selected_scene_id
        previous_reference = (
            self.reference_variant_id if preserve_reference else None
        )
        self._model = model
        attribute_ids = {item.attribute_id for item in model.result.attributes}
        if previous_attribute not in attribute_ids:
            self._selected_attribute_id = model.result.attributes[0].attribute_id
        scene_ids = {scene.scene_id for scene in model.result.scenes}
        if previous_scene not in scene_ids:
            self._selected_scene_id = None
        self._relative_loading = False
        try:
            self._populate_reference_combo(previous_reference)
            self._refresh_model_views()
        except Exception as exc:  # noqa: BLE001 - presentation boundary
            self._model = previous_model
            self._selected_attribute_id = previous_attribute
            self._selected_scene_id = previous_scene
            if previous_model is not None:
                try:
                    self._populate_reference_combo(previous_reference)
                    self._refresh_model_views()
                except Exception:  # noqa: BLE001 - best-effort rollback
                    pass
            else:
                self._clear_model_views()
            return VersionedResultLoadOutcome(
                LoadStatus.CORRUPT,
                reason=f"unable to present IQA result: {exc}",
            )

        result = model.result
        source_count = sum(len(scene.sources) for scene in result.scenes)
        mode = (
            "schema v2"
            if model.is_v2
            else "schema v1 · read-only compatibility"
        )
        self.result_label.setText(f"Job/result {result.result_id} · {mode}")
        self.dataset_label.setText(
            f"{len(result.scenes)} Scenes · {source_count} Scene sources · "
            f"{len(result.attributes)} attributes · {len(model.variants)} variants"
        )
        self.status_label.setText(f"Opened {result.root.name}")
        self._set_controls_enabled(True)
        return VersionedResultLoadOutcome(LoadStatus.SUCCESS, result=result)

    def set_relative_model(
        self,
        model: IqaExplorerModel,
    ) -> VersionedResultLoadOutcome:
        return self.set_model(model, preserve_reference=True)

    def _populate_reference_combo(self, preferred: str | None) -> None:
        if self._model is None:
            return
        self.reference_combo.blockSignals(True)
        self.reference_combo.clear()
        if self._model.is_v2:
            self.reference_combo.addItem(
                "Absolute measurements",
                ABSOLUTE_REFERENCE_ID,
            )
            for variant in self._model.variants:
                self.reference_combo.addItem(
                    variant.label,
                    variant.variant_id,
                )
            target = preferred or ABSOLUTE_REFERENCE_ID
        else:
            for variant in self._model.variants:
                self.reference_combo.addItem(
                    variant.label,
                    variant.variant_id,
                )
            target = preferred if preferred in {"A", "B"} else "A"
        index = self.reference_combo.findData(target)
        self.reference_combo.setCurrentIndex(max(0, index))
        self.reference_combo.blockSignals(False)

    def _refresh_model_views(self) -> None:
        self._populate_attribute_filter()
        self._populate_hierarchy()
        self._populate_overview_plot()
        self._populate_scene_trend()
        self._populate_scene_preview()

    def _clear_model_views(self) -> None:
        self.reference_combo.clear()
        self.attribute_filter.clear()
        self.hierarchy.clear()
        self.overview_plot.clear()
        self.overview_legend.clear()
        self.scene_trend_plot.clear()
        _clear_layout(self.preview_layout)
        self._set_controls_enabled(False)

    def _set_controls_enabled(self, enabled: bool) -> None:
        active = enabled and not self._relative_loading
        self.reference_combo.setEnabled(active)
        self.mode_combo.setEnabled(active)
        self.hierarchy.setEnabled(enabled)
        self.attribute_filter.setEnabled(enabled)
        self.pages.setEnabled(enabled)

    def _populate_attribute_filter(self) -> None:
        if self._model is None:
            return
        previous = {
            self.attribute_filter.item(row).data(Qt.ItemDataRole.UserRole):
            self.attribute_filter.item(row).checkState()
            for row in range(self.attribute_filter.count())
        }
        self.attribute_filter.blockSignals(True)
        self.attribute_filter.clear()
        total = len(self._model.result.attributes)
        for index, attribute in enumerate(self._model.result.attributes):
            item = QListWidgetItem(attribute.name, self.attribute_filter)
            item.setData(Qt.ItemDataRole.UserRole, attribute.attribute_id)
            item.setCheckState(
                previous.get(attribute.attribute_id, Qt.CheckState.Checked)
            )
            item.setIcon(_color_chip_icon(_attribute_color(index, total)))
            item.setToolTip(
                f"Check to show/hide · {attribute.name} · {attribute.unit}"
            )
        self.attribute_filter.blockSignals(False)

    def _display_columns(self) -> tuple[tuple[str, str], ...]:
        assert self._model is not None
        return tuple(
            (item.variant_id, item.label) for item in self._model.variants
        )

    def _trend_columns(self) -> tuple[tuple[str, str], ...]:
        assert self._model is not None
        reference = self.reference_variant_id
        if reference == ABSOLUTE_REFERENCE_ID:
            return self._display_columns()
        reference_label = next(
            item.label
            for item in self._model.variants
            if item.variant_id == reference
        )
        return tuple(
            (item.variant_id, f"{item.label} vs {reference_label}")
            for item in self._model.variants
            if item.variant_id != reference
        )

    def _reference_label(self) -> str | None:
        if self._model is None or self.reference_variant_id == ABSOLUTE_REFERENCE_ID:
            return None
        return next(
            item.label
            for item in self._model.variants
            if item.variant_id == self.reference_variant_id
        )

    def _stat_for(
        self,
        attribute_id: str,
        scene_id: str | None,
        target_variant_id: str,
    ) -> ScalarStatistic:
        assert self._model is not None
        reference = self.reference_variant_id
        if reference == ABSOLUTE_REFERENCE_ID:
            if scene_id is None:
                return self._model.absolute_dataset_stat(
                    target_variant_id,
                    attribute_id,
                )
            return self._model.absolute_scene_stat(
                scene_id,
                target_variant_id,
                attribute_id,
            )
        if target_variant_id == reference:
            return ScalarStatistic(0.0, True)
        if scene_id is None:
            return self._model.relative_dataset_stat(
                attribute_id,
                self.aggregation_mode,
                reference,
                target_variant_id,
            )
        return next(
            point.raw
            for point in self._model.relative_trend(
                attribute_id,
                self.aggregation_mode,
                reference,
                target_variant_id,
            )
            if point.scene_id == scene_id
        )

    def _populate_hierarchy(self) -> None:
        if self._model is None:
            return
        columns = self._display_columns()
        self.hierarchy.blockSignals(True)
        self.hierarchy.clear()
        relative = self.reference_variant_id != ABSOLUTE_REFERENCE_ID
        reference_label = self._reference_label()
        if relative and reference_label is not None:
            self.overview_detail_heading.setText(
                f"Relative Value Details · Reference: {reference_label}"
            )
        else:
            self.overview_detail_heading.setText("Absolute Value Details")
        headers = [
            "Attribute / Scene",
            *(label for _variant, label in columns),
            "Unit",
        ]
        self.hierarchy.setColumnCount(len(headers))
        self.hierarchy.setHeaderLabels(headers)
        header = self.hierarchy.header()
        header.setMinimumSectionSize(56)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 190)
        for column in range(1, len(headers)):
            header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )

        selected_item: QTreeWidgetItem | None = None
        for attribute in self._model.result.attributes:
            parent = QTreeWidgetItem(self.hierarchy)
            parent.setData(
                0,
                Qt.ItemDataRole.UserRole,
                (attribute.attribute_id, None),
            )
            parent.setText(0, attribute.name)
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            for column_index, (variant_id, _label) in enumerate(
                columns,
                start=1,
            ):
                stat = self._stat_for(
                    attribute.attribute_id,
                    None,
                    variant_id,
                )
                parent.setText(column_index, _stat_text(stat))
                _set_stat_tooltip(parent, column_index, stat)
            parent.setText(
                len(headers) - 1,
                self._model.display_unit(
                    attribute.attribute_id,
                    relative=relative,
                ),
            )

            outliers: set[str] = set()
            if relative:
                for target_variant_id, _label in columns:
                    if target_variant_id == self.reference_variant_id:
                        continue
                    outliers.update(
                        self._model.outlier_scene_ids(
                            attribute.attribute_id,
                            self.aggregation_mode,
                            self.reference_variant_id,
                            target_variant_id,
                        )
                    )
            for scene in self._model.result.scenes:
                child = QTreeWidgetItem(parent)
                child.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    (attribute.attribute_id, scene.scene_id),
                )
                child.setText(0, scene.scene_id)
                for column_index, (variant_id, _label) in enumerate(
                    columns,
                    start=1,
                ):
                    stat = self._stat_for(
                        attribute.attribute_id,
                        scene.scene_id,
                        variant_id,
                    )
                    child.setText(column_index, _stat_text(stat))
                    _set_stat_tooltip(child, column_index, stat)
                child.setText(
                    len(headers) - 1,
                    self._model.display_unit(
                        attribute.attribute_id,
                        relative=relative,
                    ),
                )
                if scene.scene_id in outliers:
                    _set_row_bold(child)
                    child.setToolTip(
                        0,
                        "Potential outlier · robust quality-oriented hint",
                    )
            parent.setExpanded(
                attribute.attribute_id == self._selected_attribute_id
            )
            if attribute.attribute_id == self._selected_attribute_id:
                selected_item = parent

        if selected_item is not None:
            self.hierarchy.setCurrentItem(selected_item)
            self.hierarchy.scrollToItem(selected_item)
        self.hierarchy.blockSignals(False)

    def _populate_overview_plot(self) -> None:
        if self._model is None:
            return
        plot = self.overview_plot
        plot.clear()
        self.overview_legend.clear()
        attributes = [
            item
            for item in self._model.result.attributes
            if item.value_kind is ValueKind.POWER
        ]
        self._overview_hover_texts = ()
        self._last_overview_hover_index = None
        if not attributes:
            plot.setTitle("No power attributes")
            return

        columns = self._display_columns()
        self.overview_legend.setColumnCount(min(4, max(1, len(columns))))
        x = np.arange(len(attributes), dtype=np.float64)
        crowded_ticks = len(attributes) >= 6 or any(
            len(item.name) > 14 for item in attributes
        )
        bottom_axis = plot.getAxis("bottom")
        bottom_axis.setStyle(
            autoExpandTextSpace=True,
            autoReduceTextSpace=not crowded_ticks,
            hideOverlappingLabels=False,
            tickTextHeight=40 if crowded_ticks else 18,
        )
        bottom_axis.setTicks(
            [[
                (
                    float(index),
                    _overview_tick_label(item.name, crowded=crowded_ticks),
                )
                for index, item in enumerate(attributes)
            ]]
        )
        width = 0.72 / max(1, len(columns))
        hover_lines = [[attribute.name] for attribute in attributes]
        relative = self.reference_variant_id != ABSOLUTE_REFERENCE_ID
        for series_index, (variant_id, label) in enumerate(columns):
            offset = (series_index - (len(columns) - 1) / 2.0) * width
            values = np.asarray(
                [
                    _stat_plot_value(
                        self._stat_for(
                            item.attribute_id,
                            None,
                            variant_id,
                        )
                    )
                    for item in attributes
                ],
                dtype=np.float64,
            )
            color = _variant_color(series_index, len(columns))
            if relative and variant_id == self.reference_variant_id:
                series_item = pg.ScatterPlotItem(
                    x=x + offset,
                    y=values,
                    symbol="o",
                    size=6,
                    pen=pg.mkPen(color),
                    brush=pg.mkBrush(color),
                )
            else:
                series_item = pg.BarGraphItem(
                    x=x + offset,
                    height=values,
                    width=width * 0.9,
                    brush=color,
                )
            plot.addItem(series_item)
            self.overview_legend.addItem(series_item, label)
            for index, value in enumerate(values):
                unit = self._model.display_unit(
                    attributes[index].attribute_id,
                    relative=relative,
                )
                hover_lines[index].append(
                    f"{label}: {_display_value(value)} {unit}"
                )
        self._overview_hover_texts = tuple(
            "\n".join(lines) for lines in hover_lines
        )
        if self.reference_variant_id == ABSOLUTE_REFERENCE_ID:
            plot.setTitle(
                "Absolute Dataset Overview · pooled weighted mean"
            )
        else:
            plot.addItem(
                pg.InfiniteLine(
                    pos=0.0,
                    angle=0,
                    pen=pg.mkPen(TOKENS.text_secondary),
                )
            )
            reference_label = self._reference_label()
            plot.setTitle(
                "Relative Dataset Overview · "
                f"Reference: {reference_label} · equal-Scene mean"
            )
        plot.setLabel("left", "Value")
        plot.enableAutoRange()

    def _populate_scene_trend(self) -> None:
        if self._model is None:
            return
        plot = self.scene_trend_plot
        plot.clear()
        self._selected_scene_line = None
        self._hover_scene_line = None
        self._scene_hover_texts = ()
        self._last_scene_hover_index = None

        scenes = self._model.result.scenes
        x = np.arange(len(scenes), dtype=np.float64)
        plot.getAxis("bottom").setTicks(
            [[
                (float(index), scene.scene_id)
                for index, scene in enumerate(scenes)
            ]]
        )
        enabled = set(self.enabled_attribute_ids)
        attributes = [
            item
            for item in self._model.result.attributes
            if item.attribute_id in enabled
        ]
        if not attributes:
            self.trend_label.setText("No attributes selected")
            plot.setTitle("No attributes selected")
            return

        columns = self._trend_columns()
        hover_lines = [[scene.scene_id] for scene in scenes]
        total_attributes = len(self._model.result.attributes)
        for attribute in attributes:
            attribute_index = next(
                index
                for index, item in enumerate(self._model.result.attributes)
                if item.attribute_id == attribute.attribute_id
            )
            color = _attribute_color(attribute_index, total_attributes)
            for series_index, (variant_id, label) in enumerate(columns):
                values = np.asarray(
                    [
                        _stat_plot_value(
                            self._stat_for(
                                attribute.attribute_id,
                                scene.scene_id,
                                variant_id,
                            )
                        )
                        for scene in scenes
                    ],
                    dtype=np.float64,
                )
                plot.plot(
                    x,
                    values,
                    pen=_series_pen(color, series_index),
                    symbol=_VARIANT_SYMBOLS[
                        series_index % len(_VARIANT_SYMBOLS)
                    ],
                    symbolSize=6,
                    symbolPen=pg.mkPen(color),
                    symbolBrush=pg.mkBrush(color),
                    connect="finite",
                )
                unit = self._model.display_unit(
                    attribute.attribute_id,
                    relative=(
                        self.reference_variant_id
                        != ABSOLUTE_REFERENCE_ID
                    ),
                )
                for scene_index, value in enumerate(values):
                    hover_lines[scene_index].append(
                        f"{attribute.name} · {label}: "
                        f"{_display_value(value)} {unit}"
                    )

        self._scene_hover_texts = tuple(
            "\n".join(lines) for lines in hover_lines
        )
        relative = self.reference_variant_id != ABSOLUTE_REFERENCE_ID
        mode_label = "Relative" if relative else "Absolute"
        self.trend_label.setText(
            f"{mode_label} Scene trend · {len(attributes)} / "
            f"{len(self._model.result.attributes)} attributes"
        )
        self.series_hint.setText(
            "Attribute = color · variant/target = marker · "
            "click = selected Scene"
        )
        if relative:
            plot.addItem(
                pg.InfiniteLine(
                    pos=0.0,
                    angle=0,
                    pen=pg.mkPen(TOKENS.text_secondary),
                )
            )
        selected_index = self._scene_index(self._selected_scene_id)
        if selected_index is not None:
            self._selected_scene_line = pg.InfiniteLine(
                pos=float(selected_index),
                angle=90,
                movable=False,
                pen=pg.mkPen(TOKENS.warning, width=1),
            )
            plot.addItem(self._selected_scene_line)
        self._hover_scene_line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen(
                TOKENS.text_secondary,
                width=1,
                style=Qt.PenStyle.DashLine,
            ),
        )
        self._hover_scene_line.hide()
        plot.addItem(self._hover_scene_line)
        plot.setTitle(f"{mode_label} values across Scenes")
        plot.setLabel("left", "Value")
        plot.enableAutoRange()

    def _populate_scene_preview(self) -> None:
        _clear_layout(self.preview_layout)
        if self._model is None or self._selected_scene_id is None:
            self.preview_caption.setText(
                "Click a Scene in the trend plot to inspect its published "
                "source identities."
            )
            return
        self.preview_caption.setText(
            f"{self._selected_scene_id} · published source identities · "
            "native inspection deferred to P5-D"
        )
        sources = self._model.scene_sources(self._selected_scene_id)
        for index, (variant_id, label, source) in enumerate(sources):
            card = QFrame(self.preview_container)
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            card_layout = QVBoxLayout(card)
            title = QLabel(f"{label} · {variant_id}", card)
            font = title.font()
            font.setBold(True)
            title.setFont(font)
            card_layout.addWidget(title)
            card_layout.addWidget(QLabel(source.source_id, card))
            card_layout.addWidget(
                QLabel(f"{source.width} × {source.height}", card)
            )
            path_label = QLabel(
                f"Published relative path: {source.relative_path}",
                card,
            )
            path_label.setWordWrap(True)
            path_label.setStyleSheet(f"color: {TOKENS.text_secondary};")
            card_layout.addWidget(path_label)
            hash_label = QLabel(f"SHA-256: {source.sha256[:16]}…", card)
            hash_label.setStyleSheet(f"color: {TOKENS.text_secondary};")
            card_layout.addWidget(hash_label)
            note = QLabel(
                "PixelScope does not open native pixels from this path in P5-B. "
                "P5-D owns logical-root resolution and hash verification.",
                card,
            )
            note.setWordWrap(True)
            card_layout.addWidget(note, 1)
            self.preview_layout.addWidget(card, index // 2, index % 2)
        self.preview_layout.setRowStretch((len(sources) + 1) // 2, 1)

    def _install_dock_title(self) -> None:
        if self._dock_title is not None:
            return
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QDockWidget):
            parent = parent.parentWidget()
        if not isinstance(parent, QDockWidget):
            return
        self._dock_title = PlotsDockTitleBar(
            parent,
            title="IQA Results",
            geometry_setting=IQA_FLOATING_GEOMETRY_SETTING,
        )
        parent.setTitleBarWidget(self._dock_title)
        parent.topLevelChanged.connect(self._dock_title.sync)  # type: ignore[attr-defined]
        self._dock_title.sync(parent.isFloating())

    @Slot()
    def _display_mode_changed(self) -> None:
        if self._model is None or self._relative_loading:
            return
        reference = self.reference_variant_id
        if (
            reference != ABSOLUTE_REFERENCE_ID
            and not self._model.reference_ready(reference)
        ):
            self.show_relative_loading(reference)
            self.relative_requested.emit(reference)
            return
        self._populate_hierarchy()
        self._populate_overview_plot()
        self._populate_scene_trend()

    @Slot(QListWidgetItem)
    def _attribute_filter_changed(self, _item: QListWidgetItem) -> None:
        if self._model is not None:
            self._populate_scene_trend()

    @Slot(object, object)
    def _hierarchy_selection_changed(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None,
    ) -> None:
        if current is None or self._model is None:
            return
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if (
            isinstance(data, tuple)
            and len(data) == 2
            and isinstance(data[0], str)
        ):
            self._selected_attribute_id = data[0]

    @Slot(QPointF)
    def _overview_plot_hovered(self, scene_position: QPointF) -> None:
        index = self._plot_hover_index(
            self.overview_plot,
            scene_position,
            len(self._overview_hover_texts),
        )
        if index is None:
            if self._last_overview_hover_index is not None:
                QToolTip.hideText()
            self._last_overview_hover_index = None
            return
        if index != self._last_overview_hover_index:
            self._last_overview_hover_index = index
            QToolTip.showText(
                QCursor.pos(),
                self._overview_hover_texts[index],
                self.overview_plot,
            )

    @Slot(QPointF)
    def _scene_plot_hovered(self, scene_position: QPointF) -> None:
        index = self._plot_hover_index(
            self.scene_trend_plot,
            scene_position,
            len(self._scene_hover_texts),
        )
        if index is None:
            if self._hover_scene_line is not None:
                self._hover_scene_line.hide()
            if self._last_scene_hover_index is not None:
                QToolTip.hideText()
            self._last_scene_hover_index = None
            return
        if self._hover_scene_line is not None:
            self._hover_scene_line.setPos(float(index))
            self._hover_scene_line.show()
        if index != self._last_scene_hover_index:
            self._last_scene_hover_index = index
            QToolTip.showText(
                QCursor.pos(),
                self._scene_hover_texts[index],
                self.scene_trend_plot,
            )

    @staticmethod
    def _plot_hover_index(
        plot: pg.PlotWidget,
        scene_position: QPointF,
        item_count: int,
    ) -> int | None:
        if item_count <= 0:
            return None
        view_box = plot.plotItem.vb
        if not view_box.sceneBoundingRect().contains(scene_position):
            return None
        index = int(round(float(view_box.mapSceneToView(scene_position).x())))
        return index if 0 <= index < item_count else None

    @Slot(object)
    def _scene_plot_clicked(self, event: object) -> None:
        if self._model is None:
            return
        button_method = getattr(event, "button", None)
        if (
            callable(button_method)
            and button_method() != Qt.MouseButton.LeftButton
        ):
            return
        position_method = getattr(event, "scenePos", None)
        if not callable(position_method):
            return
        scene_position = position_method()
        view_box = self.scene_trend_plot.plotItem.vb
        if not view_box.sceneBoundingRect().contains(scene_position):
            return
        index = int(
            round(float(view_box.mapSceneToView(scene_position).x()))
        )
        self._select_scene_index(index)

    def _select_scene_index(self, scene_index: int) -> None:
        if (
            self._model is None
            or not 0 <= scene_index < len(self._model.result.scenes)
        ):
            return
        scene_id = self._model.result.scenes[scene_index].scene_id
        if scene_id == self._selected_scene_id:
            return
        self._selected_scene_id = scene_id
        self.scene_requested.emit(scene_id)
        self._populate_scene_trend()
        self._populate_scene_preview()

    def _scene_index(self, scene_id: str | None) -> int | None:
        if self._model is None or scene_id is None:
            return None
        for index, scene in enumerate(self._model.result.scenes):
            if scene.scene_id == scene_id:
                return index
        return None


class IqaWorkspaceController(QObject):
    """Asynchronous canonical result open and deferred v2 grid preparation."""

    outcome_ready = Signal(object)

    def __init__(
        self,
        workspace: IqaWorkspaceWidget,
        parent: QObject | None = None,
        *,
        loader: Callable[[Path | str], object] | None = None,
        pool: QThreadPool | None = None,
    ) -> None:
        super().__init__(parent)
        self.workspace = workspace
        self._loader = loader or _load_workspace_result
        self._pool = pool or analysis_thread_pool()
        self._generation = 0
        self._active = True
        self._worker: TaskWorker | None = None
        self._relative_worker: TaskWorker | None = None
        workspace.relative_requested.connect(self.prepare_relative)  # type: ignore[attr-defined]

    def open_result(self, root: Path | str) -> int:
        path = Path(root)
        self._generation += 1
        generation = self._generation
        self._cancel_workers()
        self.workspace.show_loading(path)
        worker = TaskWorker(self._loader, path, generation=generation)
        worker.signals.succeeded.connect(self._result_loaded)  # type: ignore[attr-defined]
        worker.signals.failed.connect(self._load_failed)  # type: ignore[attr-defined]
        worker.signals.finished.connect(self._worker_finished)  # type: ignore[attr-defined]
        self._worker = worker
        self._pool.start(worker)
        return generation

    @Slot(str)
    def prepare_relative(self, reference_variant_id: str) -> None:
        model = self.workspace.model
        if (
            not self._active
            or model is None
            or model.reference_ready(reference_variant_id)
        ):
            return
        if self._relative_worker is not None:
            return
        worker = TaskWorker(
            _prepare_reference_model,
            model,
            reference_variant_id,
            generation=self._generation,
        )
        worker.signals.succeeded.connect(self._relative_loaded)  # type: ignore[attr-defined]
        worker.signals.failed.connect(self._relative_failed)  # type: ignore[attr-defined]
        worker.signals.finished.connect(  # type: ignore[attr-defined]
            self._relative_worker_finished
        )
        self._relative_worker = worker
        self._pool.start(worker)

    def shutdown(self) -> None:
        self._active = False
        self._generation += 1
        self._cancel_workers()

    def _cancel_workers(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
        if self._relative_worker is not None:
            self._relative_worker.cancel()
        self._worker = None
        self._relative_worker = None

    @Slot(str, object, int, object)
    def _result_loaded(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if not self._active or generation != self._generation:
            return
        try:
            outcome = self._present_loaded_value(value)
        except Exception as exc:  # noqa: BLE001 - queued callback boundary
            outcome = VersionedResultLoadOutcome(
                LoadStatus.CORRUPT,
                reason=f"unable to present IQA result: {exc}",
            )
        if outcome.status is not LoadStatus.SUCCESS:
            self.workspace.show_open_error(
                outcome.status,
                outcome.reason or "unknown result error",
            )
        self.outcome_ready.emit(outcome)

    def _present_loaded_value(
        self,
        value: object,
    ) -> VersionedResultLoadOutcome:
        if isinstance(value, _WorkspaceLoadPayload):
            if (
                value.outcome.status is LoadStatus.SUCCESS
                and value.model is not None
            ):
                return self.workspace.set_model(value.model)
            return value.outcome
        if isinstance(value, VersionedResultLoadOutcome):
            if value.status is LoadStatus.SUCCESS and value.result is not None:
                return self.workspace.set_model(IqaExplorerModel(value.result))
            return value
        return VersionedResultLoadOutcome(
            LoadStatus.CORRUPT,
            reason="reader returned no outcome",
        )

    @Slot(str, object, int, object)
    def _relative_loaded(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if not self._active or generation != self._generation:
            return
        if not isinstance(value, IqaExplorerModel):
            outcome = VersionedResultLoadOutcome(
                LoadStatus.CORRUPT,
                reason="relative worker returned no explorer model",
            )
            self.workspace.show_open_error(
                outcome.status,
                outcome.reason or "relative presentation failed",
            )
            self.outcome_ready.emit(outcome)
            return
        outcome = self.workspace.set_relative_model(value)
        if outcome.status is not LoadStatus.SUCCESS:
            self.workspace.show_open_error(
                outcome.status,
                outcome.reason or "relative presentation failed",
            )
        self.outcome_ready.emit(outcome)

    @Slot(str, object, int, object)
    def _load_failed(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if not self._active or generation != self._generation:
            return
        reason = (
            value.message
            if isinstance(value, TaskError)
            else "unexpected reader failure"
        )
        outcome = VersionedResultLoadOutcome(
            LoadStatus.CORRUPT,
            reason=reason,
        )
        self.workspace.show_open_error(outcome.status, reason)
        self.outcome_ready.emit(outcome)

    @Slot(str, object, int, object)
    def _relative_failed(
        self,
        _task_id: str,
        _document_id: object,
        generation: int,
        value: object,
    ) -> None:
        if not self._active or generation != self._generation:
            return
        reason = (
            value.message
            if isinstance(value, TaskError)
            else "unexpected Scene-grid failure"
        )
        outcome = VersionedResultLoadOutcome(
            LoadStatus.CORRUPT,
            reason=reason,
        )
        self.workspace.show_open_error(outcome.status, reason)
        self.outcome_ready.emit(outcome)

    @Slot(str)
    def _worker_finished(self, task_id: str) -> None:
        if self._worker is not None and self._worker.task_id == task_id:
            self._worker = None

    @Slot(str)
    def _relative_worker_finished(self, task_id: str) -> None:
        if (
            self._relative_worker is not None
            and self._relative_worker.task_id == task_id
        ):
            self._relative_worker = None


def _load_workspace_result(root: Path | str) -> _WorkspaceLoadPayload:
    outcome = load_result(root)
    if outcome.status is not LoadStatus.SUCCESS or outcome.result is None:
        return _WorkspaceLoadPayload(outcome)
    try:
        model = IqaExplorerModel(outcome.result)
    except Exception as exc:  # noqa: BLE001 - worker boundary
        return _WorkspaceLoadPayload(
            VersionedResultLoadOutcome(
                LoadStatus.CORRUPT,
                reason=f"unable to project IQA result: {exc}",
            )
        )
    return _WorkspaceLoadPayload(outcome, model)


def _prepare_reference_model(
    model: IqaExplorerModel,
    reference_variant_id: str,
) -> IqaExplorerModel:
    return model.prepare_reference(reference_variant_id)


def _stat_text(statistic: ScalarStatistic) -> str:
    if statistic.valid and statistic.value is not None:
        return f"{statistic.value:.4f}"
    return "—"


def _stat_plot_value(statistic: ScalarStatistic) -> float:
    if (
        statistic.valid
        and statistic.value is not None
        and np.isfinite(statistic.value)
    ):
        return float(statistic.value)
    return float("nan")


def _display_value(value: float) -> str:
    return f"{value:.4f}" if np.isfinite(value) else "—"


def _overview_tick_label(name: str, *, crowded: bool) -> str:
    clean = " ".join(name.split())
    if not crowded or len(clean) <= 12:
        return clean
    words = clean.split()
    if len(words) == 1:
        return clean if len(clean) <= 18 else f"{clean[:17]}…"
    best_split = min(
        range(1, len(words)),
        key=lambda index: max(
            len(" ".join(words[:index])),
            len(" ".join(words[index:])),
        ),
    )
    return f"{' '.join(words[:best_split])}\n{' '.join(words[best_split:])}"


def _set_stat_tooltip(
    item: QTreeWidgetItem,
    column: int,
    statistic: ScalarStatistic,
) -> None:
    if statistic.valid and statistic.value is not None:
        item.setToolTip(column, f"{statistic.value:.4f}")
    else:
        item.setToolTip(column, statistic.invalid_reason or "invalid")


def _set_row_bold(item: QTreeWidgetItem) -> None:
    for column in range(item.columnCount()):
        font: QFont = item.font(column)
        font.setBold(True)
        item.setFont(column, font)


def _attribute_color(index: int, total: int) -> QColor:
    if total <= 1:
        return QColor(TOKENS.accent)
    hue = int(round(330.0 * index / max(1, total - 1)))
    return QColor.fromHsv(hue, 165, 235)


def _variant_color(index: int, total: int) -> QColor:
    if total <= 1:
        return QColor(TOKENS.accent)
    hue = int(round(300.0 * index / max(1, total - 1)))
    return QColor.fromHsv(hue, 140, 225)


def _color_chip_icon(color: QColor) -> QIcon:
    pixmap = QPixmap(12, 12)
    pixmap.fill(color)
    return QIcon(pixmap)


def _series_pen(color: QColor, series_index: int) -> QPen:
    pen = QPen(color)
    pen.setWidthF(1.7)
    pen.setCosmetic(True)
    styles = (
        Qt.PenStyle.SolidLine,
        Qt.PenStyle.DashLine,
        Qt.PenStyle.DotLine,
    )
    pen.setStyle(styles[series_index % len(styles)])
    return pen


def _clear_layout(layout: QGridLayout) -> None:
    while layout.count():
        child = layout.takeAt(0)
        widget = child.widget()
        if widget is not None:
            widget.deleteLater()
