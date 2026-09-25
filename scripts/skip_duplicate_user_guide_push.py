"""Skip Docs push work only if PR and push are provably the same Git tree.

A pull_request checkout tests the synthetic base+head merge tree, NOT its
workflow_run.head_sha alone. Require a real eligible PR run, its pinned base,
the current PR merge commit's parents, and equal head/merge tree objects.
Any absent/stale API evidence runs BOTH push matrix jobs. No write token.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any


def has_matching_pr_run(
    runs: list[dict[str, Any]],
    *,
    repo: str,
    branch: str,
    sha: str,
    open_pr_numbers: set[int],
) -> bool:
    """Identify an eligible PR run; Git *tree* equivalence is checked separately."""
    return any(
        run.get("event") == "pull_request"
        and run.get("head_sha") == sha
        and run.get("head_branch") == branch
        and (run.get("head_repository") or {}).get("full_name") == repo
        and (
            (run.get("status") in ("queued", "in_progress") and run.get("conclusion") is None)
            or (
                run.get("status") == "completed" and run.get("conclusion") in ("success", "failure")
            )
        )
        and any(
            pr.get("number") in open_pr_numbers
            for pr in run.get("pull_requests", [])
            if isinstance(pr, dict)
        )
        for run in runs
    )


def query_json(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def same_tested_tree(
    *,
    repo: str,
    pr_number: int,
    head_sha: str,
    tested_base_sha: str,
    fetch: Callable[[str, str], Any],
    token: str,
) -> bool:
    """Check the exact current PR synthetic merge tree equals its head tree.

    GitHub's PR checkout defaults to refs/pull/N/merge. The PR workflow run
    metadata head_sha is NOT the checkout SHA. A changed merge base, stale
    merge ref, malformed parent list or unavailable commit forces push testing.
    """
    base = f"https://api.github.com/repos/{repo}"
    pr = fetch(f"{base}/pulls/{pr_number}", token)
    head = pr["head"]
    merge_sha = pr.get("merge_commit_sha")
    base_sha = pr["base"]["sha"]
    if (
        head["sha"] != head_sha
        or head["repo"]["full_name"] != repo
        or not isinstance(merge_sha, str)
        or len(merge_sha) != 40
        or not isinstance(base_sha, str)
        or len(base_sha) != 40
        or base_sha != tested_base_sha
    ):
        return False
    merge = fetch(f"{base}/git/commits/{merge_sha}", token)
    parents = [entry["sha"] for entry in merge["parents"]]
    if parents != [base_sha, head_sha]:
        return False
    head_commit = fetch(f"{base}/git/commits/{head_sha}", token)
    merge_tree = merge["tree"]["sha"]
    head_tree = head_commit["tree"]["sha"]
    return bool(merge_tree and merge_tree == head_tree)


def should_skip_push(
    *,
    repo: str,
    branch: str,
    sha: str,
    token: str,
    fetch: Callable[[str, str], Any] = query_json,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Unknown or unequal PR merge/head trees retain standalone push checks."""
    if not token or not repo or not branch or len(sha) != 40:
        return False
    owner = repo.split("/", 1)[0]
    encoded = urllib.parse.urlencode({"head": f"{owner}:{branch}", "state": "open"})
    base = f"https://api.github.com/repos/{repo}"
    try:
        prs = fetch(f"{base}/pulls?{encoded}&per_page=100", token)
        matching = {
            pr["number"]
            for pr in prs
            if pr.get("state") == "open"
            and pr.get("head", {}).get("sha") == sha
            and pr.get("head", {}).get("repo", {}).get("full_name") == repo
        }
        if not matching:
            return False  # branch-only push must retain its automatic validation
        runs_url = f"{base}/actions/workflows/user-guide.yml/runs?" + urllib.parse.urlencode(
            {"event": "pull_request", "head_sha": sha, "per_page": "100"}
        )
        # Push and PR events may enqueue in either order. Bounded polling saves
        # jobs when PR exists but never assumes that a filtered PR will run.
        for attempt in range(3):
            runs = fetch(runs_url, token)["workflow_runs"]
            if has_matching_pr_run(
                runs, repo=repo, branch=branch, sha=sha, open_pr_numbers=matching
            ):
                # A PR run for the same head SHA may have tested a different
                # base+head merge tree. Only skip if the merge *content* equals
                # the standalone push's head tree; otherwise keep both gates.
                for run in runs:
                    if not has_matching_pr_run(
                        [run], repo=repo, branch=branch, sha=sha, open_pr_numbers=matching
                    ):
                        continue
                    for record in run["pull_requests"]:
                        if record["number"] not in matching:
                            continue
                        tested_base_sha = record.get("base", {}).get("sha")
                        if not isinstance(tested_base_sha, str):
                            continue
                        if same_tested_tree(
                            repo=repo,
                            pr_number=record["number"],
                            head_sha=sha,
                            tested_base_sha=tested_base_sha,
                            fetch=fetch,
                            token=token,
                        ):
                            return True
                return False
            if attempt < 2:
                sleep(3)
    except (
        AttributeError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        urllib.error.URLError,
    ) as exc:
        print(f"Docs push dedupe unavailable ({type(exc).__name__}); running validation")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    skip = should_skip_push(
        repo=args.repo, branch=args.branch, sha=args.sha, token=os.environ.get("GH_TOKEN", "")
    )
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"skip={str(skip).lower()}\n")
    print(
        "Docs push: matching PR run AND identical merge/head Git tree; skip duplicate checks"
        if skip
        else "Docs push: no proven identical PR-tested Git tree; run full matrix checks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
