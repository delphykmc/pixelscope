from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts import run_test_batches as runner


def test_discover_ui_test_files_is_recursive_sorted_and_test_only(tmp_path: Path) -> None:
    ui = tmp_path / "tests" / "ui"
    nested = ui / "nested"
    nested.mkdir(parents=True)
    (ui / "test_zeta.py").write_text("", encoding="utf-8")
    (ui / "conftest.py").write_text("", encoding="utf-8")
    (nested / "test_alpha.py").write_text("", encoding="utf-8")

    assert runner.discover_ui_test_files(tmp_path) == [
        "tests/ui/nested/test_alpha.py",
        "tests/ui/test_zeta.py",
    ]


def test_build_batches_keeps_non_ui_together_and_chunks_ui_files(tmp_path: Path) -> None:
    for relative in runner.NON_UI_PATHS:
        (tmp_path / relative).mkdir(parents=True)
    ui = tmp_path / "tests" / "ui"
    ui.mkdir(parents=True)
    for index in range(5):
        (ui / f"test_{index}.py").write_text("", encoding="utf-8")

    batches = runner.build_batches(tmp_path, ui_batch_size=2, scope="all")

    assert batches[0] == runner.TestBatch(name="non-ui", paths=runner.NON_UI_PATHS)
    assert [batch.name for batch in batches[1:]] == ["ui-001", "ui-002", "ui-003"]
    assert [len(batch.paths) for batch in batches[1:]] == [2, 2, 1]
    assert [path for batch in batches[1:] for path in batch.paths] == [
        f"tests/ui/test_{index}.py" for index in range(5)
    ]


def test_classify_returncode_preserves_pytest_and_native_failures() -> None:
    assert runner.classify_returncode(0, platform_name="nt") == "passed"
    assert runner.classify_returncode(1, platform_name="nt") == "pytest-failed"
    assert runner.classify_returncode(5, platform_name="nt") == "no-tests-collected"
    assert runner.classify_returncode(0xC0000005, platform_name="nt") == "native-crash"
    assert runner.classify_returncode(-11, platform_name="posix") == "signal-crash"
    assert runner.classify_returncode(17, platform_name="nt") == "process-error"


def test_run_batch_uses_current_python_and_writes_log_and_junit_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded["command"] = command
        recorded["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="1 passed\n")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    batch = runner.TestBatch("ui-001", ("tests/ui/test_one.py", "tests/ui/test_two.py"))

    result = runner.run_batch(
        tmp_path,
        batch,
        artifacts_dir=artifacts,
        timeout_seconds=12.0,
    )

    command = recorded["command"]
    assert isinstance(command, list)
    assert command[:4] == [runner.sys.executable, "-m", "pytest", "-q"]
    assert command[4:6] == list(batch.paths)
    assert command[6] == f"--junitxml={artifacts / 'ui-001.xml'}"
    assert result.status == "passed"
    assert result.returncode == 0
    assert result.log_path.read_text(encoding="utf-8") == "1 passed\n"


def test_run_batch_records_timeout_without_converting_it_to_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(command, 3.0, output="partial pytest output\n")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    batch = runner.TestBatch("ui-001", ("tests/ui/test_one.py",))

    result = runner.run_batch(
        tmp_path,
        batch,
        artifacts_dir=artifacts,
        timeout_seconds=3.0,
    )

    assert result.status == "timeout"
    assert result.returncode is None
    assert result.log_path.read_text(encoding="utf-8") == "partial pytest output\n"


def test_write_summary_fails_if_any_batch_did_not_pass(tmp_path: Path) -> None:
    passed = runner.BatchResult(
        batch=runner.TestBatch("non-ui", ("tests/unit",)),
        status="passed",
        returncode=0,
        elapsed_seconds=1.0,
        log_path=tmp_path / "non-ui.log",
        junit_path=tmp_path / "non-ui.xml",
    )
    crashed = runner.BatchResult(
        batch=runner.TestBatch("ui-001", ("tests/ui/test_one.py",)),
        status="native-crash",
        returncode=0xC0000005,
        elapsed_seconds=2.0,
        log_path=tmp_path / "ui-001.log",
        junit_path=tmp_path / "ui-001.xml",
    )

    summary = runner.write_summary([passed, crashed], tmp_path).read_text(encoding="utf-8")

    assert "non-ui: passed" in summary
    assert "ui-001: native-crash" in summary
    assert "failed_or_incomplete=1" in summary
    assert "overall=FAIL" in summary
