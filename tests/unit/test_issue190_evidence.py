import json

from scripts.issue190_evidence import anonymize_sample


def test_export_excludes_private_payloads_and_disabled_l1_model_counters():
    sample = {
        "case_id": "E3K_L1_ON",
        "run_id": "sample-02",
        "status": "ok",
        "error": "C:/private/error.py",
        "source": object(),
        "settings": "private",
        "metrics_ms": {"primary_sync": 3.5, "C:/private": 1, "pixels": object()},
        "checks": ["source_exact", "C:/private"],
        "milestones": {
            "bindings_before_primary": [{"physical_viewer": 123, "document_id": "private"}],
            "proxy_counts": {"dataChanged": 0},
            "measurement_end_ns": 42,
            "C:/private": 1,
        },
        "desktop": {"qt_platform": "windows", "window_title": "private", "window_exposed": True},
    }
    result = anonymize_sample(sample)
    assert "private" not in json.dumps(result)
    assert result["metrics_ms"] == {"primary_sync": 3.5}
    assert result["checks"] == ["source_exact"]
    assert result["milestones"] == {"measurement_end_ns": 42}
    assert result["model_proxy_enabled"] is False


def test_export_retains_enabled_per_action_l2_proxies_and_e2_timeline():
    proxies = {"select_one": {"synchronous": {"dataChanged": 4}}}
    result = anonymize_sample(
        {
            "case_id": "E3_L2_100",
            "run_id": "sample-02",
            "status": "ok",
            "milestones": {"per_action_proxy_counts": proxies},
        }
    )
    assert result["model_proxy_enabled"] is True
    assert result["milestones"]["per_action_proxy_counts"] == proxies
    result = anonymize_sample(
        {
            "case_id": "E2_contended_8_0",
            "run_id": "sample-02",
            "status": "ok",
            "milestones": {
                "F_barrier_release": 1,
                "F_discovery_start": 2,
                "F_registration_finished": 3,
            },
        }
    )
    assert result["milestones"] == {
        "F_barrier_release": 1,
        "F_discovery_start": 2,
        "F_registration_finished": 3,
    }
