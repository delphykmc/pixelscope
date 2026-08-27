from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Final

if __package__ in (None, ""):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.distribution_contract import (  # noqa: E402
    RELEASE_ROOT,
    TARGET_ID,
    installer_path,
    load_payload_manifest,
    manifest_path,
    notice_path,
    portable_zip_path,
    release_stem,
    sha256_file,
)
from scripts.release_candidate_contract import (  # noqa: E402
    CANDIDATE_PROVENANCE_NAME,
    CandidateProvenanceError,
    validate_candidate_provenance,
)
from scripts.release_contract import (  # noqa: E402
    REPO_ROOT,
    SOURCE_COMMIT_MARKER,
    release_note_source,
    release_version,
    render_release_note_text,
)

PUBLICATION_SCHEMA_VERSION: Final = 1
PRODUCT_NAME: Final = "PixelScope"
RELEASE_NOTES_NAME: Final = "RELEASE_NOTES.md"
PUBLICATION_METADATA_NAME: Final = "release-publication.json"
_DATE_NOTE_RE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}-v(?P<version>.+)\.md$")
_COMMIT_RE: Final = re.compile(r"^[0-9a-f]{40}$")


class PublicationValidationError(RuntimeError):
    """Raised when release publication staging violates the canonical contract."""


def release_tag(version: str | None = None) -> str:
    return f"v{version or release_version()}"


def release_title(version: str | None = None) -> str:
    return f"PixelScope {release_tag(version)}"


def candidate_root(version: str | None = None) -> Path:
    return RELEASE_ROOT / "candidate" / release_stem(version)


def publication_root(version: str | None = None) -> Path:
    return RELEASE_ROOT / "publication" / release_stem(version)


def production_artifact_names(version: str | None = None) -> tuple[str, ...]:
    value = version or release_version()
    return (
        manifest_path(value).name,
        notice_path(value).name,
        portable_zip_path(value).name,
        installer_path(value).name,
    )


def candidate_file_names(version: str | None = None) -> frozenset[str]:
    return frozenset(
        {
            *production_artifact_names(version),
            RELEASE_NOTES_NAME,
            CANDIDATE_PROVENANCE_NAME,
        }
    )


def publication_file_names(version: str | None = None) -> frozenset[str]:
    return candidate_file_names(version) | {PUBLICATION_METADATA_NAME}


def _load_json_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationValidationError(f"{label} is unreadable: {path.name}") from exc
    if not isinstance(value, dict):
        raise PublicationValidationError(f"{label} root must be an object")
    return value


def _require_exact_files(root: Path, expected: frozenset[str], *, label: str) -> None:
    if not root.is_dir():
        raise PublicationValidationError(f"{label} directory is missing: {root}")
    actual = {path.name for path in root.iterdir() if path.is_file()}
    directories = sorted(path.name for path in root.iterdir() if path.is_dir())
    if directories:
        raise PublicationValidationError(
            f"{label} contains unexpected directories: {directories}"
        )
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise PublicationValidationError(f"{label} is missing files: {missing}")
    if extra:
        raise PublicationValidationError(f"{label} contains unexpected files: {extra}")
    empty = sorted(name for name in expected if (root / name).stat().st_size <= 0)
    if empty:
        raise PublicationValidationError(f"{label} contains empty files: {empty}")


def _artifact_inventory(root: Path, names: tuple[str, ...]) -> dict[str, dict[str, object]]:
    return {
        name: {
            "size": (root / name).stat().st_size,
            "sha256": sha256_file(root / name),
        }
        for name in names
    }


def _validate_release_note_source(version: str) -> Path:
    try:
        source = release_note_source(version)
    except RuntimeError as exc:
        raise PublicationValidationError(str(exc)) from exc
    match = _DATE_NOTE_RE.match(source.name)
    if match is None or match.group("version") != version:
        raise PublicationValidationError(
            f"release-note filename does not identify v{version}: {source.name}"
        )
    text = source.read_text(encoding="utf-8")
    if not text.startswith(f"# {release_title(version)}\n"):
        raise PublicationValidationError(
            f"release-note title must be '# {release_title(version)}'"
        )
    if text.count(SOURCE_COMMIT_MARKER) != 1:
        raise PublicationValidationError(
            "release-note source must contain exactly one source-commit marker"
        )
    return source


