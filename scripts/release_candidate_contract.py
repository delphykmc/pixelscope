from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import PurePosixPath
from typing import Final

from scripts.release_contract import EXPECTED_PYINSTALLER_VERSIONS

PROVENANCE_SCHEMA_VERSION: Final = 1
PROVENANCE_PRODUCT: Final = "PixelScope"
CANDIDATE_PROVENANCE_NAME: Final = "release-provenance.json"
_PROVENANCE_FIELDS: Final = frozenset(
    {
        "schema_version",
        "product",
        "version",
        "source_commit",
        "built_at_utc",
        "release_python_executable",
        "release_python_version",
        "pyinstaller_version",
        "inno_compiler_executable",
        "inno_compiler_major",
        "inno_compiler_sha256",
        "release_note_source",
        "artifacts",
    }
)
_ARTIFACT_FIELDS: Final = frozenset({"size", "sha256"})
_COMMIT_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_RELEASE_PYTHON_RE: Final = re.compile(r"^Python 3\.10\.(?P<micro>\d+)$")
_SUPPORTED_INNO_MAJORS: Final = frozenset({6, 7})


class CandidateProvenanceError(RuntimeError):
    """Raised when P7-C candidate provenance violates its executable schema."""


def _require_text(value: object, *, label: str, max_length: int = 512) -> str:
    if not isinstance(value, str):
        raise CandidateProvenanceError(f"{label} must be a string")
    if not value or value != value.strip():
        raise CandidateProvenanceError(f"{label} must be non-empty and trimmed")
    if len(value) > max_length or "\n" in value or "\r" in value:
        raise CandidateProvenanceError(f"{label} is not a bounded single-line value")
    return value


def _require_basename(value: object, *, label: str) -> str:
    text = _require_text(value, label=label, max_length=255)
    if text in {".", ".."} or "/" in text or "\\" in text or ":" in text:
        raise CandidateProvenanceError(
            f"{label} must be an executable basename, not a path"
        )
    return text


def _require_repo_relative(value: object, *, label: str) -> str:
    text = _require_text(value, label=label, max_length=1024)
    if "\\" in text or ":" in text:
        raise CandidateProvenanceError(
            f"{label} must be a repository-relative POSIX path"
        )
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != text:
        raise CandidateProvenanceError(
            f"{label} must be a repository-relative POSIX path"
        )
    return text


def _require_sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise CandidateProvenanceError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_source_commit(value: object) -> str:
    if not isinstance(value, str) or _COMMIT_RE.fullmatch(value) is None:
        raise CandidateProvenanceError(
            "candidate provenance source_commit must be a full lowercase Git commit SHA"
        )
    return value


def _require_utc_timestamp(value: object) -> str:
    text = _require_text(value, label="candidate provenance built_at_utc", max_length=64)
    try:
        timestamp = datetime.fromisoformat(text)
    except ValueError as exc:
        raise CandidateProvenanceError(
            "candidate provenance built_at_utc must be an ISO-8601 timestamp"
        ) from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        raise CandidateProvenanceError(
            "candidate provenance built_at_utc must identify UTC"
        )
    return text


def _require_release_python_version(value: object) -> str:
    text = _require_text(value, label="candidate provenance release_python_version")
    match = _RELEASE_PYTHON_RE.fullmatch(text)
    if match is None or int(match.group("micro")) < 8:
        raise CandidateProvenanceError(
            "candidate provenance release_python_version must be CPython "
            ">=3.10.8,<3.11"
        )
    return text


