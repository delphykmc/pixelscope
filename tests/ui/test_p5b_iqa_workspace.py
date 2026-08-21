from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import QFileDialog, QLabel

from pixelscope.app.application import _compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.remote.iqa_domain import ComparisonMode, LoadStatus, ResultLoadOutcome
from pixelscope.remote.iqa_fixture import write_golden_result
from pixelscope.remote.iqa_reader import load_result
from pixelscope.ui.iqa_workspace import (
    IQA_FLOATING_GEOMETRY_SETTING,
    IqaWorkspaceController,
    IqaWorkspaceWidget,
)
from pixelscope.ui.plots_dock_title import PlotsDockTitleBar
from pixelscope.workers.task_worker import TaskWorker


class _HoldingPool:
    def __init__(self) -> None:
        self.workers: list[TaskWorker] = []

    def start(self, worker: TaskWorker) -> None:
        self.workers.append(worker)


def _loaded(root: Path):  # type annotation would obscure assertion narrowing
    outcome = load_result(root)
    assert outcome.status is LoadStatus.SUCCESS
    assert outcome.result is not None
    return outcome.result


def _has_four_decimals(text: str) -> bool:
    if text == "—":
        return False
    _, dot, fraction = text.partition(".")
    return dot == "." and len(fraction) == 4


@pytest.fixture()
def result_root(tmp_path: Path) -> Path:
    return write_golden_result(tmp_path / "golden")


