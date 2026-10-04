from __future__ import annotations

from PySide6.QtWidgets import QApplication

from pixelscope.ui import clipboard_support


def test_set_clipboard_text_flushes_windows_ole_ownership(
    qapp: object,
    monkeypatch: object,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(  # type: ignore[attr-defined]
        clipboard_support,
        "_running_on_windows",
        lambda: True,
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        clipboard_support,
        "_flush_windows_ole_clipboard",
        lambda: calls.append("flush") or 0,
    )

    clipboard = QApplication.clipboard()
    try:
        clipboard_support.set_clipboard_text("pixelscope clipboard")

        assert clipboard.text() == "pixelscope clipboard"
        assert calls == ["flush"]
    finally:
        clipboard.clear()


def test_set_clipboard_text_skips_native_flush_off_windows(
    qapp: object,
    monkeypatch: object,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(  # type: ignore[attr-defined]
        clipboard_support,
        "_running_on_windows",
        lambda: False,
    )
    monkeypatch.setattr(  # type: ignore[attr-defined]
        clipboard_support,
        "_flush_windows_ole_clipboard",
        lambda: calls.append("flush") or 0,
    )

    clipboard = QApplication.clipboard()
    try:
        clipboard_support.set_clipboard_text("portable clipboard")

        assert clipboard.text() == "portable clipboard"
        assert calls == []
    finally:
        clipboard.clear()
