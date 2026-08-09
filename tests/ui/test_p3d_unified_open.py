from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from pixelscope.app.main_window import MainWindow
from pixelscope.io.path_discovery import SUPPORTED_IMAGE_FILTER
from pixelscope.io.raw_profile import RawProfile
from pixelscope.ui.raw_open_dialog import RawOpenDialog


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path) -> None:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    settings = QSettings()
    settings.clear()
    settings.sync()


def _profile(name: str = "sensor") -> RawProfile:
    return RawProfile(
        name=name,
        width=4,
        height=4,
        stride_bytes=8,
        storage_format="unpacked",
        container_dtype="uint16",
        endianness="little",
        bit_depth=10,
        bit_alignment="lsb",
        channel_layout="GRAY",
        black_level=64,
        white_level=1023,
    )


def _disable_selection_render(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(window, "_select_document_ids", lambda *_args, **_kwargs: None)


def _set_open_images_result(
    monkeypatch: pytest.MonkeyPatch,
    paths: list[Path],
    captured_filters: list[str] | None = None,
) -> None:
    def fake_get_open_file_names(
        _parent: object,
        _title: str,
        _directory: str,
        image_filter: str,
    ) -> tuple[list[str], str]:
        if captured_filters is not None:
            captured_filters.append(image_filter)
        return [str(path) for path in paths], image_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", fake_get_open_file_names)


def test_file_menu_has_only_unified_open_actions(qtbot: object) -> None:
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert "Open Images..." in window.action_map
    assert "Open Folder..." in window.action_map
    assert "Open RAW with Profile..." not in window.action_map
    assert not hasattr(window, "open_raw")
    assert window.action_map["Open Images..."].shortcut().toString() == "Ctrl+O"
    assert window.action_map["Open Folder..."].shortcut().toString() == "Ctrl+Shift+O"
    window.close()


def test_open_images_uses_exact_supported_filter(
    qtbot: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_filters: list[str] = []
    _set_open_images_result(monkeypatch, [], captured_filters)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.open_images()

    assert captured_filters == [SUPPORTED_IMAGE_FILTER]
    assert captured_filters[0] == "Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)"
    assert "*.*" not in captured_filters[0]
    window.close()


def test_unified_open_ordinary_image_bypasses_raw_profile_dialog(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = tmp_path / "ordinary.png"
    image_path.write_bytes(b"ordinary")
    _set_open_images_result(monkeypatch, [image_path])

    class UnexpectedRawDialog:
        def __init__(self, _parent: object) -> None:
            raise AssertionError("ordinary image unexpectedly requested a RAW profile")

    monkeypatch.setattr("pixelscope.app.main_window.RawOpenDialog", UnexpectedRawDialog)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _disable_selection_render(window, monkeypatch)

    window.open_images()

    assert len(window.documents) == 1
    document = next(iter(window.documents.values()))
    assert document.source_path == image_path
    assert window._raw_profiles == {}
    window.close()


def test_unified_open_raw_without_sidecar_accepts_profile(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_path = tmp_path / "accepted.raw"
    raw_path.write_bytes(bytes(32))
    selected_profile = _profile()
    _set_open_images_result(monkeypatch, [raw_path])

    class AcceptedRawDialog:
        source_path: Path | None = None

        def __init__(self, _parent: object) -> None:
            pass

        def set_source_path(self, path: Path) -> None:
            type(self).source_path = path

        def set_json_confirmation_option_visible(self, visible: bool) -> None:
            assert visible is False

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

        def profile(self) -> RawProfile:
            return selected_profile

    monkeypatch.setattr("pixelscope.app.main_window.RawOpenDialog", AcceptedRawDialog)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _disable_selection_render(window, monkeypatch)

    window.open_images()

    assert AcceptedRawDialog.source_path == raw_path
    assert len(window.documents) == 1
    document_id = next(iter(window.documents))
    assert window._raw_profiles[document_id] == selected_profile
    assert document_id not in window._raw_profile_paths
    window.close()


def test_unified_open_raw_cancel_does_not_register_document(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_path = tmp_path / "cancelled.raw"
    raw_path.write_bytes(bytes(32))
    _set_open_images_result(monkeypatch, [raw_path])

    class RejectedRawDialog:
        def __init__(self, _parent: object) -> None:
            pass

        def set_source_path(self, _path: Path) -> None:
            pass

        def set_json_confirmation_option_visible(self, visible: bool) -> None:
            assert visible is False

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("pixelscope.app.main_window.RawOpenDialog", RejectedRawDialog)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _disable_selection_render(window, monkeypatch)

    window.open_images()

    assert window.documents == {}
    assert window._raw_profiles == {}
    window.close()


def test_invalid_sidecar_warns_then_uses_editable_fallback(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_path = tmp_path / "invalid.raw"
    raw_path.write_bytes(bytes(32))
    sidecar = raw_path.with_suffix(".json")
    sidecar.write_text("{not-json", encoding="utf-8")
    fallback_profile = _profile("fallback")
    _set_open_images_result(monkeypatch, [raw_path])
    warnings: list[tuple[str, str]] = []

    def fake_warning(_parent: object, title: str, text: str) -> QMessageBox.StandardButton:
        warnings.append((title, text))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)

    class EditableFallbackDialog:
        def __init__(self, _parent: object) -> None:
            self.loaded_profile: RawProfile | None = None

        def set_source_path(self, path: Path) -> None:
            assert path == raw_path

        def set_profile(self, profile: RawProfile) -> None:
            self.loaded_profile = profile

        def set_json_confirmation_option_visible(self, visible: bool) -> None:
            assert visible is False

        def exec(self) -> QDialog.DialogCode:
            assert self.loaded_profile is None
            return QDialog.DialogCode.Accepted

        def profile(self) -> RawProfile:
            return fallback_profile

    monkeypatch.setattr("pixelscope.app.main_window.RawOpenDialog", EditableFallbackDialog)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    _disable_selection_render(window, monkeypatch)

    window.open_images()

    assert warnings
    assert warnings[0][0] == "Cannot load RAW sidecar"
    assert sidecar.name in warnings[0][1]
    document_id = next(iter(window.documents))
    assert window._raw_profiles[document_id] == fallback_profile
    assert window._raw_profile_paths[document_id] == sidecar
    window.close()


def test_multi_raw_open_uses_each_same_basename_sidecar(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_a = tmp_path / "a.raw"
    raw_b = tmp_path / "b.raw"
    raw_a.write_bytes(bytes(32))
    raw_b.write_bytes(bytes(32))
    profile_a = _profile("a")
    profile_b = _profile("b")
    profile_a.save_json(raw_a.with_suffix(".json"))
    profile_b.save_json(raw_b.with_suffix(".json"))
    _set_open_images_result(monkeypatch, [raw_b, raw_a])

    class UnexpectedRawDialog:
        def __init__(self, _parent: object) -> None:
            raise AssertionError("compatible sidecars should be sufficient when confirmation is disabled")

    monkeypatch.setattr("pixelscope.app.main_window.RawOpenDialog", UnexpectedRawDialog)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window._dont_show_raw_json_profiles = True
    _disable_selection_render(window, monkeypatch)

    window.open_images()

    by_name = {
        document.source_path.name: window._raw_profiles[document.document_id]
        for document in window.documents.values()
        if document.source_path is not None
    }
    assert by_name == {"a.raw": profile_a, "b.raw": profile_b}
    window.close()


def test_sidecar_suppression_still_respects_exact_size_policy(
    qtbot: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_path = tmp_path / "trailing.raw"
    raw_path.write_bytes(bytes(40))
    sidecar = raw_path.with_suffix(".json")
    profile = _profile()
    profile.save_json(sidecar)

    class RejectingDialog:
        constructed = 0

        def __init__(self, _parent: object) -> None:
            type(self).constructed += 1

        def set_source_path(self, _path: Path) -> None:
            pass

        def set_profile(self, loaded: RawProfile) -> None:
            assert loaded == profile

        def set_json_confirmation_option_visible(self, visible: bool) -> None:
            assert visible

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("pixelscope.app.main_window.RawOpenDialog", RejectingDialog)
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window._dont_show_raw_json_profiles = True

    assert window._confirm_raw_profile(
        __import__("pixelscope.io.path_discovery", fromlist=["ImageInput"]).ImageInput(
            raw_path,
            sidecar,
        ),
        None,
    ) == profile
    assert RejectingDialog.constructed == 0

    window.application_settings = replace(
        window.application_settings,
        require_exact_raw_file_size=True,
    )
    assert window._confirm_raw_profile(
        __import__("pixelscope.io.path_discovery", fromlist=["ImageInput"]).ImageInput(
            raw_path,
            sidecar,
        ),
        None,
    ) is None
    assert RejectingDialog.constructed == 1
    window.close()


def test_raw_profile_dialog_uses_profile_terms(qtbot: object) -> None:
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.load_button.text() == "Load Profile…"
    assert dialog.save_button.text() == "Save Profile…"
