from __future__ import annotations

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

    scripts = [command[1] for command, _ in commands if len(command) > 1 and command[1].endswith(".py")]
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
    assert all(env is not None and env["ISCC_PATH"] == str(compiler) for _, env in commands)


def test_release_note_source_is_dated_versioned_and_has_commit_marker() -> None:
    source = candidate._release_note_source("0.1.0")

    assert source.name == "2026-08-26-v0.1.0.md"
    assert "{{SOURCE_COMMIT}}" in source.read_text(encoding="utf-8")
