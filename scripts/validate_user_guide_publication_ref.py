from __future__ import annotations

import argparse
import ast
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SHA_RE = re.compile(r"[0-9a-f]{40}")
# Accept stable and conventional Python pre-release tags. Reject path, ref,
# expression and checkout-option syntax before resolving any user-selected ref.
_TAG_RE = re.compile(
    r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)" r"(?:(?:a|b|rc)(?:0|[1-9][0-9]*))?"
)
_REQUIRED_TAG_FILES = (
    "scripts/prepare_user_guide_publication.py",
    "requirements/docs.txt",
    "mkdocs.yml",
    ".github/workflows/user-guide-publication.yml",
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _read_committed_version(source_commit: str) -> str:
    """Read a string literal from version.py without executing selected code."""
    text = _git("show", f"{source_commit}:src/pixelscope/version.py")
    tree = ast.parse(text, filename="src/pixelscope/version.py")
    versions = [
        statement.value.value
        for statement in tree.body
        if isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id == "__version__"
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    ]
    if len(versions) != 1:
        raise ValueError("Selected tag must declare exactly one literal __version__")
    return versions[0]


def validate_publication_source(revision: str, trusted_main_sha: str) -> tuple[str, str]:
    """Verify an exact approved source before checkout, pip, or selected code."""
    if _SHA_RE.fullmatch(trusted_main_sha) is None:
        raise ValueError("Trusted main commit must be a full lowercase SHA")
    if revision != "main" and _TAG_RE.fullmatch(revision) is None:
        raise ValueError("Revision must be main or a canonical v<version> tag")

    # This script runs from checkout(ref=github.sha), not inputs.revision.
    actual_main = _git("rev-parse", "--verify", "HEAD")
    if actual_main != trusted_main_sha:
        raise ValueError("Trusted workflow checkout does not match the dispatched main SHA")

    if revision == "main":
        return trusted_main_sha, _read_committed_version(trusted_main_sha)

    source_commit = _git("rev-parse", "--verify", f"refs/tags/{revision}^{{commit}}")
    if _SHA_RE.fullmatch(source_commit) is None:
        raise ValueError("Selected tag does not resolve to a full commit SHA")

    # A tag must point to reviewed history reachable from the selected main.
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, trusted_main_sha],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    version = _read_committed_version(source_commit)
    if revision != f"v{version}":
        raise ValueError(f"Selected tag {revision} does not match source version {version}")

    # Older tags cannot silently use unreviewed/missing publication tooling.
    for path in _REQUIRED_TAG_FILES:
        _git("cat-file", "-e", f"{source_commit}:{path}")
    return source_commit, version


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a documentation publication revision before untrusted checkout"
    )
    parser.add_argument("--revision", required=True)
    parser.add_argument("--trusted-main-sha", required=True)
    parser.add_argument("--github-output", type=Path, required=True)
    args = parser.parse_args()
    source_commit, version = validate_publication_source(args.revision, args.trusted_main_sha)
    with args.github_output.open("a", encoding="utf-8") as output:
        output.write(f"source_sha={source_commit}\nversion={version}\n")
    print(f"Approved User Guide publication: {args.revision} at {source_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
