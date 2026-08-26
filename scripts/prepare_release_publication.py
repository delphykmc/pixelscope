from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.publication_contract import (  # noqa: E402
    PUBLICATION_METADATA_NAME,
    build_publication_metadata,
    candidate_file_names,
    candidate_root,
    publication_root,
    validate_candidate,
    validate_publication,
)
from scripts.release_contract import REPO_ROOT, release_version  # noqa: E402


def _source_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        errors="replace",
        check=True,
    )
    return result.stdout.strip()


def prepare_release_publication(*, current_commit: str | None = None) -> Path:
    """Stage provider-neutral release metadata without publishing anything remotely."""

    version = release_version()
    candidate = candidate_root(version).resolve()
    provenance = validate_candidate(candidate, version=version)
    candidate_commit = str(provenance["source_commit"])
    actual_commit = current_commit or _source_commit()
    if actual_commit != candidate_commit:
        raise RuntimeError(
            "Publication preparation must run from the exact candidate source commit: "
            f"candidate={candidate_commit}, current={actual_commit}"
        )

    destination = publication_root(version).resolve()
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    for name in sorted(candidate_file_names(version)):
        shutil.copy2(candidate / name, destination / name)

    metadata = build_publication_metadata(candidate, version=version)
    (destination / PUBLICATION_METADATA_NAME).write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    validate_publication(destination, version=version)
    return destination


def main() -> int:
    destination = prepare_release_publication()
    print(f"PixelScope release publication staging PASS: {destination}")
    print("No GitHub Release, upload, tag, signing, or privileged publication was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
