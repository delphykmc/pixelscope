from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import scripts.build_release_candidate as candidate
from scripts.distribution_contract import (
    installer_path,
    manifest_path,
    notice_path,
    portable_zip_path,
    release_stem,
    write_payload_manifest,
)
from scripts.validate_release_bundle import ReleaseBundleError, validate_release_bundle


def _write(path: Path, data: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _valid_bundle(tmp_path: Path, *, version: str = "1.2.3") -> tuple[Path, Path]:
    app_dir = tmp_path / "dist" / "PixelScope"
    release_root = tmp_path / "release"
    _write(app_dir / "PixelScope.exe", b"exe")
    _write(app_dir / "nested" / "runtime.dll", b"runtime")

    write_payload_manifest(
        app_dir,
        destination=release_root / manifest_path(version).name,
        version=version,
    )
    _write(release_root / notice_path(version).name, b"notices")
    _write(release_root / portable_zip_path(version).name, b"zip")
    _write(release_root / installer_path(version).name, b"setup")
    return release_root, app_dir


def test_release_bundle_accepts_exact_production_set(tmp_path: Path) -> None:
    release_root, app_dir = _valid_bundle(tmp_path)

    paths = validate_release_bundle(release_root, app_dir, version="1.2.3")

    assert {path.name for path in paths} == {
        manifest_path("1.2.3").name,
        notice_path("1.2.3").name,
        portable_zip_path("1.2.3").name,
        installer_path("1.2.3").name,
    }


def test_release_bundle_rejects_missing_or_extra_files(tmp_path: Path) -> None:
    release_root, app_dir = _valid_bundle(tmp_path)
    installer = release_root / installer_path("1.2.3").name
    installer.unlink()

    with pytest.raises(ReleaseBundleError, match="missing files"):
        validate_release_bundle(release_root, app_dir, version="1.2.3")

    _write(installer, b"setup")
    _write(release_root / "unexpected.txt")
    with pytest.raises(ReleaseBundleError, match="unexpected files"):
        validate_release_bundle(release_root, app_dir, version="1.2.3")


def test_release_bundle_rejects_disposable_smoke_setup(tmp_path: Path) -> None:
    release_root, app_dir = _valid_bundle(tmp_path)
    smoke_setup = release_root / f"{release_stem('1.2.3')}-smoke-setup.exe"
    _write(smoke_setup, b"smoke")

    with pytest.raises(ReleaseBundleError, match="disposable smoke installer"):
        validate_release_bundle(release_root, app_dir, version="1.2.3")


def test_release_bundle_rejects_manifest_payload_drift(tmp_path: Path) -> None:
    release_root, app_dir = _valid_bundle(tmp_path)
    (app_dir / "nested" / "runtime.dll").write_bytes(b"tampered")

    with pytest.raises(RuntimeError, match="size mismatch|SHA-256 mismatch"):
        validate_release_bundle(release_root, app_dir, version="1.2.3")


def test_render_release_notes_replaces_exact_source_commit(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    destination = tmp_path / "rendered.md"
    source.write_text("Version note\nSource commit: `{{SOURCE_COMMIT}}`\n", encoding="utf-8")

    candidate._render_release_notes(source, destination, commit="abc123")

    assert destination.read_text(encoding="utf-8") == (
        "Version note\nSource commit: `abc123`\n"
    )


def test_stage_candidate_copies_exact_artifacts_and_records_safe_provenance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    version = "1.2.3"
    commit = "abc123def456"
    repo_root = tmp_path / "repo"
    release_root = repo_root / "release"
    source_root = tmp_path / "validated"
    release_python = tmp_path / "private" / "release-env" / "python.exe"
    compiler = tmp_path / "private" / "tools" / "ISCC.exe"

    artifact_payloads = {
        manifest_path(version).name: b"manifest-bytes",
        notice_path(version).name: b"notice-bytes",
        portable_zip_path(version).name: b"portable-bytes",
        installer_path(version).name: b"installer-bytes",
    }
    artifacts = tuple(
        _write(source_root / name, payload) for name, payload in artifact_payloads.items()
    )
    _write(compiler, b"inno-compiler")

    notes_source = repo_root / "docs" / "releases" / "2026-08-26-v1.2.3.md"
    _write(
        notes_source,
        b"# PixelScope 1.2.3\n\nSource commit: `{{SOURCE_COMMIT}}`\n",
    )

    stage_root = release_root / "candidate" / release_stem(version)
    _write(stage_root / "stale.txt", b"stale")

    def fake_capture(command: list[str], *, env: dict[str, str] | None = None) -> str:
        del env
        if "PyInstaller" in command:
            return "5.7"
        if command[-1] == "--version":
            return "Python 3.10.11"
        raise AssertionError(f"unexpected capture command: {command}")

    monkeypatch.setattr(candidate, "REPO_ROOT", repo_root)
    monkeypatch.setattr(candidate, "RELEASE_ROOT", release_root)
    monkeypatch.setattr(candidate, "_capture", fake_capture)
    monkeypatch.setattr(candidate, "inno_major_version", lambda path: 6)

    staged = candidate._stage_candidate(
        artifacts,
        version=version,
        commit=commit,
        release_python=release_python,
        compiler=compiler,
    )

    assert staged == stage_root
    assert {path.name for path in stage_root.iterdir()} == {
        *artifact_payloads,
        "RELEASE_NOTES.md",
        "release-provenance.json",
    }
    assert not (stage_root / "stale.txt").exists()

    for name, payload in artifact_payloads.items():
        staged_path = stage_root / name
        assert staged_path.read_bytes() == payload

    rendered_notes = (stage_root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert commit in rendered_notes
    assert "{{SOURCE_COMMIT}}" not in rendered_notes

    provenance_path = stage_root / "release-provenance.json"
    provenance_text = provenance_path.read_text(encoding="utf-8")
    provenance = json.loads(provenance_text)

    assert provenance["schema_version"] == 1
    assert provenance["product"] == "PixelScope"
    assert provenance["version"] == version
    assert provenance["source_commit"] == commit
    assert provenance["release_python_executable"] == "python.exe"
    assert provenance["release_python_version"] == "Python 3.10.11"
    assert provenance["pyinstaller_version"] == "5.7"
    assert provenance["inno_compiler_executable"] == "ISCC.exe"
    assert provenance["inno_compiler_major"] == 6
    assert provenance["inno_compiler_sha256"] == hashlib.sha256(
        b"inno-compiler"
    ).hexdigest()
    assert provenance["release_note_source"] == "docs/releases/2026-08-26-v1.2.3.md"

    for name, payload in artifact_payloads.items():
        assert provenance["artifacts"][name] == {
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    assert str(release_python) not in provenance_text
    assert str(compiler) not in provenance_text
    assert str(tmp_path) not in provenance_text


def test_release_pipeline_reuses_existing_p7_scripts_and_one_compiler(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    release_python = tmp_path / "python.exe"
    compiler = tmp_path / "ISCC.exe"
    commands: list[tuple[list[str], dict[str, str] | None]] = []

    def record(command: list[str], *, env: dict[str, str] | None = None) -> None:
        commands.append((command, env))

    expected = (tmp_path / "setup.exe",)
    monkeypatch.setattr(candidate, "_run", record)
    monkeypatch.setattr(candidate, "validate_release_bundle", lambda: expected)

    assert candidate._run_release_pipeline(release_python, compiler) == expected

    scripts = [
        command[1]
        for command, _ in commands
        if len(command) > 1 and command[1].endswith(".py")
    ]
    assert scripts == [
        "scripts/build_release.py",
        "scripts/validate_release_artifact.py",
        "scripts/smoke_packaged_release.py",
        "scripts/build_portable_release.py",
        "scripts/smoke_portable_release.py",
        "scripts/build_installer_release.py",
        "scripts/smoke_installer_release.py",
        "scripts/validate_release_bundle.py",
    ]
    installer_command = next(
        command for command, _ in commands if "scripts/build_installer_release.py" in command
    )
    assert installer_command[-2:] == ["--iscc", str(compiler)]
    assert all(
        env is not None and env["ISCC_PATH"] == str(compiler) for _, env in commands
    )


def test_require_clean_worktree_rejects_dirty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(candidate, "_capture", lambda command: " M tracked.py")

    with pytest.raises(RuntimeError, match="clean source worktree"):
        candidate._require_clean_worktree()


def test_release_note_source_is_dated_versioned_and_has_commit_marker() -> None:
    source = candidate._release_note_source("0.1.0")

    assert source.name == "2026-08-26-v0.1.0.md"
    assert "{{SOURCE_COMMIT}}" in source.read_text(encoding="utf-8")
