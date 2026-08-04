from __future__ import annotations

from pathlib import Path

MAIN_WINDOW = Path("src/pixelscope/app/main_window.py")
TOOLBAR_TEST = Path("tests/ui/test_toolbar_icons.py")

MAIN_OLD = """\
        menus = {
            "File": menu_bar.addMenu("&File"),
            "Edit": menu_bar.addMenu("&Edit"),
            "Selection": menu_bar.addMenu("&Selection"),
            "View": menu_bar.addMenu("&View"),
        }
        add_action("File", "Open Images...", self.open_images, "Ctrl+O")
"""

MAIN_NEW = """\
        menus = {
            "File": menu_bar.addMenu("&File"),
            "Edit": menu_bar.addMenu("&Edit"),
            "Selection": menu_bar.addMenu("&Selection"),
            "View": menu_bar.addMenu("&View"),
        }
        for menu in menus.values():
            menu.setStyleSheet(menu_style())
        add_action("File", "Open Images...", self.open_images, "Ctrl+O")
"""

IMPORT_OLD = "from PySide6.QtGui import QIcon, QPalette\n"
IMPORT_NEW = (
    "from PySide6.QtGui import QIcon, QPalette\n"
    "from PySide6.QtWidgets import QMenu\n"
)

TEST_OLD = """\
    assert "QMenu::item:disabled" in window.menuBar().styleSheet()
    assert (
        window.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText).name()
        == TOKENS.text_disabled
    )
"""

TEST_NEW = """\
    assert "QMenu::item:disabled" in window.menuBar().styleSheet()
    popup_menus = window.menuBar().findChildren(QMenu)
    assert len(popup_menus) == 4
    assert all("QMenu::item:disabled" in menu.styleSheet() for menu in popup_menus)
    assert (
        window.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText).name()
        == TOKENS.text_disabled
    )
"""


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_file(path: Path, replacements: tuple[tuple[str, str, str], ...]) -> bool:
    original = path.read_text(encoding="utf-8")
    updated = original
    for old, new, description in replacements:
        updated = replace_once(updated, old, new, description)
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


def main() -> int:
    changed_main = patch_file(
        MAIN_WINDOW,
        ((MAIN_OLD, MAIN_NEW, "popup-menu stylesheet setup"),),
    )
    changed_test = patch_file(
        TOOLBAR_TEST,
        (
            (IMPORT_OLD, IMPORT_NEW, "QMenu test import"),
            (TEST_OLD, TEST_NEW, "disabled popup-menu style assertions"),
        ),
    )
    if changed_main or changed_test:
        print("Applied P0-D disabled popup-menu styling fix")
    else:
        print("P0-D disabled popup-menu styling fix was already applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
