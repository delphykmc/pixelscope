"""Allowlisted scalar export for the bounded R1-R3 study; no image or address payloads."""

from __future__ import annotations

import re

from scripts.issue190_user_path import stage_metrics

INTENTS = {
    "A_first",
    "A_reopen_warm_control",
    "B_add",
    "Diff_explicit_on",
    "Primary_A",
    "Primary_B",
}
CASES = {"R1_Open", "R1_Drop", "R23_OFF", "R23_ON"}
STAGES = set(
    """
action_handler_return canonical_preview_ready channel_layout_converted diff_cache_ready
diff_calculate_queued diff_calculate_return diff_calculate_start
diff_render_preview_queued diff_render_preview_return diff_render_preview_start
discovery_return discovery_start discovery_worker_completed encoded_bytes_read
encoded_file_read_begin encoded_sha256_calculated files_state_begin files_state_return
first_viewport_paint_event_processed foreground_load_worker_queued
foreground_load_worker_submit_begin gui_event_loop_next_turn image_item_upload_returned
image_load_worker_callable_entered intent_accepted legacy_first_frame_signal load_queued
load_result_signal load_worker_result_received load_worker_return load_worker_start
opencv_decode_completed primary_range_check ready_render_selection_begin
ready_render_selection_returned ready_snapshot recent_entries_stage_begin
recent_entries_stage_returned recent_entries_staged
recent_entries_submitted_to_qsettings_after_paint render_begin render_ready_analysis_bound
render_ready_diff_panel_bound render_ready_viewer_bound render_return row_registered
selection_returned selection_start source_gui_enter source_gui_return_accepted
viewport_paint_event_entered
""".split()
)
CHECKS = {
    "Open_replacement",
    "same_file_reopen_new_token",
    "exact_RGB_source_and_preview",
    "encoded_digest",
    "current_generation_tokens",
    "normal_GC",
    "no_stale_publish",
    "Drop_additive_A_B",
    "passive_Diff_default_hidden",
    "first_Diff_cache_miss",
    "Primary_A_B_A",
    "ROI_preserved",
    "correct_Primary_header",
    "pan_preserved",
    "first_uncached_Diff_exact_widened_math",
}
EVENT_FIELDS = {
    "selection_epoch",
    "load_token",
    "generation",
    "token_valid",
    "map_reused",
    "axis",
    "before_low",
    "before_high",
    "after_low",
    "after_high",
}


def export_sample(sample: dict) -> dict:
    case = sample.get("case_id")
    if case not in CASES:
        raise ValueError("unknown case")
    result = {"case_id": case, "warmup": bool(sample.get("warmup", False))}
    run_id = sample.get("run_id", "")
    if re.fullmatch(r"(?:R1_Open|R1_Drop|R23_OFF|R23_ON)-\d{2}", run_id):
        result["run_id"] = run_id
    for key, values in (
        ("status", {"fail", "inconclusive"}),
        ("correctness", {"pass", "fail"}),
        ("error_type", {"TimeoutError", "AssertionError", "watchdog_timeout"}),
    ):
        if sample.get(key) in values:
            result[key] = sample[key]
    result["checks"] = [check for check in sample.get("checks", []) if check in CHECKS]
    events = []
    revisions = {}
    origin = min((e["ns"] for e in sample.get("events", [])), default=0)
    for event in sample.get("events", []):
        if event.get("intent_id") not in INTENTS:
            continue
        stage = event.get("stage", "")
        if stage not in STAGES:
            continue
        safe = {"stage": stage, "ns": event["ns"] - origin, "intent_id": event["intent_id"]}
        for key in EVENT_FIELDS:
            value = event.get(key)
            if type(value) in (int, float, bool):
                safe[key] = value
        if event.get("source") in {"A", "B", "Diff", "pair", "unknown"}:
            safe["source"] = event["source"]
        if "preview_revision" in event:
            raw = event["preview_revision"]
            revisions.setdefault(raw, len(revisions) + 1)
            safe["preview_revision"] = revisions[raw]
        if event.get("pair") in {"A/B", "B/A"}:
            safe["pair"] = event["pair"]
        if event.get("physical_viewer") == "not_attributed":
            safe["physical_viewer"] = "not_attributed"
        events.append(safe)
    result["events"] = events
    result["metrics_ms"] = stage_metrics(events)
    result["trace_dropped"] = int(sample.get("trace_dropped", 0))
    result["range_failures"] = [
        {"primary": row["primary"], "source": row["source"]}
        for row in sample.get("range_failures", [])
        if row.get("primary") in {"A", "B"} and row.get("source") in {"A", "B", "Diff"}
    ]
    result["normal_gc"] = sample.get("normal_gc") is True
    result["system"] = {
        key: value
        for key, value in sample.get("system", {}).items()
        if key in {"heartbeat_max_gap_ms", "heartbeat_gaps_over_50ms", "process_cpu_ms"}
        and type(value) in (int, float)
    }
    result["desktop"] = {
        key: sample["desktop"][key]
        for key in (
            "qt_platform",
            "window_visible",
            "window_exposed",
            "window_minimized",
            "screen_geometry",
            "device_pixel_ratio",
        )
        if key in sample.get("desktop", {})
    }
    return result
