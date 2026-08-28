from pathlib import Path

from scripts.diagnose_remote_iqa_storage import (
    _windows_lexically_contains,
    run_storage_diagnostics,
)


def test_windows_lexical_containment_accepts_child_case_insensitively() -> None:
    root = Path(r"X:\IQA-Server")
    source = Path(r"x:\iqa-server\image.png")

    assert _windows_lexically_contains(root, source)


def test_windows_lexical_containment_rejects_sibling_prefix() -> None:
    root = Path(r"X:\iqa-server")
    source = Path(r"X:\iqa-server-other\image.png")

    assert not _windows_lexically_contains(root, source)


def test_missing_root_reports_failure_without_exposing_path(tmp_path: Path) -> None:
    report = run_storage_diagnostics(tmp_path / "missing")

    assert not report.passed
    assert not report.root_exists
    assert not report.root_is_directory
    assert report.checked_source_count == 0
    assert report.observations == ()
