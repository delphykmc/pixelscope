from __future__ import annotations

from PySide6.QtWidgets import QApplication

from pixelscope.app.application import create_application


def test_create_application_sets_canonical_icon() -> None:
    app = create_application([])

    assert isinstance(app, QApplication)
    icon = app.windowIcon()
    assert not icon.isNull()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        assert not icon.pixmap(size, size).isNull()
