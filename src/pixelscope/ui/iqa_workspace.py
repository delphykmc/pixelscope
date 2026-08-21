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
    Result,
    ResultLoadOutcome,
    ScalarStatistic,
    Source,
    ValueKind,
)
from pixelscope.remote.iqa_explorer import IqaExplorerModel, UnsupportedIqaExplorerResult
from pixelscope.remote.iqa_reader import load_result
from pixelscope.ui.design_tokens import TOKENS
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar
from pixelscope.workers.task_worker import TaskError, TaskWorker
from pixelscope.workers.thread_pools import analysis_thread_pool

MODE_LABELS = {
    ComparisonMode.RATIO_OF_WEIGHTED_MEANS: "Ratio of weighted means",
    ComparisonMode.MEAN_OF_GRID_LOG_RATIOS: "Mean of grid log ratios",
}
IQA_FLOATING_GEOMETRY_SETTING = "ui/iqa_floating_geometry"


@dataclass(frozen=True)
class _WorkspaceLoadPayload:
    outcome: ResultLoadOutcome
    model: IqaExplorerModel | None = None


class IqaWorkspaceWidget(QWidget):
    """Hierarchical Tier-1 IQA explorer with multi-attribute Scene trends."""

    scene_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("iqaWorkspace")
        self._model: IqaExplorerModel | None = None
        self._dock_title: PlotsDockTitleBar | None = None
        self._selected_attribute_id: str | None = None
        self._selected_scene_id: str | None = None
        self._selected_scene_line: pg.InfiniteLine | None = None
        self._hover_scene_line: pg.InfiniteLine | None = None
        self._overview_hover_texts: tuple[str, ...] = ()
        self._scene_hover_texts: tuple[str, ...] = ()
        self._last_overview_hover_index: int | None = None
        self._last_scene_hover_index: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(TOKENS.spacing_sm, TOKENS.spacing_sm, TOKENS.spacing_sm, 0)
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
        self.reference_combo.addItem("B — second source (A vs B)", 1)
        self.reference_combo.addItem("A — first source (B vs A)", 0)
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

        self.overview_splitter = QSplitter(Qt.Orientation.Vertical, self.overview_page)
        self.overview_splitter.setObjectName("iqaOverviewSplitter")

        self.overview_plot = pg.PlotWidget(self.overview_splitter)
        self.overview_plot.setObjectName("iqaAttributeOverviewPlot")
        self.overview_plot.setMinimumHeight(130)
        self.overview_plot.setBackground(TOKENS.workspace_background)
        self.overview_plot.showGrid(x=False, y=True, alpha=0.2)
        self.overview_plot.scene().sigMouseMoved.connect(self._overview_plot_hovered)

        self.hierarchy = QTreeWidget(self.overview_splitter)
        self.hierarchy.setObjectName("iqaAttributeSceneHierarchy")
        self.hierarchy.setColumnCount(4)
        self.hierarchy.setAlternatingRowColors(True)
        self.hierarchy.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.hierarchy.setUniformRowHeights(True)
        header = self.hierarchy.header()
        header.setMinimumSectionSize(56)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 190)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.hierarchy.currentItemChanged.connect(  # type: ignore[attr-defined]
            self._hierarchy_selection_changed
        )
        self.overview_splitter.addWidget(self.overview_plot)
        self.overview_splitter.addWidget(self.hierarchy)
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
            "Attribute = color   hover: dashed guide   click: selected guide",
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
        self.attribute_filter.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.attribute_filter.setMinimumWidth(150)
        self.attribute_filter.setMaximumWidth(230)
        self.attribute_filter.setStyleSheet(
            "QListWidget { border: 1px solid palette(mid); border-radius: 4px; }"
            "QListWidget::item { padding: 4px 6px; margin: 1px 0; border-radius: 3px; }"
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
        self.scene_trend_plot.scene().sigMouseClicked.connect(self._scene_plot_clicked)
        self.scene_trend_plot.scene().sigMouseMoved.connect(self._scene_plot_hovered)
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
            "Click a Scene in the trend plot to inspect its published source identities.",
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
    def result(self) -> Result | None:
        return self._model.result if self._model is not None else None

    @property
    def aggregation_mode(self) -> ComparisonMode:
        data = self.mode_combo.currentData()
        try:
            return ComparisonMode(str(data))
        except ValueError:
            return ComparisonMode.RATIO_OF_WEIGHTED_MEANS

    @property
    def reference_index(self) -> int:
        try:
            value = int(self.reference_combo.currentData())
        except (TypeError, ValueError):
            return 1
        return value if value in (0, 1) else 1

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
            if isinstance(attribute_id, str) and item.checkState() == Qt.CheckState.Checked:
                enabled.append(attribute_id)
        return tuple(enabled)

    def showEvent(self, event: QShowEvent) -> None:
        self._install_dock_title()
        super().showEvent(event)

    def show_loading(self, root: Path) -> None:
        self.status_label.setText(f"Opening {root.name}...")

    def show_open_error(self, status: LoadStatus, reason: str) -> None:
        self.status_label.setText(f"{status.value.upper()}: {reason}")

    def set_result(self, result: Result) -> ResultLoadOutcome:
        """Synchronously project a Result; normal controller opens off-thread."""

        try:
            model = IqaExplorerModel(result)
        except UnsupportedIqaExplorerResult as exc:
            return ResultLoadOutcome(LoadStatus.UNSUPPORTED, reason=str(exc))
        except Exception as exc:  # noqa: BLE001 - presentation boundary normalizes failures
            return ResultLoadOutcome(
                LoadStatus.CORRUPT,
                reason=f"unable to project IQA result: {exc}",
            )
        return self.set_model(model)

    def set_model(self, model: IqaExplorerModel) -> ResultLoadOutcome:
        previous_model = self._model
        previous_attribute = self._selected_attribute_id
        previous_scene = self._selected_scene_id
        self._model = model
        if previous_attribute not in {
            attribute.attribute_id for attribute in model.result.attributes
        }:
            self._selected_attribute_id = model.result.attributes[0].attribute_id
        if previous_scene not in {scene.scene_id for scene in model.result.scenes}:
            self._selected_scene_id = None
        try:
            self._refresh_model_views()
        except Exception as exc:  # noqa: BLE001 - queued Qt callback must not escape
            self._model = previous_model
            self._selected_attribute_id = previous_attribute
            self._selected_scene_id = previous_scene
            if previous_model is not None:
                try:
                    self._refresh_model_views()
                except Exception:  # noqa: BLE001 - retain best-effort previous view
                    pass
            else:
                self._clear_model_views()
            return ResultLoadOutcome(
                LoadStatus.CORRUPT,
                reason=f"unable to present IQA result: {exc}",
            )

        result = model.result
        source_count = sum(len(scene.sources) for scene in result.scenes)
        self.result_label.setText(
            f"Job/result {result.result_id} · schema v{result.schema_version}"
        )
        self.dataset_label.setText(
            f"{len(result.scenes)} Scenes · {source_count} Scene sources · "
            f"{len(result.attributes)} attributes"
        )
        self.status_label.setText(f"Opened {result.root.name}")
        self._set_controls_enabled(True)
        return ResultLoadOutcome(LoadStatus.SUCCESS, result=result)

    def _refresh_model_views(self) -> None:
        self._populate_attribute_filter()
        self._populate_hierarchy()
        self._populate_overview_plot()
        self._populate_scene_trend()
        self._populate_scene_preview()

    def _clear_model_views(self) -> None:
        self.attribute_filter.clear()
        self.hierarchy.clear()
        self.overview_plot.clear()
        self.scene_trend_plot.clear()
        _clear_layout(self.preview_layout)
        self._set_controls_enabled(False)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.reference_combo.setEnabled(enabled)
        self.mode_combo.setEnabled(enabled)
        self.hierarchy.setEnabled(enabled)
        self.attribute_filter.setEnabled(enabled)
        self.pages.setEnabled(enabled)

    def _populate_attribute_filter(self) -> None:
        if self._model is None:
            return
        previous = {
            item.data(Qt.ItemDataRole.UserRole): item.checkState()
            for row in range(self.attribute_filter.count())
            if (item := self.attribute_filter.item(row)) is not None
        }
        self.attribute_filter.blockSignals(True)
        self.attribute_filter.clear()
        total = len(self._model.result.attributes)
        for index, attribute in enumerate(self._model.result.attributes):
            item = QListWidgetItem(attribute.name, self.attribute_filter)
            item.setData(Qt.ItemDataRole.UserRole, attribute.attribute_id)
            item.setCheckState(previous.get(attribute.attribute_id, Qt.CheckState.Checked))
            item.setIcon(_color_chip_icon(_attribute_color(index, total)))
            item.setToolTip(f"Check to show/hide · {attribute.name} · {attribute.unit}")
        self.attribute_filter.blockSignals(False)

    def _populate_hierarchy(self) -> None:
        if self._model is None:
            return
        selected_attribute = self._selected_attribute_id
        reference = self.reference_index
        target = "B vs A" if reference == 0 else "A vs B"
        self.hierarchy.blockSignals(True)
        self.hierarchy.clear()
        self.hierarchy.setHeaderLabels(("Attribute / Scene", target, "", "Unit"))
        selected_item: QTreeWidgetItem | None = None
        for attribute in self._model.result.attributes:
            parent = QTreeWidgetItem(self.hierarchy)
            parent.setData(0, Qt.ItemDataRole.UserRole, (attribute.attribute_id, None))
            parent.setText(0, attribute.name)
            parent_font = parent.font(0)
            parent_font.setBold(True)
            parent.setFont(0, parent_font)
            relative_mean = self._model.relative_attribute_mean(
                attribute.attribute_id,
                self.aggregation_mode,
                reference,
            )
            parent.setText(1, _stat_text(relative_mean))
            parent.setText(3, self._model.display_unit(attribute.attribute_id))
            relative_points = self._model.relative_trend(
                attribute.attribute_id,
                self.aggregation_mode,
                reference,
            )
            outliers = set(
                self._model.outlier_scene_ids(
                    attribute.attribute_id,
                    self.aggregation_mode,
                    reference,
                )
            )
            for relative_point in relative_points:
                child = QTreeWidgetItem(parent)
                child.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    (attribute.attribute_id, relative_point.scene_id),
                )
                child.setText(0, relative_point.scene_id)
                child.setText(1, _stat_text(relative_point.value))
                child.setText(3, self._model.display_unit(attribute.attribute_id))
                _set_stat_tooltip(child, 1, relative_point.value)
                if relative_point.scene_id in outliers:
                    _set_row_bold(child)
                    child.setToolTip(0, "Potential outlier · robust distribution heuristic")
            parent.setExpanded(attribute.attribute_id == selected_attribute)
            if attribute.attribute_id == selected_attribute:
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
        legend = plot.addLegend(offset=(8, 8))
        legend.clear()
        self._overview_hover_texts = ()
        self._last_overview_hover_index = None
        attributes = [
            attribute
            for attribute in self._model.result.attributes
            if attribute.value_kind is ValueKind.POWER
        ]
        if not attributes:
            plot.setTitle("No power attributes")
            return
        x = np.arange(len(attributes), dtype=np.float64)
        plot.getAxis("bottom").setTicks(
            [[(float(index), item.name) for index, item in enumerate(attributes)]]
        )
        reference = self.reference_index
        target = "B vs A" if reference == 0 else "A vs B"
        relative_values = np.asarray(
            [
                _stat_plot_value(
                    self._model.relative_attribute_mean(
                        item.attribute_id,
                        self.aggregation_mode,
                        reference,
                    )
                )
                for item in attributes
            ],
            dtype=np.float64,
        )
        relative_bar = pg.BarGraphItem(
            x=x,
            height=relative_values,
            width=0.62,
            brush=QColor(TOKENS.accent),
        )
        plot.addItem(relative_bar)
        plot.addItem(pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen(TOKENS.text_secondary)))
        legend.addItem(relative_bar, target)
        self._overview_hover_texts = tuple(
            f"{item.name}\n{target}: {_display_value(value)} dB"
            for item, value in zip(attributes, relative_values, strict=True)
        )
        plot.setTitle(f"Power attribute mean across Scenes · {target}")
        plot.setLabel("left", "Relative power", units="dB")
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
            [[(float(index), scene.scene_id) for index, scene in enumerate(scenes)]]
        )
        enabled = set(self.enabled_attribute_ids)
        attributes = [
            attribute
            for attribute in self._model.result.attributes
            if attribute.attribute_id in enabled
        ]
        if not attributes:
            self.trend_label.setText("No attributes selected")
            self.series_hint.setText("Check one or more attributes to show Scene trends.")
            plot.setTitle("No attributes selected")
            return

        reference = self.reference_index
        target = "B vs A" if reference == 0 else "A vs B"
        hover_lines = [[f"{scene.scene_id} · {target}"] for scene in scenes]
        total = len(self._model.result.attributes)
        all_units: set[str] = set()
        for attribute in attributes:
            attribute_index = self._attribute_index(attribute.attribute_id)
            color = _attribute_color(attribute_index, total)
            relative_points = self._model.relative_trend(
                attribute.attribute_id,
                self.aggregation_mode,
                reference,
            )
            relative_values = np.asarray(
                [_stat_plot_value(point.value) for point in relative_points],
                dtype=np.float64,
            )
            plot.plot(
                x,
                relative_values,
                pen=_series_pen(color),
                symbol="d",
                symbolSize=7,
                symbolPen=pg.mkPen(color),
                symbolBrush=pg.mkBrush(color),
                connect="finite",
            )
            unit = self._model.display_unit(attribute.attribute_id)
            for scene_index, value in enumerate(relative_values):
                hover_lines[scene_index].append(
                    f"{attribute.name}: {_display_value(value)} {unit}"
                )
            all_units.add(unit)

        self._scene_hover_texts = tuple("\n".join(lines) for lines in hover_lines)
        self.trend_label.setText(
            f"Scene trend · {target} · {len(attributes)} / "
            f"{len(self._model.result.attributes)} attributes"
        )
        self.series_hint.setText(
            "Attribute = color   ◇ published comparison   "
            "hover: dashed guide   click: selected guide"
        )
        plot.addItem(pg.InfiniteLine(pos=0.0, angle=0, pen=pg.mkPen(TOKENS.text_secondary)))
        plot.setTitle(f"{target} across Scenes · hover a Scene for values")

        if len(all_units) == 1:
            plot.setLabel("left", "Value", units=next(iter(all_units)))
        else:
            plot.setLabel("left", "Value · mixed attribute units")

        scene_index = self._scene_index(self._selected_scene_id)
        if scene_index is not None:
            self._selected_scene_line = pg.InfiniteLine(
                pos=float(scene_index),
                angle=90,
                movable=False,
                pen=pg.mkPen(TOKENS.warning, width=1),
            )
            plot.addItem(self._selected_scene_line)
        self._hover_scene_line = pg.InfiniteLine(
            pos=0.0,
            angle=90,
            movable=False,
            pen=pg.mkPen(TOKENS.text_secondary, width=1, style=Qt.PenStyle.DashLine),
        )
        self._hover_scene_line.hide()
        plot.addItem(self._hover_scene_line)
        plot.enableAutoRange()

    def _populate_scene_preview(self) -> None:
        _clear_layout(self.preview_layout)
        if self._model is None or self._selected_scene_id is None:
            self.preview_caption.setText(
                "Click a Scene in the trend plot to inspect its published source identities."
            )
            return
        scene = self._model.result.scene(self._selected_scene_id)
        self.preview_caption.setText(
            f"{scene.scene_id} · source identities · image inspection is deferred to P5-D"
        )
        for index, source in enumerate(scene.sources):
            card = self._source_card(source, index)
            self.preview_layout.addWidget(card, index // 2, index % 2)
        self.preview_layout.setRowStretch((len(scene.sources) + 1) // 2, 1)

    def _source_card(self, source: Source, source_index: int) -> QWidget:
        card = QFrame(self.preview_container)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            TOKENS.spacing_sm, TOKENS.spacing_sm, TOKENS.spacing_sm, TOKENS.spacing_sm
        )
        role = chr(ord("A") + source_index)
        title = QLabel(f"{role} · {source.source_id}", card)
        title_font = title.font()
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        dimensions = QLabel(f"{source.width} × {source.height}", card)
        layout.addWidget(dimensions)
        path_label = QLabel(f"Published relative path: {source.relative_path}", card)
        path_label.setWordWrap(True)
        path_label.setStyleSheet(f"color: {TOKENS.text_secondary};")
        layout.addWidget(path_label)
        hash_label = QLabel(f"SHA-256: {source.sha256[:16]}…", card)
        hash_label.setStyleSheet(f"color: {TOKENS.text_secondary};")
        layout.addWidget(hash_label)
        inspection = QLabel(
            "Source pixels are not opened from this path in P5-B. "
            "P5-D Inspect Pair owns logical-root resolution and hash verification.",
            card,
        )
        inspection.setWordWrap(True)
        layout.addWidget(inspection, 1)
        return card

    def _attribute_index(self, attribute_id: str) -> int:
        if self._model is None:
            return 0
        for index, attribute in enumerate(self._model.result.attributes):
            if attribute.attribute_id == attribute_id:
                return index
        return 0

    def _scene_index(self, scene_id: str | None) -> int | None:
        if self._model is None or scene_id is None:
            return None
        for index, scene in enumerate(self._model.result.scenes):
            if scene.scene_id == scene_id:
                return index
        return None

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
        if self._model is None:
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
        if not isinstance(data, tuple) or len(data) != 2:
            return
        attribute_id, _scene_id = data
        if isinstance(attribute_id, str):
            self._selected_attribute_id = attribute_id

    @Slot(QPointF)
    def _overview_plot_hovered(self, scene_position: QPointF) -> None:
        hover_index = self._plot_hover_index(
            self.overview_plot,
            scene_position,
            len(self._overview_hover_texts),
        )
        if hover_index is None:
            if self._last_overview_hover_index is not None:
                QToolTip.hideText()
            self._last_overview_hover_index = None
            return
        if hover_index == self._last_overview_hover_index:
            return
        self._last_overview_hover_index = hover_index
        QToolTip.showText(
            QCursor.pos(),
            self._overview_hover_texts[hover_index],
            self.overview_plot,
        )

    @Slot(QPointF)
    def _scene_plot_hovered(self, scene_position: QPointF) -> None:
        hover_index = self._plot_hover_index(
            self.scene_trend_plot,
            scene_position,
            len(self._scene_hover_texts),
        )
        if hover_index is None:
            if self._hover_scene_line is not None:
                self._hover_scene_line.hide()
            if self._last_scene_hover_index is not None:
                QToolTip.hideText()
            self._last_scene_hover_index = None
            return
        if self._hover_scene_line is not None:
            self._hover_scene_line.setPos(float(hover_index))
            self._hover_scene_line.show()
        if hover_index == self._last_scene_hover_index:
            return
        self._last_scene_hover_index = hover_index
        QToolTip.showText(
            QCursor.pos(),
            self._scene_hover_texts[hover_index],
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
        coordinate = view_box.mapSceneToView(scene_position)
        index = int(round(float(coordinate.x())))
        return index if 0 <= index < item_count else None

    @Slot(object)
    def _scene_plot_clicked(self, event: object) -> None:
        if self._model is None:
            return
        button_method = getattr(event, "button", None)
        if callable(button_method) and button_method() != Qt.MouseButton.LeftButton:
            return
        position_method = getattr(event, "scenePos", None)
        if not callable(position_method):
            return
        scene_position = position_method()
        view_box = self.scene_trend_plot.plotItem.vb
        if not view_box.sceneBoundingRect().contains(scene_position):
            return
        coordinate = view_box.mapSceneToView(scene_position)
        scene_index = int(round(float(coordinate.x())))
        self._select_scene_index(scene_index)

    def _select_scene_index(self, scene_index: int) -> None:
        if self._model is None or not 0 <= scene_index < len(self._model.result.scenes):
            return
        scene_id = self._model.result.scenes[scene_index].scene_id
        if scene_id == self._selected_scene_id:
            return
        self._selected_scene_id = scene_id
        self.scene_requested.emit(scene_id)
        self._populate_scene_trend()
        self._populate_scene_preview()


class IqaWorkspaceController(QObject):
    """Canonical asynchronous opener for immutable local IQA results."""

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

    def open_result(self, root: Path | str) -> int:
        path = Path(root)
        self._generation += 1
        generation = self._generation
        if self._worker is not None:
            self._worker.cancel()
        self.workspace.show_loading(path)
        worker = TaskWorker(self._loader, path, generation=generation)
        worker.signals.succeeded.connect(self._result_loaded)
        worker.signals.failed.connect(self._load_failed)
        worker.signals.finished.connect(self._worker_finished)
        self._worker = worker
        self._pool.start(worker)
        return generation

    def shutdown(self) -> None:
        self._active = False
        self._generation += 1
        if self._worker is not None:
            self._worker.cancel()
        self._worker = None

    @Slot(str, object, int, object)
    def _result_loaded(
        self, _task_id: str, _document_id: object, generation: int, value: object
    ) -> None:
        if not self._active or generation != self._generation:
            return
        try:
            outcome = self._present_loaded_value(value)
        except Exception as exc:  # noqa: BLE001 - queued callback must not escape
            outcome = ResultLoadOutcome(
                LoadStatus.CORRUPT,
                reason=f"unable to present IQA result: {exc}",
            )
        if outcome.status is not LoadStatus.SUCCESS:
            self.workspace.show_open_error(outcome.status, outcome.reason or "unknown result error")
        self.outcome_ready.emit(outcome)

    def _present_loaded_value(self, value: object) -> ResultLoadOutcome:
        if isinstance(value, _WorkspaceLoadPayload):
            if value.outcome.status is LoadStatus.SUCCESS and value.model is not None:
                return self.workspace.set_model(value.model)
            return value.outcome
        if not isinstance(value, ResultLoadOutcome):
            return ResultLoadOutcome(LoadStatus.CORRUPT, reason="reader returned no outcome")
        if value.status is LoadStatus.SUCCESS and value.result is not None:
            return self.workspace.set_result(value.result)
        return value

    @Slot(str, object, int, object)
    def _load_failed(
        self, _task_id: str, _document_id: object, generation: int, value: object
    ) -> None:
        if not self._active or generation != self._generation:
            return
        reason = value.message if isinstance(value, TaskError) else "unexpected reader failure"
        outcome = ResultLoadOutcome(LoadStatus.CORRUPT, reason=reason)
        self.workspace.show_open_error(outcome.status, reason)
        self.outcome_ready.emit(outcome)

    @Slot(str)
    def _worker_finished(self, task_id: str) -> None:
        if self._worker is not None and self._worker.task_id == task_id:
            self._worker = None


def _load_workspace_result(root: Path | str) -> _WorkspaceLoadPayload:
    outcome = load_result(root)
    if outcome.status is not LoadStatus.SUCCESS or outcome.result is None:
        return _WorkspaceLoadPayload(outcome)
    try:
        model = IqaExplorerModel(outcome.result)
    except UnsupportedIqaExplorerResult as exc:
        return _WorkspaceLoadPayload(ResultLoadOutcome(LoadStatus.UNSUPPORTED, reason=str(exc)))
    except Exception as exc:  # noqa: BLE001 - worker boundary converts artifact failures
        return _WorkspaceLoadPayload(
            ResultLoadOutcome(
                LoadStatus.CORRUPT,
                reason=f"unable to project IQA result: {exc}",
            )
        )
    return _WorkspaceLoadPayload(outcome, model)


def _stat_text(statistic: ScalarStatistic) -> str:
    if statistic.valid and statistic.value is not None:
        return f"{statistic.value:.4f}"
    return "—"


def _stat_plot_value(statistic: ScalarStatistic) -> float:
    if statistic.valid and statistic.value is not None and np.isfinite(statistic.value):
        return float(statistic.value)
    return float("nan")


def _display_value(value: float) -> str:
    return f"{value:.4f}" if np.isfinite(value) else "—"


def _set_stat_tooltip(item: QTreeWidgetItem, column: int, statistic: ScalarStatistic) -> None:
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


def _color_chip_icon(color: QColor) -> QIcon:
    pixmap = QPixmap(12, 12)
    pixmap.fill(color)
    return QIcon(pixmap)


def _series_pen(color: QColor) -> QPen:
    pen = QPen(color)
    pen.setWidthF(1.7)
    pen.setCosmetic(True)
    pen.setStyle(Qt.PenStyle.SolidLine)
    return pen


def _clear_layout(layout: QGridLayout) -> None:
    while layout.count():
        child = layout.takeAt(0)
        widget = child.widget()
        if widget is not None:
            widget.deleteLater()
