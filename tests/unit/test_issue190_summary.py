from scripts.issue190_baseline import summarize


def test_exploratory_summary_keeps_raw_samples_excludes_warmup_and_failure():
    samples = [
        {"case_id": "E2", "status": "ok", "warmup": True, "metrics_ms": {"queue": 900}},
        {"case_id": "E2", "status": "ok", "metrics_ms": {"queue": 2}},
        {"case_id": "E2", "status": "ok", "metrics_ms": {"queue": 4}},
        {"case_id": "E2", "status": "failed", "metrics_ms": {"queue": 0}},
        {"case_id": "E3", "status": "timeout"},
    ]
    assert summarize(samples) == {"E2": {"queue": {"median": 3, "raw": [2, 4]}}}
