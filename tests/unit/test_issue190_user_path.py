import numpy as np
import pytest
from scripts.issue190_user_path import Recorder, stage_metrics, textured


def test_fixture_is_reproducible_distinct_and_spatially_textured():
    a, b = textured(1901, 48, 64), textured(1902, 48, 64)
    assert a.shape == (48, 64, 3) and a.dtype == np.uint8
    assert np.array_equal(a, textured(1901, 48, 64))
    assert not np.array_equal(a, b)
    assert np.array_equal(a[0, 0], [255, 0, 0])
    assert np.array_equal(b[0, 0], [0, 255, 255])
    assert np.unique(a.reshape(-1, 3), axis=0).shape[0] > 1000


def test_trace_is_off_by_default_bounded_and_rejects_object_retention():
    trace = Recorder(capacity=2)
    trace.action("ignored")
    assert not trace.events
    trace.active = True
    trace.action("A_first")
    trace.add("queued", source="A", load_token=1)
    trace.add("overflow")
    assert len(trace.events) == 2 and trace.dropped == 1
    with pytest.raises(TypeError, match="primitive"):
        trace.add("invalid", payload=np.zeros(1))
    assert trace.events[0]["selection_epoch"] == 2


def test_stage_metrics_keep_io_decode_and_gui_brackets_separate():
    stages = [
        ("intent_accepted", 0),
        ("encoded_file_read_begin", 2),
        ("encoded_bytes_read", 5),
        ("opencv_decode_completed", 12),
        ("source_gui_enter", 20),
        ("source_gui_return_accepted", 24),
    ]
    metrics = stage_metrics(
        [
            {"stage": stage, "ns": ms * 1_000_000, "intent_id": "A_first", "source": "A"}
            for stage, ms in stages
        ]
    )
    assert metrics["A_first_A_file_read"] == 3
    assert metrics["A_first_A_decode_and_encoded_hash"] == 7
    assert metrics["A_first_A_source_gui_callback"] == 4
    assert not any("postpaint" in key for key in metrics)
