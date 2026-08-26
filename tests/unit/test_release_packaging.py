from __future__ import annotations

import ctypes
import runpy
import sys
from ctypes import wintypes
from pathlib import Path

import pytest

import pixelscope
import pixelscope.app.resources as resources_module
from pixelscope.version import __version__
from scripts.build_release import pyinstaller_command
from scripts.release_contract import (
    BUILD_ROOT,
    GENERATED_ROOT,
    REPO_ROOT,
    release_version,
    render_windows_version_info,
    validate_release_python,
    windows_version_tuple,
)
from scripts.smoke_packaged_release import _configure_user32
from scripts.validate_release_artifact import ArtifactValidationError, validate_artifact


def _write(path: Path, data: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _valid_artifact(root: Path) -> Path:
    _write(root / "PixelScope.exe")
    for name in ("pixelscope.svg", "pixelscope.png", "pixelscope.ico"):
        _write(root / "pixelscope" / "assets" / "icons" / name)
    _write(root / "python310.dll")
    _write(root / "PySide6" / "QtCore.pyd")
    _write(root / "PySide6" / "QtGui.pyd")
    _write(root / "PySide6" / "QtWidgets.pyd")
    _write(root / "PySide6" / "Qt" / "plugins" / "platforms" / "qwindows.dll")
    _write(root / "numpy" / "core" / "_multiarray_umath.cp310-win_amd64.pyd")
    _write(root / "cv2" / "cv2.cp310-win_amd64.pyd")
    return root


class _MissingIconResource:
    def joinpath(self, _part: str) -> _MissingIconResource:
        return self

    def read_bytes(self) -> bytes:
        raise OSError("missing packaged icon")


def test_release_version_has_one_authority() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_section = pyproject.split("[project]", 1)[1].split("\n[", 1)[0]

    assert __version__
    assert pixelscope.__version__ == __version__
    assert release_version() == __version__
    assert windows_version_tuple(__version__)
    assert 'dynamic = ["version"]' in project_section
    assert "\nversion =" not in project_section
    assert 'version = {attr = "pixelscope.version.__version__"}' in pyproject


def test_windows_version_info_derives_from_canonical_value() -> None:
    rendered = render_windows_version_info("1.2.3rc1")

    assert windows_version_tuple("1.2.3rc1") == (1, 2, 3, 0)
    assert "filevers=(1, 2, 3, 0)" in rendered
    assert 'StringStruct("FileVersion", "1.2.3rc1")' in rendered
    assert 'StringStruct("ProductVersion", "1.2.3rc1")' in rendered


def test_windows_version_tuple_rejects_invalid_or_oversized_values() -> None:
    with pytest.raises(ValueError, match="X.Y.Z"):
        windows_version_tuple("dev")
    with pytest.raises(ValueError, match="65535"):
        windows_version_tuple("70000.1.2")


def test_release_python_baseline_is_3_10_8_or_newer_within_3_10() -> None:
    validate_release_python((3, 10, 8))
    validate_release_python((3, 10, 15))

    with pytest.raises(RuntimeError, match=">=3.10.8,<3.11"):
        validate_release_python((3, 10, 7))
    with pytest.raises(RuntimeError, match=">=3.10.8,<3.11"):
        validate_release_python((3, 11, 0))


def test_release_requirements_keep_pyinstaller_out_of_runtime() -> None:
    release = (REPO_ROOT / "requirements" / "release.txt").read_text(encoding="utf-8")
    runtime = (REPO_ROOT / "requirements" / "runtime.txt").read_text(encoding="utf-8")
    dev = (REPO_ROOT / "requirements" / "dev.txt").read_text(encoding="utf-8")

    assert "-r runtime.txt" in release
    assert "PyInstaller==5.7" in release
    assert "pyinstaller-hooks-contrib==2022.14" in release
    assert "PyInstaller" not in runtime
    assert "PyInstaller" not in dev


def test_release_scripts_support_repo_root_file_execution_imports() -> None:
    for script_name in (
        "build_release.py",
        "validate_release_artifact.py",
        "smoke_packaged_release.py",
    ):
        namespace = runpy.run_path(str(REPO_ROOT / "scripts" / script_name))
        assert "main" in namespace


def test_frozen_application_requires_packaged_icon_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resources_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(resources_module, "files", lambda _package: _MissingIconResource())

    with pytest.raises(RuntimeError, match="application icon resource is unavailable"):
        resources_module.load_application_icon()


def test_source_application_keeps_missing_icon_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(resources_module.sys, "frozen", raising=False)
    monkeypatch.setattr(resources_module, "files", lambda _package: _MissingIconResource())

    assert resources_module.load_application_icon().isNull()


def test_win32_smoke_uses_pointer_width_safe_handle_signatures() -> None:
    class FakeFunction:
        argtypes: object = None
        restype: object = None

    class FakeUser32:
        EnumWindows = FakeFunction()
        GetWindowThreadProcessId = FakeFunction()
        IsWindowVisible = FakeFunction()
        GetWindowTextLengthW = FakeFunction()
        GetWindowTextW = FakeFunction()
        PostMessageW = FakeFunction()

    enum_proc_type = object()
    user32 = FakeUser32()

    _configure_user32(user32, enum_proc_type)

    assert user32.EnumWindows.argtypes == [enum_proc_type, wintypes.LPARAM]
    assert user32.GetWindowThreadProcessId.argtypes == [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    assert user32.IsWindowVisible.argtypes == [wintypes.HWND]
    assert user32.GetWindowTextLengthW.argtypes == [wintypes.HWND]
    assert user32.GetWindowTextW.argtypes == [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    assert user32.PostMessageW.argtypes == [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]


def test_spec_is_canonical_windowed_onedir_without_collect_all() -> None:
    spec = (REPO_ROOT / "packaging" / "pixelscope.spec").read_text(encoding="utf-8")

    assert '"__main__.py"' in spec
    assert "COLLECT(" in spec
    assert "exclude_binaries=True" in spec
    assert "console=False" in spec
    assert "upx=False" in spec
    assert "datas=icon_data" in spec
    assert '"pixelscope.svg"' in spec
    assert '"pixelscope.png"' in spec
    assert '"pixelscope.ico"' in spec
    assert 'icon=str(icon_root / "pixelscope.ico")' in spec
    assert "version=str(version_info)" in spec
    assert "collect_all" not in spec
    assert "onefile" not in spec.casefold()


def test_build_command_is_argument_list_with_fixed_output_roots() -> None:
    command = pyinstaller_command()

    assert command[:3] == [sys.executable, "-m", "PyInstaller"]
    assert "--clean" in command
    assert "--noconfirm" in command
    assert command[command.index("--distpath") + 1] == str(REPO_ROOT / "dist")
    assert command[command.index("--workpath") + 1] == str(BUILD_ROOT)
    assert command[-1] == str(REPO_ROOT / "packaging" / "pixelscope.spec")
    assert GENERATED_ROOT == REPO_ROOT / "build" / "release"


def test_artifact_validator_accepts_expected_onedir_shape(tmp_path: Path) -> None:
    root = _valid_artifact(tmp_path / "PixelScope")

    validate_artifact(root)


def test_artifact_validator_requires_windows_qt_plugin(tmp_path: Path) -> None:
    root = _valid_artifact(tmp_path / "PixelScope")
    (root / "PySide6" / "Qt" / "plugins" / "platforms" / "qwindows.dll").unlink()

    with pytest.raises(ArtifactValidationError, match="Qt Windows platform plugin"):
        validate_artifact(root)


def test_artifact_validator_rejects_source_tree_leakage(tmp_path: Path) -> None:
    root = _valid_artifact(tmp_path / "PixelScope")
    (root / "tests").mkdir()

    with pytest.raises(ArtifactValidationError, match="forbidden source/dev"):
        validate_artifact(root)
