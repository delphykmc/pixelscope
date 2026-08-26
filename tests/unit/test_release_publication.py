from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import prepare_release_publication as prepare_module
from scripts import publication_contract as publication_module
from scripts import release_contract as release_contract_module
from scripts.distribution_contract import TARGET_ID, sha256_file
from scripts.release_contract import release_version, render_release_notes


def _write(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _publication_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[str, str, Path, Path]:
    version = release_version()
    commit = "a" * 40
    release_root = tmp_path / "release"
    notes_root = tmp_path / "docs" / "releases"
    notes_root.mkdir(parents=True)
    note_source = notes_root / f"2026-08-27-v{version}.md"
    note_source.write_text(
        f"# PixelScope v{version}\n\nSource commit: {{{{SOURCE_COMMIT}}}}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(publication_module, "RELEASE_ROOT", release_root)
    monkeypatch.setattr(publication_module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(release_contract_module, "RELEASE_NOTES_ROOT", notes_root)
    monkeypatch.setattr(prepare_module, "release_version", lambda: version)

    candidate = publication_module.candidate_root(version)
    candidate.mkdir(parents=True)
    artifact_names = publication_module.production_artifact_names(version)

    manifest_name = artifact_names[0]
    (candidate / manifest_name).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "PixelScope",
                "version": version,
                "target": TARGET_ID,
                "payload_root": "PixelScope",
                "files": [
                    {
                        "path": "PixelScope.exe",
                        "size": 3,
                        "sha256": "0" * 64,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    for index, name in enumerate(artifact_names[1:], start=1):
        _write(candidate / name, f"artifact-{index}".encode())

    render_release_notes(
        note_source,
        candidate / publication_module.RELEASE_NOTES_NAME,
        commit=commit,
    )
    inventory = {
        name: {
            "size": (candidate / name).stat().st_size,
            "sha256": sha256_file(candidate / name),
        }
        for name in artifact_names
    }
    (candidate / publication_module.CANDIDATE_PROVENANCE_NAME).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "PixelScope",
                "version": version,
                "source_commit": commit,
                "built_at_utc": "2026-08-27T00:00:00+00:00",
                "release_python_executable": "python.exe",
                "release_python_version": "Python 3.10.11",
                "pyinstaller_version": "5.7",
                "inno_compiler_executable": "ISCC.exe",
                "inno_compiler_major": 6,
                "inno_compiler_sha256": "1" * 64,
                "release_note_source": note_source.relative_to(tmp_path).as_posix(),
                "artifacts": inventory,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return version, commit, candidate, note_source


def _read_provenance(candidate: Path) -> tuple[Path, dict[str, object]]:
    path = candidate / publication_module.CANDIDATE_PROVENANCE_NAME
    return path, json.loads(path.read_text(encoding="utf-8"))


def test_release_tag_and_title_derive_from_canonical_version() -> None:
    version = release_version()

    assert publication_module.release_tag() == f"v{version}"
    assert publication_module.release_title() == f"PixelScope v{version}"


def test_current_release_note_uses_canonical_title_and_source_marker() -> None:
    version = release_version()
    source = release_contract_module.release_note_source(version)
    text = source.read_text(encoding="utf-8")

    assert source.name.endswith(f"-v{version}.md")
    assert text.startswith(f"# PixelScope v{version}\n")
    assert text.count(release_contract_module.SOURCE_COMMIT_MARKER) == 1


def test_prepare_publication_stages_exact_candidate_and_provider_neutral_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version, commit, candidate, note_source = _publication_fixture(tmp_path, monkeypatch)
    destination = publication_module.publication_root(version)
    destination.mkdir(parents=True)
    _write(destination / "stale.txt", b"stale")

    result = prepare_module.prepare_release_publication(current_commit=commit)

    assert result == destination.resolve()
    actual_names = {path.name for path in destination.iterdir()}
    assert actual_names == publication_module.publication_file_names(version)
    for name in publication_module.candidate_file_names(version):
        assert (destination / name).read_bytes() == (candidate / name).read_bytes()

    metadata = publication_module.validate_publication(destination, version=version)
    assert metadata["version"] == version
    assert metadata["release_tag"] == f"v{version}"
    assert metadata["release_title"] == f"PixelScope v{version}"
    assert metadata["source_commit"] == commit
    assert set(metadata["artifacts"]) == set(
        publication_module.production_artifact_names(version)
    )
    assert metadata["release_note"]["source"] == (
        note_source.relative_to(tmp_path).as_posix()
    )

    serialized = json.dumps(metadata, sort_keys=True)
    assert str(tmp_path) not in serialized
    assert "token" not in serialized.casefold()
    assert "credential" not in serialized.casefold()
    assert "github.com" not in serialized.casefold()


def test_prepare_publication_requires_current_checkout_to_match_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _version, _commit, _candidate, _note_source = _publication_fixture(tmp_path, monkeypatch)

    with pytest.raises(RuntimeError, match="exact candidate source commit"):
        prepare_module.prepare_release_publication(current_commit="b" * 40)


def test_candidate_validation_rejects_non_commit_source_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version, _commit, candidate, _note_source = _publication_fixture(tmp_path, monkeypatch)
    provenance_path, provenance = _read_provenance(candidate)
    provenance["source_commit"] = "abc123"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(
        publication_module.PublicationValidationError,
        match="full lowercase Git commit SHA",
    ):
        publication_module.validate_candidate(candidate, version=version)


def test_candidate_validation_rejects_missing_tool_provenance_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version, _commit, candidate, _note_source = _publication_fixture(tmp_path, monkeypatch)
    provenance_path, provenance = _read_provenance(candidate)
    del provenance["inno_compiler_sha256"]
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(
        publication_module.PublicationValidationError,
        match="fields mismatch.*inno_compiler_sha256",
    ):
        publication_module.validate_candidate(candidate, version=version)


def test_candidate_validation_rejects_unexpected_private_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version, _commit, candidate, _note_source = _publication_fixture(tmp_path, monkeypatch)
    provenance_path, provenance = _read_provenance(candidate)
    provenance["private_local_path"] = r"C:\Users\owner\release"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(
        publication_module.PublicationValidationError,
        match="fields mismatch.*private_local_path",
    ):
        publication_module.validate_candidate(candidate, version=version)


def test_candidate_validation_rejects_local_tool_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version, _commit, candidate, _note_source = _publication_fixture(tmp_path, monkeypatch)
    provenance_path, provenance = _read_provenance(candidate)
    provenance["inno_compiler_executable"] = r"C:\Program Files\Inno Setup 6\ISCC.exe"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(
        publication_module.PublicationValidationError,
        match="basename, not a path",
    ):
        publication_module.validate_candidate(candidate, version=version)


def test_candidate_validation_rejects_artifact_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version, _commit, candidate, _note_source = _publication_fixture(tmp_path, monkeypatch)
    artifact = candidate / publication_module.production_artifact_names(version)[1]
    artifact.write_bytes(b"tampered")

    with pytest.raises(
        publication_module.PublicationValidationError,
        match="artifact identity does not match staged file",
    ):
        publication_module.validate_candidate(candidate, version=version)


def test_candidate_validation_rejects_release_note_commit_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version, _commit, candidate, _note_source = _publication_fixture(tmp_path, monkeypatch)
    provenance_path, provenance = _read_provenance(candidate)
    provenance["source_commit"] = "c" * 40
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(
        publication_module.PublicationValidationError,
        match="rendered release notes",
    ):
        publication_module.validate_candidate(candidate, version=version)


def test_publication_validation_rejects_staged_tamper(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version, commit, _candidate, _note_source = _publication_fixture(tmp_path, monkeypatch)
    destination = prepare_module.prepare_release_publication(current_commit=commit)
    target = destination / publication_module.production_artifact_names(version)[-1]
    target.write_bytes(b"tampered")

    with pytest.raises(
        publication_module.PublicationValidationError,
        match="size mismatch|SHA-256 mismatch",
    ):
        publication_module.validate_publication(destination, version=version)


def test_release_tag_validation_requires_exact_source_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "d" * 40
    monkeypatch.setattr(
        publication_module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            stdout=f"{commit}\n",
            stderr="",
            returncode=0,
        ),
    )

    assert publication_module.validate_release_tag(commit, version="1.2.3") == commit

    with pytest.raises(
        publication_module.PublicationValidationError,
        match="points to",
    ):
        publication_module.validate_release_tag("e" * 40, version="1.2.3")


def test_release_tag_validation_rejects_missing_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise publication_module.subprocess.CalledProcessError(1, ["git"])

    monkeypatch.setattr(publication_module.subprocess, "run", fail)

    with pytest.raises(
        publication_module.PublicationValidationError,
        match="missing or invalid",
    ):
        publication_module.validate_release_tag("f" * 40, version="1.2.3")
