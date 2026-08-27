from __future__ import annotations

import pytest
from scripts.release_candidate_contract import (
    CandidateProvenanceError,
    validate_candidate_provenance,
)


def _valid_provenance() -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    expected_artifacts = {
        "PixelScope-1.2.3-windows-x64.manifest.json": {
            "size": 10,
            "sha256": "1" * 64,
        }
    }
    provenance_artifacts = {
        name: dict(entry) for name, entry in expected_artifacts.items()
    }
    provenance: dict[str, object] = {
        "schema_version": 1,
        "product": "PixelScope",
        "version": "1.2.3",
        "source_commit": "a" * 40,
        "built_at_utc": "2026-08-27T00:00:00+00:00",
        "release_python_executable": "python.exe",
        "release_python_version": "Python 3.10.11",
        "pyinstaller_version": "5.7",
        "inno_compiler_executable": "ISCC.exe",
        "inno_compiler_major": 6,
        "inno_compiler_sha256": "2" * 64,
        "release_note_source": "docs/releases/2026-08-27-v1.2.3.md",
        "artifacts": provenance_artifacts,
    }
    return provenance, expected_artifacts


def _validate(
    provenance: dict[str, object],
    artifacts: dict[str, dict[str, object]],
) -> None:
    validate_candidate_provenance(
        provenance,
        expected_version="1.2.3",
        expected_release_note_source="docs/releases/2026-08-27-v1.2.3.md",
        expected_artifacts=artifacts,
    )


def test_candidate_provenance_accepts_exact_current_schema() -> None:
    provenance, artifacts = _valid_provenance()

    _validate(provenance, artifacts)


def test_candidate_provenance_rejects_missing_and_unknown_fields() -> None:
    provenance, artifacts = _valid_provenance()
    del provenance["inno_compiler_sha256"]

    with pytest.raises(CandidateProvenanceError, match="fields mismatch"):
        _validate(provenance, artifacts)

    provenance, artifacts = _valid_provenance()
    provenance["private_local_path"] = r"C:\Users\owner\release"

    with pytest.raises(CandidateProvenanceError, match="fields mismatch"):
        _validate(provenance, artifacts)


def test_candidate_provenance_rejects_local_paths_in_identity_fields() -> None:
    provenance, artifacts = _valid_provenance()
    provenance["release_python_executable"] = r"C:\private\python.exe"

    with pytest.raises(CandidateProvenanceError, match="basename, not a path"):
        _validate(provenance, artifacts)

    provenance, artifacts = _valid_provenance()
    provenance["release_note_source"] = r"C:\private\release-notes.md"

    with pytest.raises(CandidateProvenanceError, match="repository-relative POSIX path"):
        _validate(provenance, artifacts)


def test_candidate_provenance_rejects_non_release_python_version() -> None:
    provenance, artifacts = _valid_provenance()
    provenance["release_python_version"] = r"C:\private\Python 3.10.11"

    with pytest.raises(CandidateProvenanceError, match="CPython >=3.10.8,<3.11"):
        _validate(provenance, artifacts)

    provenance, artifacts = _valid_provenance()
    provenance["release_python_version"] = "Python 3.10.7"

    with pytest.raises(CandidateProvenanceError, match="CPython >=3.10.8,<3.11"):
        _validate(provenance, artifacts)


def test_candidate_provenance_rejects_noncanonical_hash_and_artifact_identity() -> None:
    provenance, artifacts = _valid_provenance()
    provenance["inno_compiler_sha256"] = "A" * 64

    with pytest.raises(CandidateProvenanceError, match="lowercase SHA-256"):
        _validate(provenance, artifacts)

    provenance, artifacts = _valid_provenance()
    raw_artifacts = provenance["artifacts"]
    assert isinstance(raw_artifacts, dict)
    entry = raw_artifacts["PixelScope-1.2.3-windows-x64.manifest.json"]
    assert isinstance(entry, dict)
    entry["size"] = 11

    with pytest.raises(CandidateProvenanceError, match="does not match staged file"):
        _validate(provenance, artifacts)
