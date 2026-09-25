"""Reduce duplicate User Guide push jobs ONLY when a real equivalent PR run exists.

The fallback is always to execute both matrix jobs. Never infer a PR-run
guarantee merely from an open PR, cancel a required check, or drop standalone
branch pushes. Queries use the read-only workflow token, no third-party action.
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


def has_equivalent_pr_run(
    runs: list[dict[str, Any]],
    *,
    repo: str,
    branch: str,
    sha: str,
    open_pr_numbers: set[int],
) -> bool:
    """Only an actual, non-cancelled Docs PR run on the same ref can replace push."""
    return any(
        run.get("event") == "pull_request"
        and run.get("head_sha") == sha
        and run.get("head_branch") == branch
        and (run.get("head_repository") or {}).get("full_name") == repo
        and run.get("conclusion") not in ("cancelled", "skipped", "action_required")
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


def should_skip_push(
    *,
    repo: str,
    branch: str,
    sha: str,
    token: str,
    fetch: Callable[[str, str], Any] = query_json,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Fail open on API errors or PR path-filter/race: run full push validation."""
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
            if has_equivalent_pr_run(
                runs, repo=repo, branch=branch, sha=sha, open_pr_numbers=matching
            ):
                return True
            if attempt < 2:
                sleep(3)
    except (
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
        "Docs push: equivalent required PR validation exists; skip redundant push matrix job"
        if skip
        else "Docs push: no proven equivalent PR validation; run full matrix job"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
