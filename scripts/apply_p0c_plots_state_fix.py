from __future__ import annotations

from pathlib import Path

TARGET = Path("src/pixelscope/app/main_window.py")

OLD_VISIBILITY_BLOCK = '''    def _set_plots_visible(self, visible: bool) -> None:
        if visible:
            self._show_bottom_results()
        else:
            self.bottom_dock.hide()

    def _plots_visibility_changed(self, visible: bool) -> None:
        self.plots_action.blockSignals(True)
        self.plots_action.setChecked(visible)
        self.plots_action.blockSignals(False)
        self._update_action_states()

'''

NEW_VISIBILITY_BLOCK = '''    def _set_plots_visible(self, visible: bool) -> None:
        if visible:
            self._show_bottom_results()
        else:
            self.bottom_dock.hide()
        self.plots_action.blockSignals(True)
        self.plots_action.setChecked(visible)
        self.plots_action.blockSignals(False)
        self._update_action_states()

    def _plots_visibility_changed(self, visible: bool) -> None:
        self.plots_action.blockSignals(True)
        self.plots_action.setChecked(visible)
        self.plots_action.blockSignals(False)
        self._update_action_states()

'''

OLD_STATE_SOURCE = "            plots_visible = not self.bottom_dock.isHidden()\n"
NEW_STATE_SOURCE = "            plots_visible = self.plots_action.isChecked()\n"


def replace_once(text: str, old: str, new: str, description: str) -> str:
    count = text.count(old)
    if count == 0 and new in text:
        return text
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    original = TARGET.read_text(encoding="utf-8")
    updated = replace_once(
        original,
        OLD_VISIBILITY_BLOCK,
        NEW_VISIBILITY_BLOCK,
        "Plots visibility block",
    )
    updated = replace_once(
        updated,
        OLD_STATE_SOURCE,
        NEW_STATE_SOURCE,
        "Plots state source",
    )
    if updated == original:
        print("P0-C Plots state fix was already applied")
        return 0
    TARGET.write_text(updated, encoding="utf-8")
    print(f"Applied P0-C Plots state fix to {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
