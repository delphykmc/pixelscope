from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_validation_workflow_separates_cheap_focused_and_full_gates() -> None:
    text = (ROOT / ".github/workflows/validation.yml").read_text(encoding="utf-8")

    assert "Cheap repository validation" in text
    assert "Focused Windows validation" in text
    assert "Full Windows validation" in text
    assert "needs.classify.outputs.full != 'true'" in text
    assert "needs.classify.outputs.full == 'true'" in text
    assert "python -m pytest -q\n" in text
    assert "normal GC" in text
    assert "scripts/classify_ci_changes.py" in text
    assert "scripts/skip_duplicate_validation_push.py" in text


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
