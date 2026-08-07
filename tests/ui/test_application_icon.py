from __future__ import annotations

import ctypes
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication
from pytest import MonkeyPatch

import pixelscope.app.application as application_module
from pixelscope.app.application import create_application


def test_create_application_sets_canonical_icon() -> None:
    app = create_application([])

    assert isinstance(app, QApplication)
    icon = app.windowIcon()
    assert not icon.isNull()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        assert not icon.pixmap(size, size).isNull()


def test_windows_app_user_model_id_is_configured(monkeypatch: MonkeyPatch) -> None:
    calls: list[str] = []

    class FakeSetter:
        argtypes: object = None
        restype: object = None

        def __call__(self, app_id: str) -> int:
            calls.append(app_id)
            return 0

    setter = FakeSetter()
    shell32 = SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=setter)
    windll = SimpleNamespace(shell32=shell32)

    monkeypatch.setattr(application_module.sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "windll", windll, raising=False)

    application_module._set_windows_app_user_model_id()

    assert calls == [application_module.WINDOWS_APP_USER_MODEL_ID]
    assert setter.argtypes == [ctypes.c_wchar_p]
    assert setter.restype is ctypes.c_long