def _validate_source_commit(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _COMMIT_RE.fullmatch(value) is None:
        raise PublicationValidationError(f"{label} must be a full lowercase Git commit SHA")
    return value


def validate_candidate(
    root: Path | None = None,
    *,
    version: str | None = None,
) -> dict[str, object]:
    """Validate the P7-C candidate as the sole P7-D Stage 1 input authority."""

    value = version or release_version()
    stage = (root or candidate_root(value)).resolve()
    _require_exact_files(stage, candidate_file_names(value), label="release candidate")

    provenance_path = stage / CANDIDATE_PROVENANCE_NAME
    provenance = _load_json_object(provenance_path, label="candidate provenance")
    source = _validate_release_note_source(value)
    expected_source = source.relative_to(REPO_ROOT).as_posix()
    artifact_names = production_artifact_names(value)
    expected_inventory = _artifact_inventory(stage, artifact_names)
    try:
        provenance = validate_candidate_provenance(
            provenance,
            expected_version=value,
            expected_release_note_source=expected_source,
            expected_artifacts=expected_inventory,
        )
    except CandidateProvenanceError as exc:
        raise PublicationValidationError(str(exc)) from exc
    source_commit = str(provenance["source_commit"])

    manifest = load_payload_manifest(stage / manifest_path(value).name)
    if manifest.get("schema_version") != 1:
        raise PublicationValidationError("candidate payload manifest schema mismatch")
    if manifest.get("product") != PRODUCT_NAME:
        raise PublicationValidationError("candidate payload manifest product mismatch")
    if manifest.get("target") != TARGET_ID:
        raise PublicationValidationError("candidate payload manifest target mismatch")
    if manifest.get("version") != value:
        raise PublicationValidationError("candidate payload manifest version mismatch")

    rendered_path = stage / RELEASE_NOTES_NAME
    rendered = rendered_path.read_text(encoding="utf-8")
    if SOURCE_COMMIT_MARKER in rendered:
        raise PublicationValidationError("rendered release notes retain source-commit marker")
    expected_rendered = render_release_note_text(source, commit=source_commit)
    if rendered != expected_rendered:
        raise PublicationValidationError(
            "rendered release notes do not match durable source and candidate commit"
        )

    return provenance


def build_publication_metadata(
    root: Path | None = None,
    *,
    version: str | None = None,
) -> dict[str, object]:
    value = version or release_version()
    stage = (root or candidate_root(value)).resolve()
    provenance = validate_candidate(stage, version=value)
    source = _validate_release_note_source(value)
    artifact_names = production_artifact_names(value)

    return {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "product": PRODUCT_NAME,
        "version": value,
        "target": TARGET_ID,
        "release_tag": release_tag(value),
        "release_title": release_title(value),
        "source_commit": provenance["source_commit"],
        "release_note": {
            "source": source.relative_to(REPO_ROOT).as_posix(),
            "source_sha256": sha256_file(source),
            "rendered_filename": RELEASE_NOTES_NAME,
            "rendered_sha256": sha256_file(stage / RELEASE_NOTES_NAME),
        },
        "candidate_provenance": {
            "filename": CANDIDATE_PROVENANCE_NAME,
            "sha256": sha256_file(stage / CANDIDATE_PROVENANCE_NAME),
        },
        "artifacts": _artifact_inventory(stage, artifact_names),
    }


def validate_publication(
    root: Path | None = None,
    *,
    version: str | None = None,
) -> dict[str, object]:
    value = version or release_version()
    published = (root or publication_root(value)).resolve()
    _require_exact_files(
        published,
        publication_file_names(value),
        label="release publication staging",
    )

    candidate = candidate_root(value).resolve()
    expected_metadata = build_publication_metadata(candidate, version=value)
    actual_metadata = _load_json_object(
        published / PUBLICATION_METADATA_NAME,
        label="publication metadata",
    )
    if actual_metadata != expected_metadata:
        raise PublicationValidationError(
            "publication metadata does not match canonical candidate identity"
        )

    for name in candidate_file_names(value):
        candidate_path = candidate / name
        published_path = published / name
        if candidate_path.stat().st_size != published_path.stat().st_size:
            raise PublicationValidationError(f"publication file size mismatch: {name}")
        if sha256_file(candidate_path) != sha256_file(published_path):
            raise PublicationValidationError(f"publication file SHA-256 mismatch: {name}")

    return actual_metadata


def resolve_tag_commit(tag: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise PublicationValidationError(f"release tag is missing or invalid: {tag}") from exc
    commit = result.stdout.strip()
    return _validate_source_commit(commit, label=f"release tag {tag} commit")


def validate_release_tag(
    source_commit: str,
    *,
    version: str | None = None,
) -> str:
    expected_commit = _validate_source_commit(source_commit, label="expected source_commit")
    tag = release_tag(version)
    tag_commit = resolve_tag_commit(tag)
    if tag_commit != expected_commit:
        raise PublicationValidationError(
            f"release tag {tag} points to {tag_commit}, expected {expected_commit}"
        )
    return tag_commit
