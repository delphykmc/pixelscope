from __future__ import annotations

from pathlib import Path

import pyqtgraph as pg
import pytest
from PySide6.QtCore import QSettings, QRect, Qt, QThreadPool
from PySide6.QtWidgets import QFileDialog, QLabel

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_domain import ComparisonMode, LoadStatus
from pixelscope.remote.iqa_explorer import ABSOLUTE_REFERENCE_ID, IqaExplorerModel
from pixelscope.remote.iqa_result_reader import load_result
from pixelscope.remote.iqa_v2_domain import VersionedResultLoadOutcome
from pixelscope.remote.iqa_v2_fixture import write_golden_result_v2
from pixelscope.ui.iqa_workspace import (
    IQA_FLOATING_GEOMETRY_SETTING,
    IqaWorkspaceController,
    IqaWorkspaceWidget,
    _overview_tick_label,
)
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar


@pytest.fixture(autouse=True)
def isolated_ui_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    QSettings().clear()


@pytest.fixture()
def result_root(tmp_path: Path) -> Path:
    return write_golden_result_v2(tmp_path / "golden-v2", scene_count=4)


def _loaded(root: Path):  # type annotation would obscure assertion narrowing
    outcome = load_result(root)
    assert outcome.status is LoadStatus.SUCCESS
    assert outcome.result is not None
    return outcome.result


def _overview_legend_labels(widget: IqaWorkspaceWidget) -> list[str]:
    labels: list[str] = []
    for index in range(widget.overview_legend_layout.count()):
        entry = widget.overview_legend_layout.itemAt(index).widget()
        if entry is None:
            continue
        label = entry.findChild(QLabel, "iqaOverviewLegendLabel")
        if label is not None:
            labels.append(label.text())
    return labels


def test_workspace_defaults_to_absolute_nway_summary_view(
    qtbot: object,
    result_root: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]

    outcome = widget.set_model(IqaExplorerModel(_loaded(result_root)))

    assert outcome.status is LoadStatus.SUCCESS
    assert "schema v2" in widget.result_label.text()
    assert "3 variants" in widget.dataset_label.text()
    assert widget.reference_variant_id == ABSOLUTE_REFERENCE_ID
    assert widget.reference_combo.itemText(0) == "Absolute measurements"
    assert widget.hierarchy.topLevelItemCount() == 10
    assert widget.hierarchy.columnCount() == 5
    headers = [
        widget.hierarchy.headerItem().text(index)
        for index in range(widget.hierarchy.columnCount())
    ]
    assert "Baseline" in headers
    assert "Candidate Fast" in headers
    assert "Candidate Quality" in headers
    assert "pooled weighted mean" in widget.overview_plot.plotItem.titleLabel.text
    assert _overview_legend_labels(widget) == [
        "Baseline",
        "Candidate Fast",
        "Candidate Quality",
    ]
    assert sum(
        isinstance(item, pg.BarGraphItem)
        for item in widget.overview_plot.plotItem.items
    ) == 3
    assert widget.overview_chart_layout.indexOf(widget.overview_plot) == 0
    assert widget.overview_chart_layout.indexOf(widget.overview_legend) == 1
    assert widget.model is not None
    assert not widget.model.reference_ready("baseline")


def test_overview_tick_labels_wrap_crowded_multiword_names() -> None:
    assert _overview_tick_label("Luma Noise", crowded=False) == "Luma Noise"
    assert _overview_tick_label("Luma Noise", crowded=True) == "Luma Noise"
    assert _overview_tick_label(
        "Chromatic Aberration",
        crowded=True,
    ) == "Chromatic\nAberration"
    assert _overview_tick_label(
        "VeryLongSingleTokenAttribute",
        crowded=True,
    ) == "VeryLongSingleTok…"


