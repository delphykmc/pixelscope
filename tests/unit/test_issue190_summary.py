from scripts.issue190_baseline import build_decisions, summarize


def test_exploratory_summary_keeps_raw_samples_excludes_warmup_and_failure():
    samples = [
        {"case_id": "E2", "status": "ok", "warmup": True, "metrics_ms": {"queue": 900}},
        {"case_id": "E2", "status": "ok", "metrics_ms": {"queue": 2}},
        {"case_id": "E2", "status": "ok", "metrics_ms": {"queue": 4}},
        {"case_id": "E2", "status": "failed", "metrics_ms": {"queue": 0}},
        {"case_id": "E3", "status": "timeout"},
    ]
    assert summarize(samples) == {"E2": {"queue": {"median": 3, "raw": [2, 4]}}}


def test_chair_decision_ids_keep_s4_separate_from_s7_fifo_evidence():
    samples = [
        {"case_id": case, "run_id": case + "-02", "status": "ok"}
        for case in ("E1_Open_0", "E2_contended", "E3_L1_1000")
    ]
    result = build_decisions(samples)
    expected = {
        "U1": ("F1", ["E1_Open_0"]),
        "U2": ("S4", []),
        "U3": ("S7", ["E2_contended"]),
        "U4": ("F4", ["E3_L1_1000"]),
    }
    for key, (hypothesis, cases) in expected.items():
        item = result["decisions"][key]
        assert item["decision_id"] == key
        assert item["hypothesis"].startswith(hypothesis)
        assert item["case_ids"] == cases
        assert item["run_ids"] == [case + "-02" for case in cases]
        assert item["result"] == "inconclusive"
        assert item["limitation"] and item["reason"]
        assert item["feature_optimization_result"] == "inconclusive"
    assert result["decisions"]["U2"]["evidence_grade"] == "unavailable"
    assert result["decisions"]["U3"]["G1_mechanism_supported"] is True


def test_failed_or_warmup_fifo_samples_do_not_establish_mechanism_evidence():
    samples = [
        {"case_id": "E2_contended", "run_id": "warm", "status": "ok", "warmup": True},
        {"case_id": "E2_contended", "run_id": "failed", "status": "failed"},
    ]
    result = build_decisions(samples)
    assert result["decisions"]["U3"]["G1_mechanism_supported"] is False
    assert result["failures"] == ["failed"]
