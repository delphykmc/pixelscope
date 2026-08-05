from __future__ import annotations

from pathlib import Path

MAIN_WINDOW = Path("src/pixelscope/app/main_window.py")
UI_SMOKE = Path("tests/ui/test_ui_smoke.py")


def replace_region(
    text: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
    description: str,
) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"cannot find start of {description}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"cannot find end of {description}")
    return text[:start] + replacement + text[end:]


def replace_optional(text: str, old: str, new: str) -> str:
    return text.replace(old, new, 1) if old in text else text


def patch_main_window(text: str) -> str:
    if 'RAW_DONT_SHOW_JSON_SETTING = "raw/dont_show_json_profiles"' in text:
        print("MainWindow already uses Don't Show semantics")
        return text

    if 'RAW_CONFIRM_JSON_SETTING = "raw/confirm_json_profiles"' not in text:
        raise RuntimeError("RAW JSON preference integration has not been applied")

    text = text.replace(
        'RAW_CONFIRM_JSON_SETTING = "raw/confirm_json_profiles"',
        'RAW_DONT_SHOW_JSON_SETTING = "raw/dont_show_json_profiles"',
        1,
    )

    init_start_candidates = (
        "        stored_confirm_raw_json = self.settings.value(",
        "        self._confirm_raw_json_profiles = bool(",
    )
    init_start = next((candidate for candidate in init_start_candidates if candidate in text), None)
    if init_start is None:
        raise RuntimeError("cannot find existing RAW JSON setting initialization")
    text = replace_region(
        text,
        init_start,
        "        self.documents: dict[str, ImageDocument] = {}",
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

    text = replace_region(
        text,
        "        self.confirm_raw_json_action = add_action(",
        '        menus["File"].addSeparator()',
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

    text = replace_region(
        text,
        "    def _set_confirm_raw_json_profiles(",
        "    def _confirm_raw_profile(",
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
        "RAW preference setter",
    )

    text = replace_optional(
        text,
        "and not self._confirm_raw_json_profiles",
        "and self._dont_show_raw_json_profiles",
    )

    skip_start = text.find("        skip_requested = getattr(")
    if skip_start >= 0:
        skip_end_marker = "            self._set_confirm_raw_json_profiles(False)\n"
        skip_end = text.find(skip_end_marker, skip_start)
        if skip_end < 0:
            raise RuntimeError("cannot find end of RAW dialog preference result block")
        skip_end += len(skip_end_marker)
        text = (
            text[:skip_start]
            + """        dont_show_requested = getattr(
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
"""
            + text[skip_end:]
        )

    return text


def patch_ui_smoke(text: str) -> str:
    old = """    assert dialog.bayer_pattern.currentText() == "GBRG"
    assert dialog.black.text() == "64, 65, 66, 67"
    assert dialog.profile() == profile
"""
    new = """    assert dialog.bayer_pattern.currentText() == "GBRG"
    assert [
        control.value()
        for control in (dialog.black_r, dialog.black_gr, dialog.black_gb, dialog.black_b)
    ] == [64, 65, 66, 67]
    assert dialog.profile() == profile
"""
    return replace_optional(text, old, new)


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
