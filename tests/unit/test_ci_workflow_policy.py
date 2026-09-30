"""Executable contracts for CI ownership and native-runner policy."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_change_scoped_workflow_preserves_legacy_pr_check_names() -> None:
    workflow = _read(".github/workflows/user-guide.yml")

    assert "Classify validation scope" in workflow
    assert "Validate on ubuntu-latest" in workflow
    assert "Validate on windows-2022" in workflow
    assert "Run focused RAW contracts" in workflow
    assert "Run focused YUV contracts" in workflow


def test_docs_only_validation_can_skip_windows_native_job() -> None:
    workflow = _read(".github/workflows/user-guide.yml")

    assert "needs.classify.outputs.windows_native == 'true'" in workflow
    assert "Install documentation validation dependencies" in workflow
    assert "runs-on: windows-2022" in workflow


def test_expensive_e4_capture_is_not_a_per_synchronize_gate() -> None:
    workflow = _read(".github/workflows/ui-screenshot-diff.yml")

    assert "types: [opened, reopened, ready_for_review]" in workflow
    assert "synchronize" not in workflow
    assert "workflow_dispatch:" in workflow
    assert 'runs-on: windows-2022' in workflow


def test_active_native_gui_workflows_share_the_reviewed_runner_generation() -> None:
    for path in (".github/workflows/user-guide.yml", ".github/workflows/ui-screenshot-diff.yml"):
        workflow = _read(path)
        assert "windows-latest" not in workflow
        assert "windows-2022" in workflow


def test_feature_workflows_do_not_add_repository_full_pytest_gate() -> None:
    for path in (
        ".github/workflows/user-guide.yml",
        ".github/workflows/ui-screenshot-diff.yml",
    ):
        workflow = _read(path)
        lines = [line.strip() for line in workflow.splitlines()]
        assert "run: python -m pytest -q" not in lines


def test_obsolete_e1_workflow_is_removed_but_shared_capture_engine_remains() -> None:
    assert not (ROOT / ".github/workflows/ui-screenshot-poc.yml").exists()
    assert (ROOT / "scripts/capture_ui_scene.py").exists()
    assert (ROOT / "scripts/run_ui_capture_poc.py").exists()
