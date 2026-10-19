import pytest
from scripts.issue190_diff_on import durations


def test_d1_inclusive_durations_keep_nested_renderer_and_warm_phase_separate():
    rows = [
        ("cold", "handler_begin", 0),
        ("cold", "absolute_begin", 1),
        ("cold", "absolute_end", 201),
        ("cold", "handler_end", 220),
        ("warm", "handler_begin", 300),
        ("warm", "handler_end", 305),
    ]
    events = [
        {"intent_id": phase, "stage": stage, "ns": ms * 1_000_000} for phase, stage, ms in rows
    ]
    cold, warm = durations(events, "cold"), durations(events, "warm")
    assert cold["handler_ms"] == 220 and cold["absolute_ms"] == 200
    assert cold["absolute_calls"] == 1
    assert warm["handler_ms"] == 5 and "absolute_ms" not in warm


def test_d1_rejects_unbalanced_trace_instead_of_reporting_partial_cost():
    with pytest.raises(ValueError, match="unbalanced"):
        durations([{"intent_id": "cold", "stage": "absolute_begin", "ns": 1}], "cold")
