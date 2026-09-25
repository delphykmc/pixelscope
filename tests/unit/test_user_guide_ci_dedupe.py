"""E8: only a truly identical PR-tested Git tree may replace Docs push checks."""

from __future__ import annotations

import urllib.error
from typing import Any

import pytest
from scripts.skip_duplicate_user_guide_push import (
    has_matching_pr_run,
    same_tested_tree,
    should_skip_push,
)

REPO = "delphykmc/pixelscope"
SHA = "a" * 40
BASE = "b" * 40
MERGE = "c" * 40
TREE = "d" * 40
OTHER_TREE = "e" * 40
BRANCH = "perf/wp-help-e8-screenshot-rendering-tests"


def _run(**changes: object) -> dict:
    entry = {
        "event": "pull_request",
        "head_sha": SHA,
        "head_branch": BRANCH,
        "head_repository": {"full_name": REPO},
        "pull_requests": [{"number": 102, "base": {"sha": BASE}}],
        "status": "in_progress",
        "conclusion": None,
    }
    entry.update(changes)
    return entry


def _open_pr(**changes: object) -> dict:
    entry = {
        "number": 102,
        "state": "open",
        "head": {"sha": SHA, "repo": {"full_name": REPO}},
        "base": {"sha": BASE},
        "merge_commit_sha": MERGE,
    }
    entry.update(changes)
    return entry


def _api(
    *,
    run: dict | None = None,
    merge_tree: str = TREE,
    head_tree: str = TREE,
    prs: list[dict] | None = None,
    detailed_pr: dict | None = None,
    parents: list[dict] | None = None,
):
    calls: list[str] = []

    def fetch(url: str, _token: str) -> Any:
        calls.append(url)
        if "/pulls?" in url:
            return [_open_pr()] if prs is None else prs
        if url.endswith("/pulls/102"):
            return _open_pr() if detailed_pr is None else detailed_pr
        if url.endswith("/git/commits/" + MERGE):
            return {
                "parents": (
                    [{"sha": BASE}, {"sha": SHA}] if parents is None else parents
                ),
                "tree": {"sha": merge_tree},
            }
        if url.endswith("/git/commits/" + SHA):
            return {"tree": {"sha": head_tree}}
        if "/actions/workflows/user-guide.yml/runs?" in url:
            return {"workflow_runs": [_run()] if run is None else [run]}
        raise AssertionError("unexpected GitHub API request: " + url)

    return fetch, calls


def test_matching_pr_run_requires_valid_status_and_conclusion() -> None:
    for run in [
        _run(status="queued"),
        _run(status="in_progress"),
        _run(status="completed", conclusion="success"),
        _run(status="completed", conclusion="failure"),
    ]:
        assert has_matching_pr_run(
            [run], repo=REPO, branch=BRANCH, sha=SHA, open_pr_numbers={102}
        )


@pytest.mark.parametrize(
    "run",
    [
        _run(status="completed", conclusion="timed_out"),
        _run(status="completed", conclusion="stale"),
        _run(status="completed", conclusion="neutral"),
        _run(status="completed", conclusion="action_required"),
        _run(status="completed", conclusion="startup_failure"),
        _run(status="completed", conclusion="cancelled"),
        _run(status="completed", conclusion="skipped"),
        _run(status="completed", conclusion=None),
        _run(status="in_progress", conclusion="success"),
        _run(status="queued", conclusion="failure"),
        _run(status="waiting", conclusion=None),
        _run(status="unknown", conclusion=None),
        _run(head_sha="f" * 40),
        _run(head_branch="different-branch"),
        _run(head_repository={"full_name": "other/repo"}),
        _run(event="push"),
        _run(pull_requests=[{"number": 999, "base": {"sha": BASE}}]),
    ],
)
def test_nonvalidating_and_mismatched_pr_runs_cannot_skip_push(run: dict) -> None:
    assert not has_matching_pr_run(
        [run], repo=REPO, branch=BRANCH, sha=SHA, open_pr_numbers={102}
    )


