from __future__ import annotations

from pathlib import Path

import pyqtgraph as pg
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from pixelscope.remote.iqa_domain import (
    AttributeSpec,
    ComparisonOperator,
    GridGeometry,
    LoadStatus,
    QualityDirection,
    ScalarStatistic,
    SceneGeometry,
    Source,
    ValueKind,
)
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_v2_domain import (
    DatasetSummaryV2,
    MeasurementContextProvenance,
    MeasurementSummary,
    ResultV2,
    SceneV2,
    SourceMeasurementV2,
    Variant,
)
from pixelscope.ui.iqa_workspace import IqaWorkspaceWidget, _scene_ticks

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _summary(value: float) -> MeasurementSummary:
    return MeasurementSummary(
        weight_sum=1.0,
        weighted_sum=value,
        weighted_square_sum=value * value,
        valid_count=1,
        valid=True,
        weighted_mean=value,
        weighted_std=0.0,
    )


def _synthetic_model(
    root: Path,
    *,
    attribute_count: int,
    variant_count: int,
    scene_count: int,
) -> IqaExplorerModel:
    attributes = tuple(
        AttributeSpec(
            attribute_id=f"attribute_{index:03d}",
            name=f"Attribute {index:02d}",
            value_kind=ValueKind.POWER,
            comparison_operator=ComparisonOperator.POWER_RATIO_TARGET_OVER_REFERENCE_DB,
            quality_direction=QualityDirection.HIGHER_IS_BETTER,
            unit="linear-power",
            stabilization_epsilon=1e-9,
            weighting_provenance="synthetic-unit-weight",
        )
        for index in range(attribute_count)
    )
    variants = tuple(
        Variant(f"variant_{index:03d}", f"Variant {index:02d}") for index in range(variant_count)
    )
    geometry = SceneGeometry(
        analysis_width=64,
        analysis_height=64,
        source_to_analysis=(
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        valid_rect=(0.0, 0.0, 64.0, 64.0),
    )
    grid = GridGeometry(
        rows=1,
        columns=1,
        block_width=64.0,
        block_height=64.0,
        origin_x=0.0,
        origin_y=0.0,
        discarded_right=0.0,
        discarded_bottom=0.0,
    )
    grids = {attribute.attribute_id: grid for attribute in attributes}
    provenance = MeasurementContextProvenance(
        representative_id="synthetic-representative",
        preprocessing_id="synthetic-preprocessing",
        model_id="synthetic-model",
        weighting_id="synthetic-weighting",
        geometry_id="synthetic-geometry",
    )
    scenes: list[SceneV2] = []
    dataset_values: dict[tuple[str, str], list[float]] = {
        (variant.variant_id, attribute.attribute_id): []
        for variant in variants
        for attribute in attributes
    }
    for scene_index in range(scene_count):
        scene_id = f"scene_{scene_index:04d}"
        measurements: list[SourceMeasurementV2] = []
        for variant_index, variant in enumerate(variants):
            summaries: dict[str, MeasurementSummary] = {}
            for attribute_index, attribute in enumerate(attributes):
                value = float(attribute_index + 1) + 0.1 * variant_index
                value += 0.001 * scene_index
                summaries[attribute.attribute_id] = _summary(value)
                dataset_values[(variant.variant_id, attribute.attribute_id)].append(value)
            measurements.append(
                SourceMeasurementV2(
                    variant_id=variant.variant_id,
                    source=Source(
                        source_id=f"source_{scene_index:04d}_{variant_index:03d}",
                        relative_path=(f"dataset/{variant.variant_id}/{scene_index:04d}.png"),
                        sha256=f"{scene_index * variant_count + variant_index:064x}",
                        width=64,
                        height=64,
                    ),
                    geometry=geometry,
                    grids=grids,
                    summaries=summaries,
                )
            )
        scenes.append(
            SceneV2(
                scene_id=scene_id,
                measurement_context_id=f"mc2:{scene_index:064x}",
                context_provenance=provenance,
                sources=tuple(measurements),
                grid_artifact=f"scenes/{scene_id}.npz",
                grid_uncompressed_size=1,
                detail_artifacts=(),
            )
        )
    dataset_summaries = {}
    for key, values in dataset_values.items():
        mean = sum(values) / len(values)
        dataset_summaries[key] = DatasetSummaryV2(
            pooled=_summary(mean),
            scene_mean=ScalarStatistic(mean, True),
            scene_std=ScalarStatistic(0.0, True),
            scene_count=len(values),
        )
    result = ResultV2(
        root=root,
        result_id=f"synthetic-{attribute_count}-{variant_count}-{scene_count}",
        schema_version=2,
        variants=variants,
        attributes=attributes,
        scenes=tuple(scenes),
        dataset_summaries=dataset_summaries,
        summary_artifact="summary.npz",
    )
    return IqaExplorerModel(result)


def _curve_count(widget: IqaWorkspaceWidget) -> int:
    return sum(isinstance(item, pg.PlotDataItem) for item in widget.scene_trend_plot.plotItem.items)


def _assert_label_metadata(label: QLabel) -> None:
    text = label.text()
    assert label.toolTip() == text
    assert label.accessibleName() == text


@pytest.mark.parametrize(
    ("attribute_count", "variant_count", "scene_count"),
    ((2, 2, 3), (10, 2, 12)),
)
def test_small_and_normal_results_keep_all_initial_series_and_selected_detail(
    qtbot: object,
    tmp_path: Path,
    attribute_count: int,
    variant_count: int,
    scene_count: int,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    model = _synthetic_model(
        tmp_path,
        attribute_count=attribute_count,
        variant_count=variant_count,
        scene_count=scene_count,
    )

    assert widget.set_model(model).status is LoadStatus.SUCCESS

    assert len(widget.enabled_attribute_ids) == attribute_count
    assert _curve_count(widget) == attribute_count * variant_count
    assert len(widget.scene_variant_legend.items) == variant_count
    assert len(widget._scene_hover_texts) == scene_count
    assert all(
        len(hover_text.splitlines()) == 1 + attribute_count * variant_count
        for hover_text in widget._scene_hover_texts
    )
    first = widget.hierarchy.topLevelItem(0)
    assert first is not None
    assert first.childCount() == scene_count
    if attribute_count > 1:
        second = widget.hierarchy.topLevelItem(1)
        assert second is not None
        assert second.childCount() == 0


def test_dynamic_iqa_labels_synchronize_metadata_across_real_transitions(
    qtbot: object,
    tmp_path: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    model = _synthetic_model(
        tmp_path,
        attribute_count=2,
        variant_count=2,
        scene_count=3,
    )
    dynamic_labels = (
        widget.status_label,
        widget.result_label,
        widget.dataset_label,
        widget.overview_detail_heading,
        widget.trend_label,
        widget.series_hint,
        widget.preview_caption,
    )
    for label in dynamic_labels:
        _assert_label_metadata(label)

    opening_root = tmp_path / "a_result_with_a_long_descriptive_name"
    widget.show_loading(opening_root)
    assert widget.status_label.text() == f"Opening {opening_root.name}..."
    _assert_label_metadata(widget.status_label)

    assert widget.set_model(model).status is LoadStatus.SUCCESS
    for label in dynamic_labels:
        _assert_label_metadata(label)

    widget.reference_combo.setCurrentIndex(1)
    assert widget.status_label.text() == "Loading Scene grids for Reference Variant 00..."
    _assert_label_metadata(widget.status_label)
    widget.show_relative_error(LoadStatus.CORRUPT, "reference grid unavailable")
    assert widget.status_label.text() == "CORRUPT: reference grid unavailable"
    _assert_label_metadata(widget.status_label)

    widget.attribute_filter.item(0).setCheckState(Qt.CheckState.Unchecked)
    assert "1 / 2 attributes" in widget.trend_label.text()
    assert "check Attributes to show more" in widget.series_hint.text()
    _assert_label_metadata(widget.trend_label)
    _assert_label_metadata(widget.series_hint)

    widget._select_scene_index(2)
    assert widget.preview_caption.text().startswith("scene_0002 · published source identities")
    _assert_label_metadata(widget.preview_caption)
    preview_labels = widget.preview_container.findChildren(QLabel)
    assert len(preview_labels) == 12
    for label in preview_labels:
        _assert_label_metadata(label)

    widget.show_open_error(LoadStatus.UNSUPPORTED, "future schema")
    assert widget.status_label.text() == "UNSUPPORTED: future schema"
    _assert_label_metadata(widget.status_label)


def test_stress_result_bounds_initial_curves_hover_ticks_and_lazy_scene_rows(
    qtbot: object,
    tmp_path: Path,
) -> None:
    widget = IqaWorkspaceWidget()
    qtbot.addWidget(widget)  # type: ignore[attr-defined]
    model = _synthetic_model(
        tmp_path,
        attribute_count=32,
        variant_count=16,
        scene_count=128,
    )

    assert widget.set_model(model).status is LoadStatus.SUCCESS

    assert widget.hierarchy.topLevelItemCount() == 32
    assert len(widget.enabled_attribute_ids) == 2
    assert _curve_count(widget) == 32
    assert len(widget.scene_variant_legend.items) == 16
    assert (
        len({sample.item.opts["symbol"] for sample, _label in widget.scene_variant_legend.items})
        == 16
    )
    assert [label.text for _sample, label in widget.scene_variant_legend.items] == [
        f"Variant {index:02d}" for index in range(16)
    ]
    assert "32 visible series" in widget.trend_label.text()
    assert "check Attributes to show more" in widget.series_hint.text()
    assert len(widget._scene_hover_texts) == 128
    assert all(len(text.splitlines()) == 33 for text in widget._scene_hover_texts)
    assert "Attribute 02" not in widget._scene_hover_texts[0]
    ticks = _scene_ticks(model.scene_ids)
    assert len(ticks) == 12
    assert ticks[0] == (0.0, "scene_0000")
    assert ticks[-1] == (127.0, "scene_0127")

    first = widget.hierarchy.topLevelItem(0)
    second = widget.hierarchy.topLevelItem(1)
    third = widget.hierarchy.topLevelItem(2)
    assert first is not None and second is not None and third is not None
    assert first.childCount() == 128
    assert second.childCount() == 0
    assert third.childCount() == 0
    assert sum(widget.hierarchy.topLevelItem(index).childCount() for index in range(32)) == 128

    second.setExpanded(True)
    assert second.childCount() == 128
    assert second.child(0).data(0, Qt.ItemDataRole.UserRole) == (
        "attribute_001",
        "scene_0000",
    )
    widget.hierarchy.setCurrentItem(third)
    assert widget.selected_attribute_id == "attribute_002"
    assert third.childCount() == 128
    assert sum(widget.hierarchy.topLevelItem(index).childCount() for index in range(32)) == 384

    widget.attribute_filter.item(2).setCheckState(Qt.CheckState.Checked)
    assert len(widget.enabled_attribute_ids) == 3
    assert _curve_count(widget) == 48
    assert all(len(text.splitlines()) == 49 for text in widget._scene_hover_texts)
    assert "Attribute 02" in widget._scene_hover_texts[0]

    widget._select_scene_index(127)
    assert widget.selected_scene_id == "scene_0127"
