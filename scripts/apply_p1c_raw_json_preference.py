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
    marker = 'RAW_DONT_SHOW_JSON_SETTING = "raw/dont_show_json_profiles"\n'
    if marker in text:
        print("RAW JSON Don't Show preference already applied")
        return text

    text = replace_once(
        text,
        "from pixelscope.io.raw_profile import RawProfile\n",
        """from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import required_file_size
""",
        "RAW size helper import",
    )
    text = replace_once(
        text,
        "LOGGER = logging.getLogger(__name__)\n",
        """LOGGER = logging.getLogger(__name__)
RAW_DONT_SHOW_JSON_SETTING = "raw/dont_show_json_profiles"
""",
        "RAW Don't Show setting constant",
    )
    text = replace_once(
        text,
        """        self.settings = QSettings()
        self._last_directory = str(self.settings.value("paths/last_directory", ""))

        self.documents: dict[str, ImageDocument] = {}
""",
        """        self.settings = QSettings()
        self._last_directory = str(self.settings.value("paths/last_directory", ""))
        stored_dont_show_raw_json = self.settings.value(
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

        self.documents: dict[str, ImageDocument] = {}
""",
        "RAW Don't Show setting initialization",
    )
    text = replace_once(
        text,
        """        add_action("File", "Open Images...", self.open_images, "Ctrl+O")
        add_action("File", "Open Folder...", self.open_folder, "Ctrl+Shift+O")
        add_action("File", "Open RAW with Profile...", self.open_raw)
        add_action("File", "Export Statistics CSV...", self.export_statistics)
        menus["File"].addSeparator()
""",
        """        add_action("File", "Open Images...", self.open_images, "Ctrl+O")
        add_action("File", "Open Folder...", self.open_folder, "Ctrl+Shift+O")
        add_action("File", "Open RAW with Profile...", self.open_raw)
        self.dont_show_raw_json_action = add_action(
            "File",
            "Don't Show RAW JSON Profiles",
            lambda _checked=False: None,
        )
        self.dont_show_raw_json_action.setCheckable(True)
        self.dont_show_raw_json_action.setChecked(self._dont_show_raw_json_profiles)
        self.dont_show_raw_json_action.toggled.connect(  # type: ignore[attr-defined]
            self._set_dont_show_raw_json_profiles
        )
        menus["File"].addSeparator()
        add_action("File", "Export Statistics CSV...", self.export_statistics)
        menus["File"].addSeparator()
""",
        "RAW Don't Show menu action",
    )
    text = replace_once(
        text,
        """    def _confirm_raw_profile(
        self,
        image_input: ImageInput,
        existing_id: str | None,
    ) -> RawProfile | None:
        dialog = RawOpenDialog(self)
        initial_profile: RawProfile | None = None
        if image_input.raw_profile_path is not None:
            try:
                initial_profile = RawProfile.load_json(image_input.raw_profile_path)
            except Exception as exc:  # noqa: BLE001 - user may correct it in the dialog
                QMessageBox.warning(
                    self,
                    "Cannot load RAW sidecar",
                    f"{image_input.raw_profile_path.name}: {exc}\\nUsing editable defaults.",
                )
        elif existing_id is not None:
            initial_profile = self._raw_profiles.get(existing_id)
            if initial_profile is None:
                existing_document = self.documents.get(existing_id)
                if existing_document is not None and isinstance(
                    existing_document.raw_profile, RawProfile
                ):
                    initial_profile = existing_document.raw_profile
        if initial_profile is not None:
            dialog.set_profile(initial_profile)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.profile()
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

    def _confirm_raw_profile(
        self,
        image_input: ImageInput,
        existing_id: str | None,
    ) -> RawProfile | None:
        initial_profile: RawProfile | None = None
        profile_from_json = False
        if image_input.raw_profile_path is not None:
            try:
                initial_profile = RawProfile.load_json(image_input.raw_profile_path)
                profile_from_json = True
            except Exception as exc:  # noqa: BLE001 - user may correct it in the dialog
                QMessageBox.warning(
                    self,
                    "Cannot load RAW sidecar",
                    f"{image_input.raw_profile_path.name}: {exc}\\nUsing editable defaults.",
                )
        elif existing_id is not None:
            initial_profile = self._raw_profiles.get(existing_id)
            if initial_profile is None:
                existing_document = self.documents.get(existing_id)
                if existing_document is not None and isinstance(
                    existing_document.raw_profile, RawProfile
                ):
                    initial_profile = existing_document.raw_profile

        source_matches_profile = False
        if initial_profile is not None:
            try:
                source_matches_profile = (
                    image_input.path.stat().st_size >= required_file_size(initial_profile)
                )
            except OSError:
                source_matches_profile = False
        if (
            profile_from_json
            and initial_profile is not None
            and self._dont_show_raw_json_profiles
            and source_matches_profile
        ):
            return initial_profile

        dialog = RawOpenDialog(self)
        set_source_path = getattr(dialog, "set_source_path", None)
        if callable(set_source_path):
            set_source_path(image_input.path)
        if initial_profile is not None:
            dialog.set_profile(initial_profile)
        set_option_visible = getattr(
            dialog,
            "set_json_confirmation_option_visible",
            None,
        )
        if callable(set_option_visible):
            set_option_visible(profile_from_json)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        profile = dialog.profile()
        dont_show_requested = getattr(
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
        return profile
""",
        "RAW Don't Show flow",
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
