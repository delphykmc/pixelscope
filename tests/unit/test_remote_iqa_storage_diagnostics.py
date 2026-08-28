from pathlib import Path

from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from scripts.diagnose_remote_iqa_storage import (
    _same_windows_path,
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


def test_same_windows_path_is_case_insensitive() -> None:
    assert _same_windows_path(Path(r"X:\IQA-Server"), r"x:\iqa-server")
    assert not _same_windows_path(Path(r"X:\IQA-Server"), r"X:\other")


def test_missing_root_reports_failure_without_exposing_path(tmp_path: Path) -> None:
    report = run_storage_diagnostics(tmp_path / "missing")

    assert not report.passed
    assert report.mode == "synthetic_root"
    assert not report.root_exists
    assert not report.root_is_directory
    assert report.configured_root_count == 1
    assert report.configured_root_match_count == 1
    assert report.checked_source_count == 0
    assert report.observations == ()


def test_persisted_settings_mode_reports_missing_configured_root_match(tmp_path: Path) -> None:
    settings = RemoteIqaSettings(
        server_base_url="http://diagnostic.invalid",
        storage_roots=(RemoteIqaStorageRoot("other", r"Y:\other"),),
    )

    report = run_storage_diagnostics(tmp_path / "missing", settings=settings)

    assert not report.passed
    assert report.mode == "persisted_settings"
    assert report.configured_root_count == 1
    assert report.configured_root_match_count == 0