def test_identical_current_head_and_merge_tree_may_skip_push() -> None:
    fetch, calls = _api()
    assert should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch
    )
    assert any("/pulls/102" in call for call in calls)
    assert any("/git/commits/" + MERGE in call for call in calls)
    assert any("/git/commits/" + SHA in call for call in calls)


def test_differs_from_pr_synthetic_merge_tree_must_keep_push_checks() -> None:
    fetch, _ = _api(merge_tree=OTHER_TREE)
    assert not should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch
    )


@pytest.mark.parametrize(
    "detail",
    [
        _open_pr(base={"sha": "e" * 40}),
        _open_pr(head={"sha": "f" * 40, "repo": {"full_name": REPO}}),
        _open_pr(merge_commit_sha=None),
    ],
)
def test_base_advanced_force_push_or_missing_merge_ref_keeps_push(detail: dict) -> None:
    fetch, _ = _api(detailed_pr=detail)
    assert not should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch
    )


def test_wrong_merge_parents_keep_push_checks() -> None:
    fetch, _ = _api(parents=[{"sha": "e" * 40}, {"sha": SHA}])
    assert not should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch
    )


def test_pr_run_metadata_must_name_same_tested_base() -> None:
    fetch, _ = _api(
        run=_run(pull_requests=[{"number": 102, "base": {"sha": "f" * 40}}])
    )
    assert not should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch
    )


def test_direct_tree_comparison_succeeds_only_for_same_pinned_base() -> None:
    fetch, _ = _api()
    assert same_tested_tree(
        repo=REPO,
        pr_number=102,
        head_sha=SHA,
        tested_base_sha=BASE,
        fetch=fetch,
        token="fake",
    )
    assert not same_tested_tree(
        repo=REPO,
        pr_number=102,
        head_sha=SHA,
        tested_base_sha="e" * 40,
        fetch=fetch,
        token="fake",
    )


def test_branch_only_push_executes_without_polling() -> None:
    urls: list[str] = []

    def fetch(url: str, _token: str) -> object:
        urls.append(url)
        return []

    assert not should_skip_push(repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch)
    assert len(urls) == 1 and "/pulls?" in urls[0]


def test_pr_run_is_not_assumed_from_open_pr_or_missing_actions_result() -> None:
    calls: list[str] = []
    delays: list[float] = []

    def fetch(url: str, _token: str) -> object:
        calls.append(url)
        return [_open_pr()] if "/pulls?" in url else {"workflow_runs": []}

    assert not should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch, sleep=delays.append
    )
    assert len(calls) == 4
    assert delays == [3, 3]


def test_actual_pr_run_after_event_race_short_circuits_push() -> None:
    checks = 0
    fetch_api, _ = _api()

    def fetch(url: str, token: str) -> Any:
        nonlocal checks
        if "/actions/workflows/user-guide.yml/runs?" in url:
            checks += 1
            return {"workflow_runs": [_run()]} if checks == 2 else {"workflow_runs": []}
        return fetch_api(url, token)

    assert should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch, sleep=lambda _: None
    )
    assert checks == 2


def test_missing_token_closed_pr_wrong_sha_or_api_error_runs_push() -> None:
    assert not should_skip_push(repo=REPO, branch=BRANCH, sha=SHA, token="")
    for entry in [_open_pr(state="closed"), _open_pr(head={"sha": "f" * 40})]:
        assert not should_skip_push(
            repo=REPO,
            branch=BRANCH,
            sha=SHA,
            token="fake",
            fetch=lambda _url, _token, payload=entry: [payload],
        )

    def unavailable(_url: str, _token: str) -> object:
        raise urllib.error.URLError("synthetic outage")

    assert not should_skip_push(repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=unavailable)


def test_invalid_github_merge_commit_response_falls_back_to_push() -> None:
    fetch_api, _ = _api()

    def fetch(url: str, token: str) -> Any:
        if "/git/commits/" + MERGE in url:
            return {"parents": None}
        return fetch_api(url, token)

    assert not should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch
    )