def test_reference_selection_requests_lazy_grid_preparation(
    qtbot: object,
    result_root: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    assert (
        widget.set_model(IqaExplorerModel(_loaded(result_root))).status
        is LoadStatus.SUCCESS
    )
    requested: list[str] = []
    widget.relative_requested.connect(requested.append)

    index = widget.reference_combo.findData("baseline")
    widget.reference_combo.setCurrentIndex(index)

    assert requested == ["baseline"]
    assert "Loading Scene grids" in widget.status_label.text()
    assert not widget.reference_combo.isEnabled()


def test_relative_model_preserves_reference_and_projects_all_targets(
    qtbot: object,
    result_root: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    model = IqaExplorerModel(_loaded(result_root))
    assert widget.set_model(model).status is LoadStatus.SUCCESS
    widget.reference_combo.blockSignals(True)
    widget.reference_combo.setCurrentIndex(
        widget.reference_combo.findData("baseline")
    )
    widget.reference_combo.blockSignals(False)

    outcome = widget.set_relative_model(model.prepare_reference("baseline"))

    assert outcome.status is LoadStatus.SUCCESS
    assert widget.reference_variant_id == "baseline"
    assert widget.model is not None
    assert widget.model.reference_ready("baseline")
    assert widget.hierarchy.columnCount() == 4
    headers = [
        widget.hierarchy.headerItem().text(index)
        for index in range(widget.hierarchy.columnCount())
    ]
    assert "Candidate Fast vs Baseline" in headers
    assert "Candidate Quality vs Baseline" in headers
    assert "equal-Scene mean" in widget.overview_plot.plotItem.titleLabel.text
    assert _overview_legend_labels(widget) == [
        "Candidate Fast",
        "Candidate Quality",
    ]
    assert "Baseline" not in _overview_legend_labels(widget)
    assert sum(
        isinstance(item, pg.BarGraphItem)
        for item in widget.overview_plot.plotItem.items
    ) == 2

    widget.mode_combo.setCurrentIndex(
        widget.mode_combo.findData(
            ComparisonMode.MEAN_OF_GRID_LOG_RATIOS.value
        )
    )
    assert (
        widget.aggregation_mode
        is ComparisonMode.MEAN_OF_GRID_LOG_RATIOS
    )


def test_switching_to_unprepared_reference_requests_only_that_reference(
    qtbot: object,
    result_root: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    model = IqaExplorerModel(_loaded(result_root)).prepare_reference("baseline")
    assert widget.set_model(model).status is LoadStatus.SUCCESS
    requested: list[str] = []
    widget.relative_requested.connect(requested.append)

    widget.reference_combo.setCurrentIndex(
        widget.reference_combo.findData("candidate_fast")
    )

    assert requested == ["candidate_fast"]
    assert model.reference_ready("baseline")
    assert not model.reference_ready("candidate_fast")


def test_scene_trend_filters_and_source_cards_keep_native_pixels_out_of_p5b(
    qtbot: object,
    result_root: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    assert (
        widget.set_model(IqaExplorerModel(_loaded(result_root))).status
        is LoadStatus.SUCCESS
    )

    assert len(widget.enabled_attribute_ids) == 10
    first = widget.attribute_filter.item(0)
    assert not first.icon().isNull()
    assert first.flags() & Qt.ItemFlag.ItemIsUserCheckable
    first.setCheckState(Qt.CheckState.Unchecked)
    assert len(widget.enabled_attribute_ids) == 9

    widget._select_scene_index(1)
    assert widget.selected_scene_id == "scene_000001"
    assert widget.preview_layout.count() == 3
    first_card = widget.preview_layout.itemAt(0).widget()
    assert first_card is not None
    text = "\n".join(
        label.text() for label in first_card.findChildren(QLabel)
    )
    assert "Published relative path" in text
    assert "P5-D" in text


def test_late_presentation_failure_restores_previous_visible_result(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    result_root: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    model = IqaExplorerModel(_loaded(result_root))
    assert widget.set_model(model).status is LoadStatus.SUCCESS
    before = widget.result_label.text()
    original = widget._populate_scene_trend
    calls = 0

    def fail_once_after_mutation() -> None:
        nonlocal calls
        calls += 1
        original()
        if calls == 1:
            raise RuntimeError("injected late presentation failure")

    monkeypatch.setattr(
        widget,
        "_populate_scene_trend",
        fail_once_after_mutation,
    )
    outcome = widget.set_model(model)

    assert outcome.status is LoadStatus.CORRUPT
    assert widget.result_label.text() == before
    assert widget.model is model
    assert calls == 2


def test_controller_opens_v2_then_prepares_reference_off_thread(
    qtbot: object,
    result_root: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    pool = QThreadPool(widget)
    controller = IqaWorkspaceController(widget, pool=pool)
    outcomes: list[VersionedResultLoadOutcome] = []
    controller.outcome_ready.connect(outcomes.append)

    controller.open_result(result_root)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: widget.model is not None,
        timeout=5000,
    )
    assert widget.model is not None
    assert not widget.model.reference_ready("baseline")

    widget.reference_combo.setCurrentIndex(
        widget.reference_combo.findData("baseline")
    )
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: (
            widget.model is not None
            and widget.model.reference_ready("baseline")
        ),
        timeout=5000,
    )
    assert widget.reference_variant_id == "baseline"
    assert any(
        outcome.status is LoadStatus.SUCCESS for outcome in outcomes
    )
    controller.shutdown()
    assert pool.waitForDone(5000)


def test_failed_open_does_not_replace_last_valid_result(
    qtbot: object,
    result_root: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    valid = IqaExplorerModel(_loaded(result_root))
    assert widget.set_model(valid).status is LoadStatus.SUCCESS
    controller = IqaWorkspaceController(
        widget,
        loader=lambda _root: VersionedResultLoadOutcome(
            LoadStatus.CORRUPT,
            reason="synthetic corruption",
        ),
        pool=QThreadPool(widget),
    )
    outcomes: list[VersionedResultLoadOutcome] = []
    controller.outcome_ready.connect(outcomes.append)

    controller.open_result(result_root)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: bool(outcomes),
        timeout=3000,
    )

    assert outcomes[-1].status is LoadStatus.CORRUPT
    assert widget.model is valid
    assert widget.status_label.text() == "CORRUPT: synthetic corruption"
    controller.shutdown()


def test_main_window_iqa_dock_preserves_native_authority_and_resets_geometry(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    result_root: Path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _compose_main_window_presentation(window)
    window.show()
    before = (
        dict(window.documents),
        tuple(window.selected_documents),
        window.current_document,
        window._active_document_id,
        window._difference_source_ids,
    )
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(result_root),
    )

    file_menu = next(
        action.menu()
        for action in window.menuBar().actions()
        if action.text().replace("&", "") == "File"
    )
    assert file_menu is not None
    iqa_action = window.action_map["Open IQA Result..."]
    assert iqa_action in file_menu.actions()
    iqa_action.trigger()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.iqa_workspace.model is not None,
        timeout=5000,
    )

    assert window.iqa_dock.isVisible()
    title_bar = window.iqa_dock.titleBarWidget()
    assert isinstance(title_bar, PlotsDockTitleBar)
    assert title_bar.title.text() == "IQA Results"
    after = (
        dict(window.documents),
        tuple(window.selected_documents),
        window.current_document,
        window._active_document_id,
        window._difference_source_ids,
    )
    assert after == before

    window.iqa_dock.setFloating(True)
    window.iqa_dock.show()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        window.iqa_dock.isFloating,
        timeout=2000,
    )
    window.iqa_dock.setGeometry(QRect(180, 140, 520, 360))
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.settings.contains(IQA_FLOATING_GEOMETRY_SETTING),
        timeout=2000,
    )
    qtbot.wait(50)  # type: ignore[attr-defined]
    window.reset_workspace_layout()
    assert not window.iqa_dock.isFloating()
    assert (
        window.dockWidgetArea(window.iqa_dock)
        == Qt.DockWidgetArea.RightDockWidgetArea
    )
    assert window.iqa_dock.isHidden()
    assert not window.settings.contains(IQA_FLOATING_GEOMETRY_SETTING)
    window.close()
