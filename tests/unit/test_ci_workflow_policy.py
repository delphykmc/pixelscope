from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _run_blocks(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped.startswith("run:"):
            continue
        indent = len(line) - len(stripped)
        value = stripped.removeprefix("run:").strip()
        if value and value not in {"|", "|-", ">", ">-"}:
            blocks.append(value)
            continue

        body: list[str] = []
        for candidate in lines[index + 1 :]:
            candidate_stripped = candidate.lstrip()
            candidate_indent = len(candidate) - len(candidate_stripped)
            if candidate_stripped and candidate_indent <= indent:
                break
            if candidate_stripped:
                body.append(candidate_stripped)
        blocks.append(" ".join(body) if value.startswith(">") else "\n".join(body))
    return blocks


def test_validation_workflow_keeps_full_pytest_out_of_ci() -> None:
    text = (WORKFLOWS / "validation.yml").read_text(encoding="utf-8")

    assert "Cheap repository validation" in text
    assert "Source typecheck" in text
    assert "Focused Windows validation" in text
    assert "Full Windows validation" not in text
    assert "Run complete repository pytest contract under normal GC" not in text
    assert "needs.classify.outputs.full" not in text
    assert "local_full_required" in text
    assert "GitHub CI intentionally does not run the complete pytest suite" in text
    assert "python -m pip install -r requirements/runtime.txt mypy==1.8.0" in text
    assert "python -m mypy src" in text
    assert "needs.classify.outputs.ci_policy == 'true'" in text
    assert '--diff-mode "$CI_DIFF_MODE"' in text
    assert "scripts/classify_ci_changes.py" in text
    assert "scripts/skip_duplicate_validation_push.py" in text


def test_all_workflow_pytest_invocations_are_explicitly_scoped() -> None:
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        for block in _run_blocks(path):
            if "python -m pytest" in block:
                assert "tests/" in block, f"unscoped pytest invocation in {path}: {block}"


def test_focused_native_validation_is_not_suppressed_by_local_full_signal() -> None:
    text = (WORKFLOWS / "validation.yml").read_text(encoding="utf-8")

    assert "needs.classify.outputs.windows_native == 'true'" in text
    assert "needs.classify.outputs.local_full_required != 'true'" not in text


def test_user_guide_workflow_no_longer_owns_unrelated_native_validation() -> None:
    text = (WORKFLOWS / "user-guide.yml").read_text(encoding="utf-8")

    assert "Validate on windows-latest" not in text  # rendered job name is dynamic
    assert "Install application for Windows release-artifact regression tests" not in text
    assert "Install pinned Qt UI test harness on Windows" not in text
    assert "Validate E7 local and context Help UI on Windows" not in text
    assert "Run release-artifact regressions on Windows" not in text
    assert "Type-check entire src with mypy" not in text
    assert "matrix:\n        os: [ubuntu-latest, windows-latest]" in text


def test_ci_policy_contains_no_pr_number_specific_selection() -> None:
    paths = (
        WORKFLOWS / "validation.yml",
        ROOT / "scripts/classify_ci_changes.py",
        ROOT / "scripts/ci_test_groups.py",
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "pull/" not in text
    assert "PR #" not in text
