from scripts.issue190_baseline import build_decisions, summarize
from scripts.issue190_followup import e2_intervals


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
    # Case-to-decision mapping does not establish causal FIFO support by itself.
    assert result["decisions"]["U3"]["G1_mechanism_supported"] is False


def test_failed_or_warmup_fifo_samples_do_not_establish_mechanism_evidence():
    samples = [
        {"case_id": "E2_contended", "run_id": "warm", "status": "ok", "warmup": True},
        {"case_id": "E2_contended", "run_id": "failed", "status": "failed"},
    ]
    result = build_decisions(samples)
    assert result["decisions"]["U3"]["G1_mechanism_supported"] is False
    assert result["failures"] == ["failed"]


def test_e2_separates_barrier_worker_discovery_gui_rows_and_commit():
    marks = dict(
        zip(
            [
                "F_barrier_enter",
                "F_barrier_release",
                "F_discovery_start",
                "F_discovery_return",
                "F_first_row_inserted",
                "F_last_row_inserted",
                "F_registration_finished",
                "A_discovery_start",
            ],
            [
                0,
                750_000_000,
                751_000_000,
                951_000_000,
                954_000_000,
                964_000_000,
                969_000_000,
                970_000_000,
            ],
            strict=True,
        )
    )
    assert e2_intervals(marks) == {
        "F_barrier_wait": 750,
        "F_release_to_discovery_start": 1,
        "F_discovery_work": 200,
        "F_worker_to_first_GUI_row": 3,
        "F_GUI_row_span": 10,
        "F_last_row_to_commit": 5,
        "F_GUI_handoff_to_commit": 18,
        "F_commit_to_A_dispatch": 1,
    }


def test_e2_incomplete_timeline_is_not_inferred_success():
    import pytest

    with pytest.raises(KeyError):
        e2_intervals({"F_barrier_enter": 0})


def test_control_only_does_not_establish_head_of_line_mechanism():
    result = build_decisions([{"case_id": "E2_control", "run_id": "control", "status": "ok"}])
    assert result["decisions"]["U3"]["G1_mechanism_supported"] is False


def _paired_fifo_sample(case_id: str, *, run: str = "02") -> dict:
    if case_id == "E2_control":
        marks = {
            "A_enqueue": 5_000_000,
            "B_enqueue": 6_000_000,
            "A_discovery_start": 7_000_000,
            "A_registered": 10_000_000,
            "B_discovery_start": 12_000_000,
            "B_registered": 15_000_000,
        }
    else:
        marks = {
            "F_discovery_enter": 50_000_000,
            "F_barrier_enter": 51_000_000,
            "A_enqueue": 55_000_000,
            "B_enqueue": 56_000_000,
            "F_barrier_release": 70_000_000,
            "F_discovery_start": 71_000_000,
            "F_discovery_return": 90_000_000,
            "F_first_row_inserted": 92_000_000,
            "F_last_row_inserted": 95_000_000,
            "F_registration_finished": 98_000_000,
            "A_discovery_start": 100_000_000,
            "A_registered": 105_000_000,
            "B_discovery_start": 110_000_000,
            "B_registered": 115_000_000,
        }
    intervals = (
        ("A_enqueue", "A_discovery_start", "A_enqueue_to_discovery_start"),
        ("A_enqueue", "A_registered", "A_enqueue_to_registered"),
        ("B_enqueue", "B_discovery_start", "B_enqueue_to_discovery_start"),
        ("B_enqueue", "B_registered", "B_enqueue_to_registered"),
    )
    return {
        "case_id": case_id,
        "run_id": f"{case_id}-{run}",
        "status": "ok",
        "warmup": False,
        "returncode": 0,
        "milestones": marks,
        "metrics_ms": {name: (marks[end] - marks[start]) / 1e6 for start, end, name in intervals},
        "checks": [
            "A_B_order",
            "FIFO",
            "unique_rows",
            "no_stale_callback",
            "folder_natural_order_no_autoselect",
        ],
    }


def test_fifo_g1_support_requires_paired_control_metrics_and_correctness():
    from copy import deepcopy

    control = _paired_fifo_sample("E2_control")
    contended = _paired_fifo_sample("E2_contended_8_0")

    def supported(samples):
        decision = build_decisions(samples)["decisions"]["U3"]
        assert decision["feature_optimization_result"] == "inconclusive"
        return decision["G1_mechanism_supported"]

    assert supported([control, contended]) is True
    assert supported([contended]) is False
    assert supported([control]) is False

    bad_control = deepcopy(control)
    bad_control["status"] = "failed"
    assert supported([bad_control, contended]) is False

    bad_control = deepcopy(control)
    bad_control["warmup"] = True
    assert supported([bad_control, contended]) is False

    bad_contended = deepcopy(contended)
    bad_contended["metrics_ms"].pop("A_enqueue_to_discovery_start")
    assert supported([control, bad_contended]) is False

    bad_contended = deepcopy(contended)
    bad_contended["checks"].remove("FIFO")
    assert supported([control, bad_contended]) is False

    bad_contended = deepcopy(contended)
    bad_contended["milestones"]["F_registration_finished"] = 110_000_000
    assert supported([control, bad_contended]) is False

    bad_contended = deepcopy(contended)
    bad_contended["run_id"] = "E2_contended_8_0-03"
    assert supported([control, bad_contended]) is False

    # Merely claiming the same result without an observed greater queue wait fails.
    bad_contended = deepcopy(contended)
    bad_contended["metrics_ms"]["A_enqueue_to_discovery_start"] = 0
    assert supported([control, bad_contended]) is False


def test_fifo_g1_support_rejects_control_missing_metrics_or_order_evidence():
    from copy import deepcopy

    control = _paired_fifo_sample("E2_control")
    contended = _paired_fifo_sample("E2_contended_8_0")
    bad_control = deepcopy(control)
    bad_control["metrics_ms"].pop("A_enqueue_to_registered")
    assert (
        build_decisions([bad_control, contended])["decisions"]["U3"]["G1_mechanism_supported"]
        is False
    )

    bad_control = deepcopy(control)
    bad_control["checks"].remove("A_B_order")
    assert (
        build_decisions([bad_control, contended])["decisions"]["U3"]["G1_mechanism_supported"]
        is False
    )
