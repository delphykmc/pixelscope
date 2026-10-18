import json

from scripts.issue190_user_path_evidence import export_sample


def test_export_removes_paths_payloads_and_process_addresses():
    sample = {
        "case_id": "R23_ON",
        "run_id": "R23_ON-02",
        "status": "fail",
        "correctness": "fail",
        "error": "C:/private",
        "settings": "private",
        "events": [
            {"stage": "intent_accepted", "ns": 99, "intent_id": "B_add"},
            {
                "stage": "load_result_signal",
                "ns": 100,
                "intent_id": "B_add",
                "source": "B",
                "preview_revision": 123456789,
                "path": "C:/private",
                "payload": object(),
            },
        ],
    }
    safe = export_sample(sample)
    assert "private" not in json.dumps(safe) and "123456789" not in json.dumps(safe)
    assert safe["events"][0]["ns"] == 0
    assert safe["events"][1]["preview_revision"] == 1
    assert safe["status"] == "fail" and safe["correctness"] == "fail"


def test_export_recomputes_metrics_and_preserves_range_failures():
    safe = export_sample(
        {
            "case_id": "R23_OFF",
            "metrics_ms": {"private": 999},
            "range_failures": [{"primary": "B", "source": "A", "private": "payload"}],
            "events": [],
            "trace_dropped": 3,
        }
    )
    assert safe["metrics_ms"] == {}
    assert safe["range_failures"] == [{"primary": "B", "source": "A"}]
    assert safe["trace_dropped"] == 3