def _validate_artifacts(
    value: object,
    *,
    expected_artifacts: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    if not isinstance(value, dict):
        raise CandidateProvenanceError(
            "candidate provenance artifacts must be an object"
        )
    if set(value) != set(expected_artifacts):
        raise CandidateProvenanceError(
            "candidate provenance artifacts must contain the exact production artifact set"
        )

    normalized: dict[str, dict[str, object]] = {}
    for name, expected_entry in expected_artifacts.items():
        raw_entry = value.get(name)
        if not isinstance(raw_entry, dict) or set(raw_entry) != _ARTIFACT_FIELDS:
            raise CandidateProvenanceError(
                f"candidate provenance artifact entry is invalid: {name}"
            )
        size = raw_entry.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise CandidateProvenanceError(
                f"candidate provenance artifact size is invalid: {name}"
            )
        digest = _require_sha256(
            raw_entry.get("sha256"),
            label=f"candidate provenance artifact SHA-256 for {name}",
        )
        normalized[name] = {"size": size, "sha256": digest}
        if normalized[name] != expected_entry:
            raise CandidateProvenanceError(
                f"candidate provenance artifact identity does not match staged file: {name}"
            )
    return normalized


def validate_candidate_provenance(
    provenance: object,
    *,
    expected_version: str,
    expected_release_note_source: str,
    expected_artifacts: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Validate the exact current P7-C release-provenance schema and values."""

    if not isinstance(provenance, dict):
        raise CandidateProvenanceError("candidate provenance root must be an object")
    actual_fields = set(provenance)
    if actual_fields != _PROVENANCE_FIELDS:
        missing = sorted(_PROVENANCE_FIELDS - actual_fields)
        extra = sorted(actual_fields - _PROVENANCE_FIELDS)
        raise CandidateProvenanceError(
            f"candidate provenance fields mismatch: missing={missing}, extra={extra}"
        )
    if provenance.get("schema_version") != PROVENANCE_SCHEMA_VERSION:
        raise CandidateProvenanceError("candidate provenance schema mismatch")
    if provenance.get("product") != PROVENANCE_PRODUCT:
        raise CandidateProvenanceError("candidate provenance product mismatch")
    if provenance.get("version") != expected_version:
        raise CandidateProvenanceError("candidate provenance version mismatch")

    _require_source_commit(provenance.get("source_commit"))
    _require_utc_timestamp(provenance.get("built_at_utc"))
    _require_basename(
        provenance.get("release_python_executable"),
        label="candidate provenance release_python_executable",
    )
    _require_release_python_version(provenance.get("release_python_version"))
    pyinstaller_version = _require_text(
        provenance.get("pyinstaller_version"),
        label="candidate provenance pyinstaller_version",
    )
    if pyinstaller_version not in EXPECTED_PYINSTALLER_VERSIONS:
        raise CandidateProvenanceError(
            "candidate provenance pyinstaller_version violates the exact "
            "PyInstaller 5.7 contract"
        )
    _require_basename(
        provenance.get("inno_compiler_executable"),
        label="candidate provenance inno_compiler_executable",
    )
    inno_major = provenance.get("inno_compiler_major")
    if not isinstance(inno_major, int) or isinstance(inno_major, bool):
        raise CandidateProvenanceError(
            "candidate provenance inno_compiler_major must be an integer"
        )
    if inno_major not in _SUPPORTED_INNO_MAJORS:
        raise CandidateProvenanceError(
            "candidate provenance Inno compiler major is unsupported"
        )
    _require_sha256(
        provenance.get("inno_compiler_sha256"),
        label="candidate provenance inno_compiler_sha256",
    )
    release_note_source = _require_repo_relative(
        provenance.get("release_note_source"),
        label="candidate provenance release_note_source",
    )
    if release_note_source != expected_release_note_source:
        raise CandidateProvenanceError(
            "candidate release-note source identity mismatch"
        )
    _validate_artifacts(
        provenance.get("artifacts"),
        expected_artifacts=expected_artifacts,
    )
    return dict(provenance)


def build_candidate_provenance(
    *,
    version: str,
    source_commit: str,
    built_at_utc: str,
    release_python_executable: str,
    release_python_version: str,
    pyinstaller_version: str,
    inno_compiler_executable: str,
    inno_compiler_major: int,
    inno_compiler_sha256: str,
    release_note_source: str,
    artifacts: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Build and self-validate the canonical P7-C release provenance document."""

    provenance: dict[str, object] = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "product": PROVENANCE_PRODUCT,
        "version": version,
        "source_commit": source_commit,
        "built_at_utc": built_at_utc,
        "release_python_executable": release_python_executable,
        "release_python_version": release_python_version,
        "pyinstaller_version": pyinstaller_version,
        "inno_compiler_executable": inno_compiler_executable,
        "inno_compiler_major": inno_compiler_major,
        "inno_compiler_sha256": inno_compiler_sha256,
        "release_note_source": release_note_source,
        "artifacts": artifacts,
    }
    return validate_candidate_provenance(
        provenance,
        expected_version=version,
        expected_release_note_source=release_note_source,
        expected_artifacts=artifacts,
    )
