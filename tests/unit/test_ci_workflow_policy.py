"""Executable contracts for CI ownership and native-runner policy."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_validation_is_feature_neutral() -> None:
    workflow = _read(".github/workflows/validation.yml")

    assert "name: Focused validation" in workflow
    assert not (ROOT / ".github/workflows/user-guide.yml").exists()
    assert "Validate on ubuntu-latest" in workflow
    assert "Validate on windows-2022" in workflow


def test_generic_src_runs_mypy_without_requiring_native_pytest() -> None:
    workflow = _read(".github/workflows/validation.yml")
    ubuntu, windows = workflow.split("\n  windows:\n", maxsplit=1)

    assert "needs.classify.outputs.src_changed == 'true'" in ubuntu
    assert "python -m mypy src" in ubuntu
    assert "requirements/runtime.txt mypy==1.8.0" in ubuntu
    assert "needs.classify.outputs.windows_native == 'true'" in windows
    assert "python -m mypy src" not in windows


def test_docs_families_have_separate_pytest_steps() -> None:
    workflow = _read(".github/workflows/validation.yml")

    assert "Run core documentation contracts" in workflow
    assert "Run screenshot lifecycle contracts" in workflow
    assert "Run publication and packaging contracts" in workflow
    assert "needs.classify.outputs.docs_core == 'true'" in workflow
    assert "needs.classify.outputs.screenshots == 'true'" in workflow
    assert "needs.classify.outputs.publication == 'true'" in workflow


def test_expensive_e4_capture_is_not_a_per_synchronize_gate() -> None:
    workflow = _read(".github/workflows/ui-screenshot-diff.yml")

    assert "types: [opened, reopened, ready_for_review]" in workflow
    assert "synchronize" not in workflow
    assert "workflow_dispatch:" in workflow
    assert "runs-on: windows-2022" in workflow


def test_active_native_gui_workflows_share_the_reviewed_runner_generation() -> None:
    for path in (".github/workflows/validation.yml", ".github/workflows/ui-screenshot-diff.yml"):
        workflow = _read(path)
        assert "windows-latest" not in workflow
        assert "windows-2022" in workflow


def test_feature_workflows_do_not_add_repository_full_pytest_gate() -> None:
    for path in (".github/workflows/validation.yml", ".github/workflows/ui-screenshot-diff.yml"):
        workflow = _read(path)
        lines = [line.strip() for line in workflow.splitlines()]
        assert "run: python -m pytest -q" not in lines


def test_obsolete_e1_workflow_is_removed_but_shared_capture_engine_remains() -> None:
    assert not (ROOT / ".github/workflows/ui-screenshot-poc.yml").exists()
    assert (ROOT / "scripts/capture_ui_scene.py").exists()
    assert (ROOT / "scripts/run_ui_capture_poc.py").exists()
