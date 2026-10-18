"""Test-owned follow-up diagnostics; no production hooks or rendering changes."""

from __future__ import annotations

import time


def e2_intervals(marks: dict) -> dict:
    pairs = {
        "F_barrier_wait": ("F_barrier_enter", "F_barrier_release"),
        "F_release_to_discovery_start": ("F_barrier_release", "F_discovery_start"),
        "F_discovery_work": ("F_discovery_start", "F_discovery_return"),
        "F_worker_to_first_GUI_row": ("F_discovery_return", "F_first_row_inserted"),
        "F_GUI_row_span": ("F_first_row_inserted", "F_last_row_inserted"),
        "F_last_row_to_commit": ("F_last_row_inserted", "F_registration_finished"),
        "F_GUI_handoff_to_commit": ("F_discovery_return", "F_registration_finished"),
        "F_commit_to_A_dispatch": ("F_registration_finished", "A_discovery_start"),
    }
    result = {}
    for name, (start, end) in pairs.items():
        assert marks[end] >= marks[start], name
        result[name] = (marks[end] - marks[start]) / 1e6
    return result


def desktop_metadata(app, window) -> dict:
    handle = window.windowHandle()
    screen = handle.screen() if handle else None
    geometry = screen.geometry() if screen else None
    return {
        "qt_platform": app.platformName(),
        "window_visible": window.isVisible(),
        "window_exposed": bool(handle and handle.isExposed()),
        "window_minimized": window.isMinimized(),
        "screen_geometry": [geometry.width(), geometry.height()] if geometry else None,
        "device_pixel_ratio": window.devicePixelRatioF(),
        "proof_required": "external desktop screenshot; windows QPA alone does not establish G2",
    }


def fourk_lane(window, app, wait, case: str, marks: dict, metrics: dict, probe, begin) -> list[str]:
    import numpy as np

    from pixelscope.core.image_document import ImageDocument

    _, lane, diff_state = case.split("_")
    documents = [
        ImageDocument.from_array(np.full((2160, 3840, 3), value, dtype=np.uint8), name)
        for name, value in (("A-UHD", 17), ("B-UHD", 93))
    ]
    for document in documents:
        window.add_document(document, select=False)
    ids = [d.document_id for d in documents]
    window._select_document_ids(ids)
    window.set_layout_mode("Multi View")
    panel = window.comparison_analysis_panel
    diff = window.difference_panel

    def idle():
        return (
            panel._worker is None
            and not panel._refresh_timer.isActive()
            and diff._worker is None
            and diff._preview_worker is None
            and not window._workers
        )

    wait(lambda: bool(panel.last_results) and idle())
    diff.calculate_difference()
    wait(lambda: window._difference_document is not None and idle())
    cached = diff.cached_display_for_current()
    assert cached is not None
    difference = window._difference_document
    difference_source = difference.source
    difference_values = difference.source.copy()
    source_ids = [(id(d.source), id(d.preview), d.generation) for d in documents]
    load_tokens = window._load_tokens.copy()
    probe()
    counts = {"dataChanged": 0, "selectionChanged": 0}
    deltas = {}

    def data_changed(*_args):
        counts["dataChanged"] += 1

    def selection_changed(*_args):
        counts["selectionChanged"] += 1

    if lane == "L2":
        window.document_list.model().dataChanged.connect(data_changed)
        window.document_list.selectionModel().selectionChanged.connect(selection_changed)

    def timed(name, callback):
        before_counts = counts.copy()
        start = time.perf_counter_ns()
        callback()
        returned = time.perf_counter_ns()
        metrics[name + "_sync"] = (returned - start) / 1e6
        after_counts = counts.copy()
        app.processEvents()
        event_return = time.perf_counter_ns()
        metrics[name + "_next_processEvents"] = (event_return - returned) / 1e6
        wait(idle)
        metrics[name + "_idle_observation"] = (time.perf_counter_ns() - returned) / 1e6
        if lane == "L2":
            deltas[name] = {
                "synchronous": {k: after_counts[k] - before_counts[k] for k in counts},
                "subsequent_events": {k: counts[k] - after_counts[k] for k in counts},
            }

    # Cache computation and initial state setup are deliberately untimed.
    window.diff_action.setChecked(diff_state == "OFF")
    wait(idle)
    app.processEvents()
    begin()
    timed(
        "diff_toggle_" + diff_state.lower(),
        lambda: window.diff_action.setChecked(diff_state == "ON"),
    )
    assert window.diff_action.isChecked() == (diff_state == "ON")
    window._set_focus_document(ids[0])
    wait(idle)
    app.processEvents()

    def bindings():
        return [
            {
                "physical_viewer": id(v),
                "document_id": v.document.document_id,
                "view_range": v.view_box.viewRange(),
            }
            for v in window.multi_compare_view.occupied_viewers
            if v.document is not None
        ]

    before_binding = bindings()
    timed("primary_A_to_B", lambda: window._set_focus_document(ids[1]))
    assert window._focus_document_id == ids[1]
    assert window.multi_compare_view.occupied_viewers[0].document is documents[1]
    after_binding = bindings()
    timed("primary_B_to_A", lambda: window._set_focus_document(ids[0]))
    assert window._focus_document_id == ids[0]
    assert window.multi_compare_view.occupied_viewers[0].document is documents[0]
    timed("files_only_state_update", lambda: window._update_file_states(documents, documents[0]))
    marks["measurement_end_ns"] = time.perf_counter_ns()
    assert [d.document_id for d in window.selected_documents] == ids
    assert window._load_tokens == load_tokens and not window._workers
    assert window._load_pool.activeThreadCount() == 0
    assert diff.cached_display_for_current() is not None
    assert window._difference_document.source is difference_source
    assert np.array_equal(window._difference_document.source, difference_values)
    assert window.diff_action.isChecked() == (diff_state == "ON")
    expected_count = 3 if diff_state == "ON" else 2
    assert len(window.multi_compare_view.occupied_viewers) == expected_count
    actual_ids = {v.document.document_id for v in window.multi_compare_view.occupied_viewers}
    assert actual_ids == set(
        ids + ([window._difference_document.document_id] if diff_state == "ON" else [])
    )
    assert window._difference_document.display_name
    for d, identity, value in zip(documents, source_ids, (17, 93), strict=True):
        assert (id(d.source), id(d.preview), d.generation) == identity
        assert np.all(d.source == value) and np.all(d.preview == value)
    marks["per_action_proxy_counts"] = deltas
    marks["bindings_before_primary"] = before_binding
    marks["bindings_after_primary"] = after_binding
    marks["attribution_limit"] = (
        "Snapshots outside timers show effective reuse/range only; no timed viewer/rebind/fit "
        "or aux/Diff attribution. processEvents return/idle is not completed physical paint."
    )
    return [
        "two_UHD_exact",
        "resident_no_load_dispatch",
        "same_selected_order",
        "correct_primary",
        "diff_cache_pixels_and_visibility",
        "source_identity_unchanged",
    ]
