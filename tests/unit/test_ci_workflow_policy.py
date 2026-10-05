from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_validation_workflow_keeps_full_pytest_out_of_ci() -> None:
    text = (ROOT / ".github/workflows/validation.yml").read_text(encoding="utf-8")

    assert "Cheap repository validation" in text
    assert "Focused Windows validation" in text
    assert "Full Windows validation" not in text
    assert "Run complete repository pytest contract under normal GC" not in text
    assert "run: python -m pytest -q\n" not in text
    assert "needs.classify.outputs.full" not in text
    assert "python -m mypy src" in text
    assert "scripts/classify_ci_changes.py" in text
    assert "scripts/skip_duplicate_validation_push.py" in text


def test_focused_native_validation_is_not_suppressed_by_local_full_signal() -> None:
    text = (ROOT / ".github/workflows/validation.yml").read_text(encoding="utf-8")

    assert "needs.classify.outputs.windows_native == 'true'" in text
    assert "needs.classify.outputs.full != 'true'" not in text


def test_user_guide_workflow_no_longer_owns_unrelated_native_validation() -> None:
    text = (ROOT / ".github/workflows/user-guide.yml").read_text(encoding="utf-8")

    assert "Validate on windows-latest" not in text  # rendered job name is dynamic
    assert "Install application for Windows release-artifact regression tests" not in text
    assert "Install pinned Qt UI test harness on Windows" not in text
    assert "Validate E7 local and context Help UI on Windows" not in text
    assert "Run release-artifact regressions on Windows" not in text
    assert "Type-check entire src with mypy" not in text
    assert "matrix:\n        os: [ubuntu-latest, windows-latest]" in text


def test_ci_policy_contains_no_pr_number_specific_selection() -> None:
    paths = (
        ROOT / ".github/workflows/validation.yml",
        ROOT / "scripts/classify_ci_changes.py",
        ROOT / "scripts/ci_test_groups.py",
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "pull/" not in text
    assert "PR #" not in text
