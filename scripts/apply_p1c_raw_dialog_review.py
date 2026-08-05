from __future__ import annotations

from pathlib import Path

MAIN_WINDOW = Path("src/pixelscope/app/main_window.py")
UI_SMOKE = Path("tests/ui/test_ui_smoke.py")


def replace_once(text: str, old: str, new: str, description: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {description}, found {count}")
    return text.replace(old, new, 1)


def patch_main_window(text: str) -> str:
    if 'RAW_DONT_SHOW_JSON_SETTING = "raw/dont_show_json_profiles"' in text:
        print("MainWindow already uses Don't Show semantics")
        return text

    text = replace_once(
        text,
        'RAW_CONFIRM_JSON_SETTING = "raw/confirm_json_profiles"\n',
        'RAW_DONT_SHOW_JSON_SETTING = "raw/dont_show_json_profiles"\n',
        "RAW setting constant",
    )
    text = replace_once(
        text,
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
        """        stored_dont_show_raw_json = self.settings.value(
            RAW_DONT_SHOW_JSON_SETTING,
            False,
        )
        if isinstance(stored_dont_show_raw_json, bool):
            self._dont_show_raw_json_profiles = stored_dont_show_raw_json
        else:
            self._dont_show_raw_json_profiles = (
                str(stored_dont_show_raw_json).strip().casefold()
                in {"true", "1", "yes", "on"}
            )
""",
        "RAW setting initialization",
    )
    text = replace_once(
        text,
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
        """        self.dont_show_raw_json_action = add_action(
            "File",
            "Don't Show RAW JSON Profiles",
            lambda _checked=False: None,
        )
        self.dont_show_raw_json_action.setCheckable(True)
        self.dont_show_raw_json_action.setChecked(self._dont_show_raw_json_profiles)
        self.dont_show_raw_json_action.toggled.connect(  # type: ignore[attr-defined]
            self._set_dont_show_raw_json_profiles
        )
""",
        "RAW menu action",
    )
    text = replace_once(
        text,
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
        """    def _set_dont_show_raw_json_profiles(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self._dont_show_raw_json_profiles = enabled
        self.settings.setValue(RAW_DONT_SHOW_JSON_SETTING, enabled)
        self.settings.sync()
        if (
            hasattr(self, "dont_show_raw_json_action")
            and self.dont_show_raw_json_action.isChecked() != enabled
        ):
            self.dont_show_raw_json_action.blockSignals(True)
            self.dont_show_raw_json_action.setChecked(enabled)
            self.dont_show_raw_json_action.blockSignals(False)
""",
        "RAW setting persistence method",
    )
    text = replace_once(
        text,
        """            and not self._confirm_raw_json_profiles
            and source_matches_profile
""",
        """            and self._dont_show_raw_json_profiles
            and source_matches_profile
""",
        "RAW dialog bypass condition",
    )
    text = replace_once(
        text,
        """        skip_requested = getattr(
            dialog,
            "skip_json_confirmation_requested",
            None,
        )
        if profile_from_json and callable(skip_requested) and skip_requested():
            self._set_confirm_raw_json_profiles(False)
""",
        """        dont_show_requested = getattr(
            dialog,
            "dont_show_json_profiles_requested",
            None,
        )
        if not callable(dont_show_requested):
            dont_show_requested = getattr(
                dialog,
                "skip_json_confirmation_requested",
                None,
            )
        if (
            profile_from_json
            and callable(dont_show_requested)
            and dont_show_requested()
        ):
            self._set_dont_show_raw_json_profiles(True)
""",
        "RAW dialog Don't Show result",
    )
    return text


def patch_ui_smoke(text: str) -> str:
    return replace_once(
        text,
        """    assert dialog.bayer_pattern.currentText() == "GBRG"
    assert dialog.black.text() == "64, 65, 66, 67"
    assert dialog.profile() == profile
""",
        """    assert dialog.bayer_pattern.currentText() == "GBRG"
    assert [
        control.value()
        for control in (dialog.black_r, dialog.black_gr, dialog.black_gb, dialog.black_b)
    ] == [64, 65, 66, 67]
    assert dialog.profile() == profile
""",
        "Bayer black-level smoke assertion",
    )


def update(path: Path, patcher: object) -> None:
    original = path.read_text(encoding="utf-8")
    updated = patcher(original)  # type: ignore[operator]
    if updated == original:
        print(f"No changes required: {path}")
        return
    path.write_text(updated, encoding="utf-8")
    print(f"Updated: {path}")


def main() -> int:
    update(MAIN_WINDOW, patch_main_window)
    update(UI_SMOKE, patch_ui_smoke)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
