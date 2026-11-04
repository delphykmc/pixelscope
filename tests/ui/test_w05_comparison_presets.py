"""W05 composed command-bar and Difference safety regression tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pixelscope.app.bootstrap import compose_main_window_presentation
from pixelscope.app.main_window import MainWindow
from pixelscope.core.comparison_presets import ComparisonPair, ComparisonPreset
from pixelscope.core.image_document import ImageDocument
from pixelscope.ui.quick_compare import ComparisonPresetController

pytestmark = pytest.mark.usefixtures("isolated_qsettings")


def _window(qtbot: object) -> tuple[MainWindow, ComparisonPresetController]:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    compose_main_window_presentation(window)
    controller = window.quick_compare_controller.comparison_presets
    assert isinstance(controller, ComparisonPresetController)
    return window, controller


def _sources(window: MainWindow, root: Path, count: int) -> list[ImageDocument]:
    documents = [
        ImageDocument.from_array(
            np.full((48, 64), 20 + index, dtype=np.uint8),
            "same.png",
            source_path=root / str(index) / "same.png",
        )
        for index in range(count)
    ]
    for document in documents:
        window.add_document(document, select=False)
    window._select_document_ids([document.document_id for document in documents])
    return documents


@pytest.mark.parametrize("count", [2, 4, 6])
def test_original_presets_leave_files_selected_and_current_page_untouched(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, count)
    original_page = tuple(doc.document_id for doc in window.current_comparison_documents())
    selected = tuple(doc.document_id for doc in window.selected_documents)
    assert controller.pair == ComparisonPair(docs[0].document_id, docs[1].document_id)

    def no_calculate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("W05 preset must never calculate Difference")

    monkeypatch.setattr(window.difference_panel, "calculate_difference", no_calculate)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    assert controller.preset is ComparisonPreset.ORIGINAL_2
    assert [
        v.document.document_id
        for v in window.multi_compare_view.occupied_viewers
        if v.document is not None
    ] == [doc.document_id for doc in docs[:2]]
    if count >= 4:
        controller.set_preset(ComparisonPreset.ORIGINAL_4)
        assert [
            v.document.document_id
            for v in window.multi_compare_view.occupied_viewers
            if v.document is not None
        ] == [doc.document_id for doc in docs[:4]]
    else:
        controller.set_preset(ComparisonPreset.ORIGINAL_4)
        assert controller.preset is ComparisonPreset.ORIGINAL_2
    assert tuple(doc.document_id for doc in window.selected_documents) == selected
    assert tuple(doc.document_id for doc in window.current_comparison_documents()) == original_page
    controller.set_preset(ComparisonPreset.WORKSPACE)
    assert controller.preset is ComparisonPreset.WORKSPACE
    window.close()


def test_reference_remains_fixed_as_target_changes_in_original_four(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 4)
    controller.set_preset(ComparisonPreset.ORIGINAL_4)
    ref_id = docs[0].document_id

    def no_calculate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Target changes must not calculate Difference")

    monkeypatch.setattr(window.difference_panel, "calculate_difference", no_calculate)
    for target in docs[1:]:
        controller._change_pair(target_id=target.document_id)
        assert controller.pair == ComparisonPair(ref_id, target.document_id)
        pair = window.difference_panel.selected_documents()
        assert pair is not None
        assert (pair[0].document_id, pair[1].document_id) == (
            ref_id,
            target.document_id,
        )
        badges = {
            viewer.document.document_id: viewer.header.badge.text()
            for viewer in window.multi_compare_view.occupied_viewers
            if viewer.document is not None
        }
        assert badges[ref_id] == "A1"
        assert badges[target.document_id] == f"B{docs.index(target) + 1}"
    assert len(window.selected_documents) == 4
    window.close()


def test_diff_preset_does_not_display_missing_or_unrelated_map(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 2)

    def no_calculate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Switching presets cannot invoke Difference Calculate")

    monkeypatch.setattr(window.difference_panel, "calculate_difference", no_calculate)
    controller.set_preset(ComparisonPreset.AB_DIFF)
    assert controller.status_label.text() == "Not Calculated".title()
    assert all(
        viewer.document is not window._difference_document
        for viewer in window.multi_compare_view.occupied_viewers
    )
    controller.set_preset(ComparisonPreset.DIFF_FOCUS)
    assert window._difference_document is None
    assert controller.pair == ComparisonPair(docs[0].document_id, docs[1].document_id)
    window.close()


def test_cached_pair_can_be_displayed_only_after_identity_match(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 4)
    panel = window.difference_panel
    numerical = np.full((48, 64), 25, dtype=np.uint8)
    preview = numerical.copy()
    correct_key = panel._cache_key()
    assert correct_key is not None

    monkeypatch.setattr(panel, "has_cached_map", lambda: panel._cache_key() == correct_key)
    monkeypatch.setattr(
        panel,
        "cached_display_for_current",
        lambda: ("Cached Difference", numerical, preview)
        if panel._cache_key() == correct_key
        else None,
    )
    monkeypatch.setattr(
        panel,
        "calculate_difference",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("preset calculated Difference")
        ),
    )
    controller.set_preset(ComparisonPreset.AB_DIFF)
    assert controller.status_label.text() == "Cached"
    assert any(
        viewer.document is window._difference_document
        for viewer in window.multi_compare_view.occupied_viewers
    )
    # Different target: the previous cached map is never shown for C.
    controller._change_pair(target_id=docs[2].document_id)
    assert controller.status_label.text() == "Not Calculated".title()
    assert all(
        viewer.document is not window._difference_document
        for viewer in window.multi_compare_view.occupied_viewers
    )
    window.close()


def test_changed_page_generation_revokes_temporary_preset(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 6)
    controller.set_preset(ComparisonPreset.ORIGINAL_4)
    docs[0].generation += 1
    window._render_selection(preserve_view=True)
    assert controller.preset is ComparisonPreset.WORKSPACE
    window.close()


def test_closing_preset_controller_rejects_late_callbacks(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    _sources(window, tmp_path, 2)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    window.close()
    assert controller._closed
    controller.on_workspace_rendered()


def test_sync_off_allows_preset_without_mutating_selection(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    _sources(window, tmp_path, 4)
    page = tuple(doc.document_id for doc in window.current_comparison_documents())
    window.multi_compare_view.set_sync_enabled(False)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    assert controller.preset is ComparisonPreset.ORIGINAL_2
    assert tuple(doc.document_id for doc in window.selected_documents) == page
    assert window._difference_document is None
    window.multi_compare_view.set_sync_enabled(True)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    assert controller.preset is ComparisonPreset.ORIGINAL_2
    window.multi_compare_view.set_sync_enabled(False)
    controller.set_preset(ComparisonPreset.WORKSPACE)
    assert controller.preset is ComparisonPreset.WORKSPACE
    window.close()


def test_page_two_presets_bind_exact_runtime_documents(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 8)
    window.next_comparison_page()
    current = window.current_comparison_documents()
    assert tuple(doc.document_id for doc in current) == (
        docs[6].document_id,
        docs[7].document_id,
    )
    assert controller.pair == ComparisonPair(docs[6].document_id, docs[7].document_id)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    presented = [
        v.document for v in window.multi_compare_view.occupied_viewers if v.document is not None
    ]
    assert presented == current
    assert len(window.selected_documents) == 8
    window.close()


def _settled(qtbot: object, window: MainWindow) -> None:
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: not window.multi_compare_view._layout_refit_active
        and all(
            not v._geometry_timer.isActive() and v.measure_physical_zoom().valid
            for v in (
                [window.viewer]
                if window.central_stack.currentWidget() is window.viewer
                else window.multi_compare_view.occupied_viewers
            )
        ),
        timeout=5000,
    )


def _restore_finished(qtbot: object, window: MainWindow) -> None:
    qtbot.waitUntil(lambda: window._preset_view_state.status != "pending", timeout=5000)  # type: ignore[attr-defined]
    assert window._preset_view_state.status == "applied"


@pytest.mark.parametrize("count", [2, 4, 6])
def test_independent_physical_views_survive_hidden_presets(
    qtbot: object,
    tmp_path: Path,
    count: int,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, count)
    window.resize(1400, 880)
    window.show()
    _settled(qtbot, window)
    window.multi_compare_view.set_sync_enabled(False)
    expected = {}
    for i, viewer in enumerate(window.multi_compare_view.occupied_viewers):
        percent, center = 100.0 + i * 30, (20.0 + i, 18.0 + i)
        assert viewer.set_physical_zoom(percent, center).achieved
        expected[viewer.document.document_id] = (percent, center)
    for preset in (
        ComparisonPreset.ORIGINAL_2,
        ComparisonPreset.ORIGINAL_4 if count >= 4 else ComparisonPreset.ORIGINAL_2,
        ComparisonPreset.WORKSPACE,
    ):
        controller.set_preset(preset)
        _restore_finished(qtbot, window)
        for viewer in window.multi_compare_view.occupied_viewers:
            percent, center = expected[viewer.document.document_id]
            assert viewer.zoom_percent == pytest.approx(percent, rel=0.005)
            x, y = viewer.view_box.viewRange()
            assert ((x[0] + x[1]) / 2, (y[0] + y[1]) / 2) == pytest.approx(center)
    assert window._visible_document_ids == {d.document_id for d in docs}
    assert window._current_page_required_ids().issuperset(window._visible_document_ids)
    window.close()


def test_single_to_presets_publishes_capacity_active_and_preserves_view(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 4)
    window.set_layout_mode("Single View")
    window.resize(1400, 880)
    window.show()
    _settled(qtbot, window)
    assert window.viewer.set_physical_zoom(175, (24, 19)).achieved
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    _restore_finished(qtbot, window)
    assert window._view_capacity == 2
    assert window.central_stack.currentWidget() is window.multi_compare_view
    assert window._visible_document_ids == {d.document_id for d in docs[:2]}
    for viewer in window.multi_compare_view.occupied_viewers:
        assert viewer.zoom_percent == pytest.approx(175, rel=0.005)
        x, y = viewer.view_box.viewRange()
        assert ((x[0] + x[1]) / 2, (y[0] + y[1]) / 2) == pytest.approx((24, 19))
    window.next_image()
    assert window._active_document_id == docs[1].document_id
    window.next_image()
    assert window._active_document_id == docs[0].document_id
    window.cycle_primary_source()
    assert window._focus_document_id == docs[-1].document_id
    assert controller.pair == ComparisonPair(docs[0].document_id, docs[1].document_id)
    controller.set_preset(ComparisonPreset.WORKSPACE)
    _restore_finished(qtbot, window)
    assert window.central_stack.currentWidget() is window.viewer
    window.set_layout_mode("Multi View")
    assert controller.preset is ComparisonPreset.WORKSPACE
    window.close()


def test_real_difference_worker_focus_roi_and_permission(
    qtbot: object,
    tmp_path: Path,
) -> None:
    from pixelscope.core.roi import RoiBounds

    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 6)
    window.show()
    panel = window.difference_panel
    panel.calculate_difference()
    qtbot.waitUntil(
        lambda: panel._worker is None and panel._preview_worker is None and panel.has_cached_map(),
        timeout=10000,
    )  # type: ignore[attr-defined]
    for preset, count in ((ComparisonPreset.AB_DIFF, 3), (ComparisonPreset.DIFF_FOCUS, 1)):
        controller.set_preset(preset)
        assert window._view_capacity == (4 if count == 3 else 1)
        visible = (
            list(window.multi_compare_view.occupied_viewers) if count == 3 else [window.viewer]
        )
        assert len(visible) == count
        assert any(v.document is window._difference_document for v in visible)
        assert window._visible_document_ids == {v.document.document_id for v in visible}
        assert len(window.current_comparison_documents()) == 6
    window.show_selected_image(1)
    assert controller.preset is ComparisonPreset.WORKSPACE
    assert window.viewer.document is docs[1]
    controller.set_preset(ComparisonPreset.AB_DIFF)
    controller._change_pair(target_id=docs[2].document_id)
    assert panel.get_presented_difference_token() is None
    assert panel.get_current_difference_token() is None
    assert window._difference_document is None
    panel.set_active_roi(RoiBounds(1, 1, 8, 8))
    assert panel.get_current_difference_token() is None
    window.close()


def test_pending_view_restore_is_revoked_before_user_input_and_close(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    _sources(window, tmp_path, 4)
    window.show()
    _settled(qtbot, window)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    live = window._preset_view_state
    assert live.status == "pending"
    viewer = window.multi_compare_view.occupied_viewers[0]
    viewer.view_box.user_navigation_started.emit()
    assert live.status == "interrupted"
    viewer.set_physical_zoom(222, (23, 21))
    live._restore()
    assert viewer.zoom_percent == pytest.approx(222, rel=0.005)
    window.close()
    assert live._closed and not live.sources
    live._restore()


def test_large_selection_arrows_only_activate_presented_originals(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 8)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    for _ in range(5):
        window.next_image()
        assert window._active_document_id in {d.document_id for d in docs[:2]}
        assert window._current_index in (0, 1)
    for _ in range(5):
        window.previous_image()
        assert window._active_document_id in {d.document_id for d in docs[:2]}
    window.next_comparison_page()
    assert controller.preset is ComparisonPreset.WORKSPACE
    assert [d.document_id for d in window.current_comparison_documents()] == [
        d.document_id for d in docs[6:]
    ]
    window.close()


@pytest.mark.parametrize("family,channel", [("YUV420", "U"), ("BAYER", "R")])
def test_native_pair_presets_preserve_source_samples_and_pick(
    qtbot: object,
    tmp_path: Path,
    family: str,
    channel: str,
) -> None:
    from pixelscope.core.yuv import NativeYuvFrame
    from pixelscope.io.raw_profile import RawProfile

    window, controller = _window(qtbot)
    docs = []
    for i in range(2):
        if family == "YUV420":
            doc = ImageDocument.from_yuv(
                NativeYuvFrame(
                    y=np.full((48, 64), 40 + i, dtype=np.uint8),
                    u=np.full((24, 32), 90 + i, dtype=np.uint8),
                    v=np.full((24, 32), 160, dtype=np.uint8),
                    layout="YUV420",
                ),
                f"{i}.yuv",
            )
        else:
            profile = RawProfile(
                name="native",
                width=64,
                height=48,
                stride_bytes=128,
                storage_format="unpacked",
                container_dtype="uint16",
                endianness="little",
                bit_depth=12,
                bit_alignment="lsb",
                channel_layout="BAYER",
                bayer_pattern="RGGB",
                black_level=0,
                white_level=4095,
            )
            doc = ImageDocument.from_array(
                np.full((48, 64), 1024 + i, dtype=np.uint16),
                f"{i}.raw",
                channel_layout="BAYER",
                bit_depth=12,
                raw_profile=profile,
            )
        docs.append(doc)
        window.add_document(doc, select=False)
    window._select_document_ids([d.document_id for d in docs])
    original = [(id(d.source), d.generation, d.source.copy()) for d in docs]
    panel = window.difference_panel
    panel.channel.setCurrentText(channel)
    panel.calculate_difference()
    qtbot.waitUntil(
        lambda: panel.has_cached_map() and panel._worker is None and panel._preview_worker is None,
        timeout=10000,
    )  # type: ignore[attr-defined]
    controller.set_preset(ComparisonPreset.AB_DIFF)
    assert window._difference_document.reference_shape == docs[0].reference_shape
    viewer = next(v for v in window.multi_compare_view.occupied_viewers if v.document is docs[0])
    window.review_selection_controller._pick_requested(viewer, True)
    assert window.review_selection_controller.picked_ids == frozenset({docs[0].document_id})
    controller.set_preset(ComparisonPreset.DIFF_FOCUS)
    window.review_selection_controller._pick_requested(window.viewer, True)
    assert window.review_selection_controller.picked_ids == frozenset({docs[0].document_id})
    controller.set_preset(ComparisonPreset.WORKSPACE)
    for doc, (identity, generation, samples) in zip(docs, original, strict=False):
        assert id(doc.source) == identity and doc.generation == generation
        np.testing.assert_array_equal(doc.source, samples)
    window.close()


def test_runtime_view_restore_rolls_back_failed_second_tile(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    window, controller = _window(qtbot)
    _sources(window, tmp_path, 4)
    window.show()
    _settled(qtbot, window)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    _restore_finished(qtbot, window)
    live = window._preset_view_state
    window.multi_compare_view.set_sync_enabled(False)
    for i, viewer in enumerate(window.multi_compare_view.occupied_viewers):
        viewer.set_physical_zoom(300 + i * 30, (30 + i, 20 + i))
    before = [v.view_box.viewRange() for v in window.multi_compare_view.occupied_viewers]
    second = window.multi_compare_view.occupied_viewers[1]
    real_apply = second.set_physical_zoom

    def fail(percent: float, center: tuple[float, float]):
        return replace(real_apply(percent, center), achieved=False)

    monkeypatch.setattr(second, "set_physical_zoom", fail)
    live.request()
    qtbot.waitUntil(lambda: live.status != "pending", timeout=5000)  # type: ignore[attr-defined]
    assert live.status == "unavailable"
    for viewer, ranges in zip(window.multi_compare_view.occupied_viewers, before, strict=False):
        np.testing.assert_allclose(viewer.view_box.viewRange(), ranges)
    window.close()


@pytest.mark.parametrize("command", ["fit", "100", "plus"])
def test_single_explicit_zoom_revokes_pending_restore(
    qtbot: object,
    tmp_path: Path,
    command: str,
) -> None:
    window, controller = _window(qtbot)
    _sources(window, tmp_path, 2)
    window.set_layout_mode("Single View")
    window.show()
    _settled(qtbot, window)
    controller.set_preset(ComparisonPreset.ORIGINAL_2)
    _restore_finished(qtbot, window)
    controller.set_preset(ComparisonPreset.WORKSPACE)
    live = window._preset_view_state
    assert live.status == "pending"
    if command == "fit":
        window.fit_image()
    elif command == "100":
        window.zoom_100_percent()
    else:
        window.zoom_by(1.25)
    expected = window.viewer.view_box.viewRange()
    assert live.status == "interrupted"
    live._restore()
    np.testing.assert_allclose(window.viewer.view_box.viewRange(), expected)
    window.close()


def test_preset_difference_primary_is_actionable_and_t_remains_source_only(
    qtbot: object,
    tmp_path: Path,
) -> None:
    window, controller = _window(qtbot)
    docs = _sources(window, tmp_path, 4)
    panel = window.difference_panel
    panel.calculate_difference()
    qtbot.waitUntil(
        lambda: panel.has_cached_map() and panel._worker is None and panel._preview_worker is None,
        timeout=10000,
    )  # type: ignore[attr-defined]
    controller.set_preset(ComparisonPreset.AB_DIFF)
    difference = window._difference_document
    assert difference is not None
    window._set_focus_document(difference)
    assert window._focus_document_id == difference.document_id
    assert window._active_document_id == difference.document_id
    pair = controller.pair
    window.cycle_primary_source()
    assert window._focus_document_id in {d.document_id for d in docs}
    assert controller.pair == pair
    window.close()
