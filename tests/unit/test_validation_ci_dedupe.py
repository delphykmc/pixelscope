from __future__ import annotations

from typing import Any

from scripts.skip_duplicate_validation_push import has_matching_pr_run, should_skip_push

REPO = "delphykmc/pixelscope"
BRANCH = "ci/example"
SHA = "a" * 40
BASE = "b" * 40
MERGE = "c" * 40
TREE = "d" * 40


def _run() -> dict[str, Any]:
    return {
        "event": "pull_request",
        "head_sha": SHA,
        "head_branch": BRANCH,
        "head_repository": {"full_name": REPO},
        "pull_requests": [{"number": 12, "base": {"sha": BASE}}],
        "status": "in_progress",
        "conclusion": None,
    }


def _fetch(*, merge_tree: str = TREE):
    calls: list[str] = []

    def fetch(url: str, _token: str) -> Any:
        calls.append(url)
        if "/pulls?" in url:
            return [
                {
                    "number": 12,
                    "state": "open",
                    "head": {"sha": SHA, "repo": {"full_name": REPO}},
                }
            ]
        if url.endswith("/pulls/12"):
            return {
                "number": 12,
                "head": {"sha": SHA, "repo": {"full_name": REPO}},
                "base": {"sha": BASE},
                "merge_commit_sha": MERGE,
            }
        if url.endswith("/git/commits/" + MERGE):
            return {
                "parents": [{"sha": BASE}, {"sha": SHA}],
                "tree": {"sha": merge_tree},
            }
        if url.endswith("/git/commits/" + SHA):
            return {"tree": {"sha": TREE}}
        if "/actions/workflows/validation.yml/runs?" in url:
            return {"workflow_runs": [_run()]}
        raise AssertionError(url)

    return fetch, calls


def test_matching_pr_run_must_be_same_repo_branch_sha_and_open_pr() -> None:
    assert has_matching_pr_run([_run()], repo=REPO, branch=BRANCH, sha=SHA, open_pr_numbers={12})
    assert not has_matching_pr_run(
        [_run()], repo=REPO, branch="other", sha=SHA, open_pr_numbers={12}
    )


def test_identical_pr_merge_and_head_tree_may_skip_duplicate_push() -> None:
    fetch, calls = _fetch()
    assert should_skip_push(repo=REPO, branch=BRANCH, sha=SHA, token="token", fetch=fetch)
    assert any("validation.yml/runs" in call for call in calls)


def test_different_merge_tree_keeps_standalone_push_validation() -> None:
    fetch, _ = _fetch(merge_tree="e" * 40)
    assert not should_skip_push(repo=REPO, branch=BRANCH, sha=SHA, token="token", fetch=fetch)


def test_missing_token_or_open_pr_evidence_keeps_push_validation() -> None:
    assert not should_skip_push(repo=REPO, branch=BRANCH, sha=SHA, token="")
    assert not should_skip_push(
        repo=REPO,
        branch=BRANCH,
        sha=SHA,
        token="token",
        fetch=lambda _url, _token: [],
    )


def test_branch_push_without_pr_does_not_poll_workflow_runs() -> None:
    calls: list[str] = []

    def fetch(url: str, _token: str) -> Any:
        calls.append(url)
        return []

    assert not should_skip_push(repo=REPO, branch=BRANCH, sha=SHA, token="token", fetch=fetch)
    assert len(calls) == 1 and "/pulls?" in calls[0]
