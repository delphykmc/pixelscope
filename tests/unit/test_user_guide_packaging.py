from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import build_release as release_module
from scripts.build_user_guide import SHIM_PATH, validate_source_shim
from scripts.release_contract import REPO_ROOT


def test_vendored_offline_search_shim_has_expected_digest() -> None:
    assert SHIM_PATH.is_file()
    validate_source_shim()


def test_release_build_embeds_help_beside_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("index", encoding="utf-8")
    (site / "404.html").write_text("hosting only", encoding="utf-8")
    vendor = site / "assets" / "vendor"
    vendor.mkdir(parents=True)
    (vendor / "iframe-worker-1.0.4.js").write_bytes(SHIM_PATH.read_bytes())
    dist_root = tmp_path / "dist"
    app_dir = dist_root / "PixelScope"
    existing_help = app_dir / "help"
    existing_help.mkdir(parents=True)
    (existing_help / "stale.txt").write_text("old", encoding="utf-8")

    calls: list[tuple[object, object]] = []

    def fake_run(command: list[str], *, cwd: Path, check: bool) -> SimpleNamespace:
        calls.append((command, cwd))
        assert check
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "PixelScope.exe").write_bytes(b"exe")
        return SimpleNamespace(returncode=0)

    def check_artifact() -> None:
        help_root = app_dir / "help"
        assert (help_root / "index.html").is_file()
        assert (help_root / "assets/vendor/iframe-worker-1.0.4.js").read_bytes() == (
            SHIM_PATH.read_bytes()
        )
        assert not (help_root / "stale.txt").exists()
        assert not (help_root / "404.html").exists()

    monkeypatch.setattr(release_module, "validate_release_host", lambda: None)
    monkeypatch.setattr(release_module, "build_user_guide", lambda *, python: site)
    monkeypatch.setattr(release_module, "write_windows_version_info", lambda: None)
    monkeypatch.setattr(release_module, "documentation_python", lambda: Path("python.exe"))
    monkeypatch.setattr(release_module, "pyinstaller_command", lambda: ["pyinstaller"])
    monkeypatch.setattr(release_module, "DIST_ROOT", dist_root)
    monkeypatch.setattr(release_module, "subprocess", SimpleNamespace(run=fake_run))
    monkeypatch.setattr(release_module, "validate_artifact", check_artifact)

    assert release_module.main() == 0
    assert calls == [(["pyinstaller"], REPO_ROOT)]


def test_inno_recursively_packages_canonical_help_tree() -> None:
    script = (REPO_ROOT / "packaging/installer/pixelscope.iss").read_text(
        encoding="utf-8"
    )
    assert 'Source: "{#AppSource}\\\\*"' in script
    assert "recursesubdirs createallsubdirs" in script
