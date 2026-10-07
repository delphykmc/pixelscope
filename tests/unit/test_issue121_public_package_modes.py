from __future__ import annotations

from pathlib import Path

from scripts import build_release
from scripts.release_contract import (
    APP_DIR,
    REFERENCE_APP_DIR,
    REFERENCE_SPEC_PATH,
    SPEC_PATH,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_exposes_distinct_core_and_reference_launchers() -> None:
    pyproject = (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'pixelscope = "pixelscope.app.application:main"' in pyproject
    assert 'pixelscope-reference = "pixelscope_iqa_reference.application:main"' in pyproject


def test_pyinstaller_specs_keep_public_package_modes_explicit() -> None:
    core = SPEC_PATH.read_text(encoding="utf-8")
    reference = REFERENCE_SPEC_PATH.read_text(encoding="utf-8")

    assert 'source_root / "pixelscope" / "__main__.py"' in core
    assert '"pixelscope_iqa_reference"' in core
    assert '"pixelscope_enterprise"' in core

    assert 'source_root / "pixelscope_iqa_reference" / "__main__.py"' in reference
    assert 'name="PixelScopeReference"' in reference
    assert '"pixelscope_enterprise"' in reference


def test_release_builder_selects_core_by_default_and_reference_explicitly() -> None:
    core_spec, core_dir, core_executable = build_release._target_paths("core")
    reference_spec, reference_dir, reference_executable = build_release._target_paths("reference")

    assert core_spec == SPEC_PATH
    assert core_dir == APP_DIR
    assert core_executable == "PixelScope.exe"
    assert str(SPEC_PATH) == build_release.pyinstaller_command()[-1]

    assert reference_spec == REFERENCE_SPEC_PATH
    assert reference_dir == REFERENCE_APP_DIR
    assert reference_executable == "PixelScopeReference.exe"
    assert str(REFERENCE_SPEC_PATH) == build_release.pyinstaller_command("reference")[-1]
