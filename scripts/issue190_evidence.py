"""Allowlisted scalar sample export; raw logs/settings/pixels remain local."""

from __future__ import annotations

import re


def anonymize_sample(sample: dict) -> dict:
    allowed = (
        "case_id",
        "run_id",
        "warmup",
        "status",
        "returncode",
        "normal_gc",
        "fixture_sha256",
        "qt_platform",
    )
    output = {key: sample[key] for key in allowed if key in sample}
    output["metrics_ms"] = {
        key: value
        for key, value in sample.get("metrics_ms", {}).items()
        if re.fullmatch(r"[A-Za-z0-9_]+", key) and type(value) in (int, float)
    }
    output["checks"] = [
        check
        for check in sample.get("checks", [])
        if isinstance(check, str) and re.fullmatch(r"[A-Za-z0-9_]+", check)
    ]
    output["model_proxy_enabled"] = "_L2_" in sample["case_id"]
    output["milestones"] = {}
    for key, value in sample.get("milestones", {}).items():
        if key in ("proxy_counts", "per_action_proxy_counts"):
            if output["model_proxy_enabled"]:
                output["milestones"][key] = value
        elif re.fullmatch(
            r"(?:[ABF]_(?:enqueue|registered|discovery_(?:enter|start|end|return)|"
            r"barrier_(?:enter|release)|first_row(?:_inserted)?|last_row_inserted|"
            r"final_row|registration_finished)|registration_complete|measurement_end_ns)",
            key,
        ) and type(value) in (int, float):
            output["milestones"][key] = value
    output["desktop"] = {
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
    return output
