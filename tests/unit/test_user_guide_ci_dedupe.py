"""E8 fail-open push/PR duplicate detection must retain branch-only validation."""

from __future__ import annotations

import urllib.error

from scripts.skip_duplicate_user_guide_push import has_equivalent_pr_run, should_skip_push

REPO = "delphykmc/pixelscope"
SHA = "a" * 40
BRANCH = "perf/wp-help-e8-screenshot-rendering-tests"


def _run(**changes: object) -> dict:
    entry = {
        "event": "pull_request",
        "head_sha": SHA,
        "head_branch": BRANCH,
        "head_repository": {"full_name": REPO},
        "pull_requests": [{"number": 102}],
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
    }
    entry.update(changes)
    return entry


def test_only_existing_matching_pr_validation_can_replace_push() -> None:
    assert has_equivalent_pr_run(
        [_run()], repo=REPO, branch=BRANCH, sha=SHA, open_pr_numbers={102}
    )
    assert has_equivalent_pr_run(
        [_run(status="completed", conclusion="failure")],
        repo=REPO,
        branch=BRANCH,
        sha=SHA,
        open_pr_numbers={102},
    )  # PR failure remains visible; never hide it with a successful duplicate


def test_wrong_shas_branches_repos_events_and_cancelled_runs_fail_open() -> None:
    for altered in [
        {"head_sha": "b" * 40},
        {"head_branch": "different-branch"},
        {"head_repository": {"full_name": "other/repo"}},
        {"event": "push"},
        {"pull_requests": [{"number": 999}]},
        {"conclusion": "cancelled"},
        {"conclusion": "skipped"},
        {"conclusion": "action_required"},
    ]:
        assert not has_equivalent_pr_run(
            [_run(**altered)], repo=REPO, branch=BRANCH, sha=SHA, open_pr_numbers={102}
        )


def test_branch_only_push_executes_without_polling() -> None:
    urls: list[str] = []

    def fetch(url: str, _token: str) -> object:
        urls.append(url)
        return []

    assert not should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch
    )
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

    def fetch(url: str, _token: str) -> object:
        nonlocal checks
        if "/pulls?" in url:
            return [_open_pr()]
        checks += 1
        return {"workflow_runs": [_run()]} if checks == 2 else {"workflow_runs": []}

    assert should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=fetch, sleep=lambda _: None
    )
    assert checks == 2


def test_missing_token_closed_pr_wrong_sha_or_api_error_runs_push() -> None:
    assert not should_skip_push(repo=REPO, branch=BRANCH, sha=SHA, token="")
    for entry in [_open_pr(state="closed"), _open_pr(head={"sha": "b" * 40})]:
        assert not should_skip_push(
            repo=REPO,
            branch=BRANCH,
            sha=SHA,
            token="fake",
            fetch=lambda _url, _token: [entry],
        )

    def unavailable(_url: str, _token: str) -> object:
        raise urllib.error.URLError("synthetic outage")

    assert not should_skip_push(
        repo=REPO, branch=BRANCH, sha=SHA, token="fake", fetch=unavailable
    )
