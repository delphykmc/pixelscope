from __future__ import annotations

from pathlib import Path

DESIGN_TOKENS = Path("src/pixelscope/ui/design_tokens.py")
TOOLBAR_TESTS = Path("tests/ui/test_toolbar_icons.py")


def _replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def _patch_design_tokens(text: str) -> str:
    text = _replace_once(
        text,
        "from PySide6.QtWidgets import QApplication\n",
        "from PySide6.QtWidgets import (\n"
        "    QApplication,\n"
        "    QProxyStyle,\n"
        "    QStyle,\n"
        "    QStyleHintReturn,\n"
        "    QStyleOption,\n"
        "    QWidget,\n"
        ")\n",
        "QtWidgets imports",
    )
    style_class = '''\n\nclass EngineeringStyle(QProxyStyle):
    """Keep disabled text flat instead of using the Windows etched effect."""

    def styleHint(
        self,
        hint: QStyle.StyleHint,
        option: QStyleOption | None = None,
        widget: QWidget | None = None,
        return_data: QStyleHintReturn | None = None,
    ) -> int:
        if hint == QStyle.StyleHint.SH_EtchDisabledText:
            return 0
        return super().styleHint(hint, option, widget, return_data)
'''
    marker = "\n\ndef apply_engineering_palette(app: QApplication) -> None:\n"
    if style_class not in text:
        if marker not in text:
            raise RuntimeError("apply_engineering_palette marker not found")
        text = text.replace(marker, style_class + marker, 1)
    return _replace_once(
        text,
        '    app.setStyle("Fusion")\n',
        '    app.setStyle(EngineeringStyle("Fusion"))\n',
        "Fusion style setup",
    )


def _patch_toolbar_tests(text: str) -> str:
    if "from PySide6.QtWidgets import QMenu, QStyle\n" not in text:
        if "from PySide6.QtWidgets import QMenu\n" in text:
            text = text.replace(
                "from PySide6.QtWidgets import QMenu\n",
                "from PySide6.QtWidgets import QMenu, QStyle\n",
                1,
            )
        else:
            text = _replace_once(
                text,
                "from PySide6.QtGui import QIcon, QPalette\n",
                "from PySide6.QtGui import QIcon, QPalette\n"
                "from PySide6.QtWidgets import QMenu, QStyle\n",
                "QMenu and QStyle test import",
            )

    popup_assertions = '''    popup_menus = window.menuBar().findChildren(QMenu)
    assert len(popup_menus) == 4
    assert all("QMenu::item:disabled" in menu.styleSheet() for menu in popup_menus)
'''
    popup_assertions_with_hint = '''    popup_menus = window.menuBar().findChildren(QMenu)
    assert len(popup_menus) == 4
    assert all("QMenu::item:disabled" in menu.styleSheet() for menu in popup_menus)
    assert all(
        menu.style().styleHint(QStyle.StyleHint.SH_EtchDisabledText) == 0
        for menu in popup_menus
    )
'''
    return _replace_once(
        text,
        popup_assertions,
        popup_assertions_with_hint,
        "disabled popup-menu style assertions",
    )


def _patch_file(path: Path, patcher: object) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = patcher(original)  # type: ignore[operator]
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    design_changed = _patch_file(DESIGN_TOKENS, _patch_design_tokens)
    tests_changed = _patch_file(TOOLBAR_TESTS, _patch_toolbar_tests)
    if design_changed or tests_changed:
        print("Applied flat disabled-menu text style fix")
    else:
        print("Flat disabled-menu text style fix was already applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
