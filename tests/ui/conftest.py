from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from pixelscope.ui.display_gain import display_gain_state


def _configure_isolated_qsettings(path: Path, *, sync: bool) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(path))
    settings = QSettings()
    settings.clear()
    if sync:
        settings.sync()


@pytest.fixture()
def isolated_qsettings(tmp_path: Path) -> None:
    """Start a test with empty user-scope INI settings under its temp path."""
    _configure_isolated_qsettings(tmp_path, sync=False)


@pytest.fixture()
def isolated_synced_qsettings(tmp_path: Path) -> None:
    """Start a test with empty, flushed user-scope INI settings."""
    _configure_isolated_qsettings(tmp_path, sync=True)


@pytest.fixture()
def isolated_qsettings_subdirectory(tmp_path: Path) -> None:
    """Keep settings separate from other artifacts created below tmp_path."""
    _configure_isolated_qsettings(tmp_path / "settings", sync=False)


@pytest.fixture(autouse=True)
def reset_display_gain_for_p3d_input_policy(request: pytest.FixtureRequest) -> Iterator[None]:
    """Isolate P3-D input-policy gain mutation without touching unrelated UI tests."""

    if request.path.name != "test_p3d_input_policy.py":
        yield
        return
    state = display_gain_state()
    state.set_gain(1.0)
    try:
        yield
    finally:
        state.set_gain(1.0)
