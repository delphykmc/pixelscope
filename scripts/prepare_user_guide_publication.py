from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Final

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_user_guide import build_user_guide  # noqa: E402
from scripts.check_user_guide_site import find_site_problems  # noqa: E402
from scripts.distribution_contract import sha256_file  # noqa: E402
from scripts.release_contract import REPO_ROOT, release_version  # noqa: E402

STAGING_ROOT: Final = REPO_ROOT / "build" / "user-guide-publication"
METADATA_NAME: Final = "publication.json"
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}")


def validate_selected_revision(
    revision: str, *, version: str, source_commit: str, ref_commit: str
) -> None:
    """Require exactly main or the canonical release tag at the checked-out commit."""
    if revision not in {"main", f"v{version}"}:
        raise ValueError(
            f"Documentation revision must be main or the canonical tag v{version}: {revision!r}"
        )
    if _COMMIT_RE.fullmatch(source_commit) is None:
        raise ValueError("Documentation source commit must be a full lowercase SHA")
    if source_commit != ref_commit:
        raise ValueError(
            f"Documentation checkout {source_commit} does not match {revision}: {ref_commit}"
        )


def _git_rev_parse(ref: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def resolved_revision_commit(revision: str, version: str) -> str:
    if revision == "main":
        # Checkout may be detached in CI. In local clones refs/heads/main also works.
        for ref in ("refs/remotes/origin/main^{commit}", "refs/heads/main^{commit}"):
            try:
                return _git_rev_parse(ref)
            except subprocess.CalledProcessError:
                continue
        raise RuntimeError("Cannot resolve main to verify documentation publication")
    if revision == f"v{version}":
        return _git_rev_parse(f"refs/tags/{revision}^{{commit}}")
    raise ValueError("Unsupported documentation publication revision")


def build_publication_manifest(
    site: Path, *, revision: str, version: str, source_commit: str
) -> dict[str, object]:
    files = sorted(
        (path for path in site.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(site).as_posix(),
    )
    return {
        "schema_version": 1,
        "product": "PixelScope User Guide",
        "version": version,
        "source_ref": revision,
        "source_commit": source_commit,
        "site_root": "site",
        "files": [
            {
                "path": path.relative_to(site).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }


def validate_publication_manifest(site: Path, metadata: dict[str, object]) -> None:
    version = metadata.get("version")
    revision = metadata.get("source_ref")
    source_commit = metadata.get("source_commit")
    if not all(isinstance(item, str) for item in (version, revision, source_commit)):
        raise ValueError("Invalid User Guide publication identity")
    if metadata != build_publication_manifest(
        site, revision=revision, version=version, source_commit=source_commit
    ):
        raise ValueError("User Guide publication file inventory/identity mismatch")
    problems = find_site_problems(site)
    if problems:
        raise ValueError("Invalid User Guide site:\n - " + "\n - ".join(problems))


def prepare_publication(
    revision: str,
    *,
    destination: Path = STAGING_ROOT,
    expected_commit: str | None = None,
) -> Path:
    version = release_version()
    source_commit = _git_rev_parse("HEAD")
    # For main, the preflight pins the dispatched main SHA: origin/main could
    # advance before this build. For a tag, also recheck the actual tag target.
    ref_commit = (
        expected_commit
        if revision == "main" and expected_commit is not None
        else resolved_revision_commit(revision, version)
    )
    validate_selected_revision(
        revision,
        version=version,
        source_commit=source_commit,
        ref_commit=ref_commit,
    )
    if expected_commit is not None and source_commit != expected_commit:
        raise ValueError("Checked-out documentation source differs from preflight commit")
    site = build_user_guide()
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    published_site = destination / "site"
    shutil.copytree(site, published_site)
    metadata = build_publication_manifest(
        published_site, revision=revision, version=version, source_commit=source_commit
    )
    validate_publication_manifest(published_site, metadata)
    (destination / METADATA_NAME).write_text(
        json.dumps(metadata, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare validated static User Guide for hosting")
    parser.add_argument("--revision", required=True, help="main or exact canonical v<version> tag")
    parser.add_argument("--expected-commit", help="SHA approved by trusted workflow preflight")
    args = parser.parse_args()
    root = prepare_publication(args.revision, expected_commit=args.expected_commit)
    print(f"User Guide publication staged: {root}")
    print(f"Site root: {root / 'site'}")
    print(f"Provenance: {root / METADATA_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