def test_workspace_keeps_overview_navigation_local_and_formats_four_decimals(
    qtbot: object, result_root: Path
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    requested: list[str] = []
    widget.scene_requested.connect(requested.append)

    assert widget.set_result(_loaded(result_root)).status is LoadStatus.SUCCESS

    assert "golden-p5a-v1" in widget.result_label.text()
    assert "11 Scenes" in widget.dataset_label.text()
    assert widget.reference_index == 1
    assert widget.hierarchy.topLevelItemCount() == 10
    assert widget.hierarchy.header().sectionSize(0) <= 220
    assert "A vs B" in widget.hierarchy.headerItem().text(1)
    legend = widget.overview_plot.plotItem.legend
    assert legend is not None
    assert len(legend.items) == 1
    assert widget._overview_hover_texts
    assert "A vs B" in widget._overview_hover_texts[0]

    attribute = widget.hierarchy.topLevelItem(2)
    assert attribute.childCount() == 11
    assert _has_four_decimals(attribute.text(1))
    assert attribute.text(2) == ""
    scene = attribute.child(3)
    published_value = scene.text(1)
    assert _has_four_decimals(published_value)
    assert scene.text(2) == ""

    widget.hierarchy.setCurrentItem(scene)

    assert widget.selected_attribute_id == "chroma_noise"
    assert widget.selected_scene_id is None
    assert requested == []
    assert widget.pages.currentWidget() is widget.overview_page
    assert widget.preview_layout.count() == 0

    widget.reference_combo.setCurrentIndex(widget.reference_combo.findData(0))
    assert widget.reference_index == 0
    assert widget.mode_combo.isEnabled()
    attribute = widget.hierarchy.topLevelItem(2)
    scene = attribute.child(3)
    assert _has_four_decimals(scene.text(1))
    assert scene.text(1) != published_value
    assert "B vs A" in widget.hierarchy.headerItem().text(1)

    widget.mode_combo.setCurrentIndex(
        widget.mode_combo.findData(ComparisonMode.MEAN_OF_GRID_LOG_RATIOS.value)
    )
    assert widget.aggregation_mode is ComparisonMode.MEAN_OF_GRID_LOG_RATIOS
    assert widget.selected_attribute_id == "chroma_noise"


def test_scene_trend_defaults_to_all_attributes_filters_and_selects_source_metadata(
    qtbot: object, result_root: Path
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    requested: list[str] = []
    widget.scene_requested.connect(requested.append)
    assert widget.set_result(_loaded(result_root)).status is LoadStatus.SUCCESS

    assert len(widget.enabled_attribute_ids) == 10
    assert "10 / 10 attributes" in widget.trend_label.text()
    assert widget.scene_splitter.count() == 2
    assert widget.overview_splitter.count() == 2
    assert widget._hover_scene_line is not None
    assert len(widget._scene_hover_texts) == 11
    assert "Luma noise" in widget._scene_hover_texts[0]

    first = widget.attribute_filter.item(0)
    assert not first.icon().isNull()
    assert first.flags() & Qt.ItemFlag.ItemIsUserCheckable
    first.setCheckState(Qt.CheckState.Unchecked)
    assert len(widget.enabled_attribute_ids) == 9
    assert "9 / 10 attributes" in widget.trend_label.text()

    widget._select_scene_index(3)
    assert widget.selected_scene_id == "scene_000003"
    assert requested[-1] == "scene_000003"
    assert widget.preview_layout.count() == 2
    assert "source identities" in widget.preview_caption.text()
    first_card = widget.preview_layout.itemAt(0).widget()
    assert first_card is not None
    card_text = "\n".join(label.text() for label in first_card.findChildren(QLabel))
    assert "Published relative path" in card_text
    assert "P5-D Inspect Pair" in card_text


def test_workspace_marks_only_robust_outlier_rows_in_bold(
    qtbot: object, result_root: Path
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    assert widget.set_result(_loaded(result_root)).status is LoadStatus.SUCCESS

    luma_detail = widget.hierarchy.topLevelItem(1)
    bold_scenes = [
        luma_detail.child(index).text(0)
        for index in range(luma_detail.childCount())
        if luma_detail.child(index).font(0).bold()
    ]

    assert "scene_000007" in bold_scenes
    assert len(bold_scenes) < luma_detail.childCount()


@pytest.mark.parametrize(
    ("status", "reason"),
    (
        (LoadStatus.INVALID, "publication_state is not complete"),
        (LoadStatus.CORRUPT, "missing summary artifact"),
        (LoadStatus.UNSUPPORTED, "unsupported result schema_version 2"),
    ),
)
def test_controller_reports_open_outcomes_without_replacing_last_valid_result(
    qtbot: object,
    result_root: Path,
    status: LoadStatus,
    reason: str,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    valid = _loaded(result_root)
    widget.set_result(valid)
    outcomes: list[ResultLoadOutcome] = []
    pool = QThreadPool(widget)
    controller = IqaWorkspaceController(
        widget,
        loader=lambda _root: ResultLoadOutcome(status, reason=reason),
        pool=pool,
    )
    controller.outcome_ready.connect(outcomes.append)

    controller.open_result(result_root)
    qtbot.waitUntil(lambda: bool(outcomes), timeout=3000)  # type: ignore[attr-defined]

    assert outcomes[-1].status is status
    assert widget.result is valid
    assert widget.status_label.text() == f"{status.value.upper()}: {reason}"
    controller.shutdown()
    assert pool.waitForDone(3000)


def test_controller_ignores_stale_and_post_shutdown_callbacks(
    qtbot: object, result_root: Path
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    pool = _HoldingPool()
    controller = IqaWorkspaceController(widget, pool=pool)  # type: ignore[arg-type]
    outcome = ResultLoadOutcome(LoadStatus.SUCCESS, result=_loaded(result_root))

    first = controller.open_result(result_root)
    second = controller.open_result(result_root)
    controller._result_loaded("stale", None, first, outcome)
    assert widget.result is None
    controller._result_loaded("current", None, second, outcome)
    assert widget.result is outcome.result
    controller.shutdown()
    controller._result_loaded("after-close", None, second + 1, outcome)
    assert widget.result is outcome.result


def test_missing_canonical_pair_is_an_explicit_unsupported_open_outcome(
    qtbot: object, result_root: Path
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    valid = _loaded(result_root)
    assert widget.set_result(valid).status is LoadStatus.SUCCESS
    scene = valid.scenes[-1]
    attribute_id = valid.attributes[0].attribute_id
    malformed = replace(
        valid,
        scenes=(
            replace(
                scene,
                comparisons=tuple(
                    item
                    for item in scene.comparisons
                    if not (
                        item.attribute_id == attribute_id
                        and item.source_a_id == scene.sources[0].source_id
                        and item.source_b_id == scene.sources[1].source_id
                    )
                ),
            ),
        ),
    )
    direct = widget.set_result(malformed)
    assert direct.status is LoadStatus.UNSUPPORTED
    assert widget.result is valid
    outcomes: list[ResultLoadOutcome] = []
    pool = QThreadPool(widget)
    controller = IqaWorkspaceController(
        widget,
        loader=lambda _root: ResultLoadOutcome(LoadStatus.SUCCESS, result=malformed),
        pool=pool,
    )
    controller.outcome_ready.connect(outcomes.append)

    controller.open_result(result_root)
    qtbot.waitUntil(lambda: bool(outcomes), timeout=3000)  # type: ignore[attr-defined]

    assert outcomes[-1].status is LoadStatus.UNSUPPORTED
    assert "ordered" in (outcomes[-1].reason or "")
    assert widget.result is valid
    assert widget.status_label.text().startswith("UNSUPPORTED:")
    controller.shutdown()
    assert pool.waitForDone(3000)


def test_late_presentation_failure_restores_previous_visible_result(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
    result_root: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    valid = _loaded(result_root)
    assert widget.set_result(valid).status is LoadStatus.SUCCESS
    before_result_label = widget.result_label.text()
    before_scene_value = widget.hierarchy.topLevelItem(0).child(0).text(1)
    candidate = replace(valid, result_id="candidate-result")

    original_populate_scene_trend = widget._populate_scene_trend
    calls = 0

    def fail_once_after_mutation() -> None:
        nonlocal calls
        calls += 1
        original_populate_scene_trend()
        if calls == 1:
            raise RuntimeError("injected late presentation failure")

    monkeypatch.setattr(widget, "_populate_scene_trend", fail_once_after_mutation)

    outcome = widget.set_result(candidate)

    assert outcome.status is LoadStatus.CORRUPT
    assert outcome.reason == "unable to present IQA result: injected late presentation failure"
    assert widget.result is valid
    assert widget.result_label.text() == before_result_label
    assert widget.hierarchy.topLevelItem(0).child(0).text(1) == before_scene_value
    assert widget.attribute_filter.count() == len(valid.attributes)
    assert calls == 2


def test_main_window_iqa_dock_uses_plots_title_controls_and_preserves_native_authority(
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
    assert iqa_action.isVisible()
    iqa_action.trigger()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.iqa_workspace.result is not None, timeout=5000
    )

    assert window.iqa_dock.isVisible()
    assert window.iqa_workspace.result is not None
    title_bar = window.iqa_dock.titleBarWidget()
    assert isinstance(title_bar, PlotsDockTitleBar)
    assert title_bar.title.text() == "IQA Results"
    assert title_bar.float_button.toolTip() == "Float IQA Results"
    assert title_bar.maximize_button.toolTip() == "Maximize IQA Results"
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
    qtbot.waitUntil(window.iqa_dock.isFloating, timeout=2000)  # type: ignore[attr-defined]
    window.iqa_dock.resize(520, 360)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: window.settings.contains(IQA_FLOATING_GEOMETRY_SETTING),
        timeout=2000,
    )
    window.reset_workspace_layout()
    assert not window.iqa_dock.isFloating()
    assert window.dockWidgetArea(window.iqa_dock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert window.iqa_dock.isHidden()
    assert not window.settings.contains(IQA_FLOATING_GEOMETRY_SETTING)
    window.close()

    recreated = MainWindow()
    qtbot.addWidget(recreated)  # type: ignore[attr-defined]
    _compose_main_window_presentation(recreated)
    assert recreated.iqa_workspace.result is None
    assert recreated.documents == {}
    recreated.close()
