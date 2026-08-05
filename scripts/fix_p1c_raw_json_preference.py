from __future__ import annotations

from pathlib import Path

MAIN_WINDOW = Path("src/pixelscope/app/main_window.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_main_window(text: str) -> str:
    text = replace_once(
        text,
        """        self._confirm_raw_json_profiles = bool(
            self.settings.value(RAW_CONFIRM_JSON_SETTING, True, type=bool)
        )
""",
        """        stored_confirm_raw_json = self.settings.value(
            RAW_CONFIRM_JSON_SETTING,
            True,
        )
        if isinstance(stored_confirm_raw_json, bool):
            self._confirm_raw_json_profiles = stored_confirm_raw_json
        else:
            self._confirm_raw_json_profiles = (
                str(stored_confirm_raw_json).strip().casefold()
                not in {"false", "0", "no", "off", ""}
            )
""",
        "RAW confirmation setting parser",
    )
    text = replace_once(
        text,
        """        self.confirm_raw_json_action = add_action(
            "File",
            "Confirm RAW JSON Profiles",
            self._set_confirm_raw_json_profiles,
        )
        self.confirm_raw_json_action.setCheckable(True)
        self.confirm_raw_json_action.setChecked(self._confirm_raw_json_profiles)
""",
        """        self.confirm_raw_json_action = add_action(
            "File",
            "Confirm RAW JSON Profiles",
            lambda _checked=False: None,
        )
        self.confirm_raw_json_action.setCheckable(True)
        self.confirm_raw_json_action.setChecked(self._confirm_raw_json_profiles)
        self.confirm_raw_json_action.toggled.connect(  # type: ignore[attr-defined]
            self._set_confirm_raw_json_profiles
        )
""",
        "RAW confirmation action wiring",
    )
    text = replace_once(
        text,
        """    def _set_confirm_raw_json_profiles(self, enabled: bool) -> None:
        self._confirm_raw_json_profiles = enabled
        self.settings.setValue(RAW_CONFIRM_JSON_SETTING, enabled)
        if hasattr(self, "confirm_raw_json_action"):
            self.confirm_raw_json_action.blockSignals(True)
            self.confirm_raw_json_action.setChecked(enabled)
            self.confirm_raw_json_action.blockSignals(False)
""",
        """    def _set_confirm_raw_json_profiles(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self._confirm_raw_json_profiles = enabled
        self.settings.setValue(RAW_CONFIRM_JSON_SETTING, enabled)
        self.settings.sync()
        if (
            hasattr(self, "confirm_raw_json_action")
            and self.confirm_raw_json_action.isChecked() != enabled
        ):
            self.confirm_raw_json_action.blockSignals(True)
            self.confirm_raw_json_action.setChecked(enabled)
            self.confirm_raw_json_action.blockSignals(False)
""",
        "RAW confirmation persistence method",
    )
    return text


def main() -> int:
    original = MAIN_WINDOW.read_text(encoding="utf-8")
    updated = patch_main_window(original)
    if updated == original:
        print(f"No changes required: {MAIN_WINDOW}")
        return 0
    MAIN_WINDOW.write_text(updated, encoding="utf-8")
    print(f"Updated: {MAIN_WINDOW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
