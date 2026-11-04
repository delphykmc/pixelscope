from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSettings

from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.ui.input_profile_library import InputProfileLibrary, interpretation_key
from pixelscope.ui.raw_open_dialog import RawOpenDialog
from pixelscope.ui.yuv_open_dialog import YuvOpenDialog


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "input-profiles.ini"), QSettings.Format.IniFormat)


def _raw(**changes: object) -> RawProfile:
    payload: dict[str, object] = {
        "name": "camera",
        "width": 4,
        "height": 2,
        "stride_bytes": 8,
        "offset_bytes": 0,
        "storage_format": "unpacked",
        "container_dtype": "uint16",
        "endianness": "little",
        "bit_depth": 10,
        "bit_alignment": "lsb",
        "channel_layout": "BAYER",
        "bayer_pattern": "RGGB",
        "black_level": [0, 0, 0, 0],
        "white_level": 1023,
    }
    payload.update(changes)
    return RawProfile.parse_obj(payload)


def test_identity_ignores_display_name_not_native_interpretation() -> None:
    base = _raw()
    assert interpretation_key(base) == interpretation_key(_raw(name="renamed"))
    assert interpretation_key(base) != interpretation_key(_raw(stride_bytes=10))
    assert interpretation_key(base) != interpretation_key(_raw(endianness="big"))
    assert interpretation_key(base) != interpretation_key(_raw(bit_alignment="msb"))
    assert interpretation_key(base) != interpretation_key(_raw(bayer_pattern="BGGR"))
    assert interpretation_key(base) != interpretation_key(_raw(storage_format="mipi_raw10"))


def test_recent_dedup_order_and_favorites_persist_without_path(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    library = InputProfileLibrary(settings)
    a = _raw()
    b = _raw(stride_bytes=10)
    library.record_recent(a)
    library.record_recent(b)
    library.record_recent(_raw(name="new label"))
    assert len(library.recent("raw")) == 2
    assert interpretation_key(library.recent("raw")[0].profile) == interpretation_key(a)

    first = library.add_favorite(a, "Sensor baseline")
    second = library.add_favorite(b, "Sensor baseline")
    assert first != second
    library.rename_favorite(first, "Sensor A")
    settings.sync()

    reopened = InputProfileLibrary(_settings(tmp_path))
    assert len(reopened.recent("raw")) == 2
    assert tuple(entry.label for entry in reopened.favorites("raw")) == (
        "Sensor A",
        "Sensor baseline",
    )
    assert interpretation_key(reopened.favorites("raw")[0].profile) != interpretation_key(
        reopened.favorites("raw")[1].profile
    )
    reopened.remove_favorite(second)
    assert len(InputProfileLibrary(_settings(tmp_path)).favorites("raw")) == 1
    serialized = str(settings.value("InputProfiles/library_v1"))
    assert str(tmp_path) not in serialized
    assert "source_path" not in serialized
    assert "document_id" not in serialized


def test_independent_family_mru_caps_and_interleaved_persistence(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    library = InputProfileLibrary(settings)
    first_yuv = YuvProfile(width=4, height=4, channel_layout="YUV420")
    library.record_recent(first_yuv)
    for index in range(15):
        width = 4 + 2 * index
        library.record_recent(_raw(width=width, stride_bytes=2 * width))
    assert len(library.recent("raw")) == 12
    assert len(library.recent("yuv")) == 1
    assert library.recent("raw")[0].profile.width == 32
    assert library.recent("raw")[-1].profile.width == 10
    assert interpretation_key(library.recent("yuv")[0].profile) == interpretation_key(first_yuv)

    for index in range(14):
        width = 6 + 2 * index
        library.record_recent(YuvProfile(width=width, height=4, channel_layout="YUV422"))
    assert len(library.recent("raw")) == 12
    assert len(library.recent("yuv")) == 12
    assert library.recent("yuv")[0].profile.width == 32
    assert library.recent("yuv")[-1].profile.width == 10

    library.record_recent(_raw(width=32, stride_bytes=64, name="new label"))
    assert len(library.recent("raw")) == 12
    assert library.recent("raw")[0].profile.name == "new label"
    settings.sync()
    restored = InputProfileLibrary(_settings(tmp_path))
    assert len(restored.recent("raw")) == 12
    assert len(restored.recent("yuv")) == 12
    assert restored.recent("raw")[0].profile.name == "new label"


def test_legacy_v1_global_history_migrates_to_family_caps(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    library = InputProfileLibrary(settings)
    old_yuv = YuvProfile(width=4, height=4, channel_layout="YUV420")
    library.record_recent(old_yuv)
    payload = json.loads(str(settings.value("InputProfiles/library_v1")))
    for width in range(4, 32, 2):
        raw = _raw(width=width, stride_bytes=width * 2)
        payload["recent"].insert(
            0,
            {
                "id": "",
                "label": raw.name,
                "kind": "raw",
                "origin": "Manual",
                "profile": raw.dict(),
            },
        )
    settings.setValue("InputProfiles/library_v1", json.dumps(payload))
    migrated = InputProfileLibrary(settings)
    assert len(migrated.recent("raw")) == 12
    assert len(migrated.recent("yuv")) == 1
    assert interpretation_key(migrated.recent("yuv")[0].profile) == interpretation_key(old_yuv)


def test_yuv_is_separate_family_and_rejects_unsupported_saved_profile(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    library = InputProfileLibrary(settings)
    yuv = YuvProfile(width=4, height=4, channel_layout="YUV420")
    library.record_recent(yuv)
    library.add_favorite(yuv, "YUV420 4x4")
    assert not library.recent("raw")
    assert len(library.recent("yuv")) == 1

    stored = json.loads(str(settings.value("InputProfiles/library_v1")))
    stored["favorites"].append(
        {
            "id": "unsupported",
            "label": "P010",
            "origin": "Favorite",
            "kind": "yuv",
            "profile": {
                "width": 4,
                "height": 4,
                "channel_layout": "YUV420",
                "bit_depth": 10,
            },
        }
    )
    settings.setValue("InputProfiles/library_v1", json.dumps(stored))
    reopened = InputProfileLibrary(settings)
    assert len(reopened.favorites("yuv")) == 1
    assert reopened.error is not None


def test_saved_json_snapshot_survives_deleted_external_file(tmp_path: Path) -> None:
    sidecar = tmp_path / "external.json"
    original = _raw(name="external camera")
    original.save_json(sidecar)
    library = InputProfileLibrary(_settings(tmp_path))
    imported = RawProfile.load_json(sidecar)
    library.add_favorite(imported, "Safe copy")
    sidecar.unlink()

    reopened = InputProfileLibrary(_settings(tmp_path))
    saved = reopened.favorites("raw")[0].profile
    assert interpretation_key(saved) == interpretation_key(original)
    assert not sidecar.exists()


def test_same_label_profiles_have_discriminating_selector_signatures(
    qtbot: object, tmp_path: Path
) -> None:
    library = InputProfileLibrary(_settings(tmp_path))
    library.add_favorite(_raw(stride_bytes=8), "Sensor")
    library.add_favorite(_raw(stride_bytes=10), "Sensor")
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    controls = dialog.profile_library_controls
    controls.library = InputProfileLibrary(_settings(tmp_path))
    controls.refresh()
    first = controls.favorite_box.itemText(1)
    second = controls.favorite_box.itemText(2)
    assert first != second
    assert "stride 8" in first
    assert "stride 10" in second


def test_unsupported_schema_and_corrupt_settings_fail_closed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.setValue("InputProfiles/library_v1", '{"version": 999, "recent": []}')
    library = InputProfileLibrary(settings)
    assert library.read_only
    assert not library.recent("raw")
    try:
        library.add_favorite(_raw(), "Must not overwrite")
    except ValueError:
        pass
    else:
        raise AssertionError("future schema must remain untouched")
    assert '"version": 999' in str(settings.value("InputProfiles/library_v1"))
    library.reset()
    assert not library.read_only

    settings.setValue("InputProfiles/library_v1", "not json")
    reopened = InputProfileLibrary(settings)
    assert reopened.read_only
    assert reopened.error is not None


def test_raw_dialog_reuse_preserves_explicit_stride_and_validation(
    qtbot: object, tmp_path: Path
) -> None:
    path = tmp_path / "sensor.raw"
    path.write_bytes(bytes(18))
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    settings = _settings(tmp_path)
    dialog.profile_library_controls.library = InputProfileLibrary(settings)
    dialog.profile_library_controls.refresh()
    dialog.set_source_path(path)
    dialog.set_profile(_raw(stride_bytes=10))
    dialog._accept_validated()
    assert dialog.result() == dialog.DialogCode.Accepted

    reopened = RawOpenDialog()
    qtbot.addWidget(reopened)  # type: ignore[attr-defined]
    reopened.profile_library_controls.library = InputProfileLibrary(_settings(tmp_path))
    reopened.profile_library_controls.refresh()
    reopened.set_source_path(path)
    reopened.profile_library_controls.recent_box.setCurrentIndex(1)
    assert reopened.stride.value() == 10
    assert not reopened.stride_is_auto
    assert reopened.file_size_state == "match"
    assert "Byte-size validation does not prove" in (reopened.native_interpretation_summary.text())
    assert "Recent" in reopened.native_interpretation_summary.text()


def test_raw_provenance_tracks_edits_after_favorite_and_json(qtbot: object, tmp_path: Path) -> None:
    library = InputProfileLibrary(_settings(tmp_path))
    library.add_favorite(_raw(), "Original")
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    controls = dialog.profile_library_controls
    controls.library = library
    controls.refresh()
    controls.favorite_box.setCurrentIndex(1)
    assert "Origin: Favorite" in dialog.native_interpretation_summary.text()

    dialog.stride.setValue(10)
    assert "Origin: Modified from Favorite" in dialog.native_interpretation_summary.text()
    dialog._accept_validated()
    assert library.recent("raw")[0].origin == "Modified from Favorite"
    assert library.favorites("raw")[0].profile.stride_bytes == 8

    other = RawOpenDialog()
    qtbot.addWidget(other)  # type: ignore[attr-defined]
    other.set_profile(_raw())
    other.set_input_origin("Explicit JSON")
    assert "Origin: Explicit JSON" in other.native_interpretation_summary.text()
    other.stride.setValue(10)
    assert "Origin: Modified from Explicit JSON" in other.native_interpretation_summary.text()
    other.stride.setValue(8)
    assert "Origin: Explicit JSON" in other.native_interpretation_summary.text()


def test_raw_recent_origin_becomes_modified_after_edit(qtbot: object, tmp_path: Path) -> None:
    library = InputProfileLibrary(_settings(tmp_path))
    library.record_recent(_raw())
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    controls = dialog.profile_library_controls
    controls.library = library
    controls.refresh()
    controls.recent_box.setCurrentIndex(1)
    dialog.stride.setValue(10)
    assert "Origin: Modified from Recent" in dialog.native_interpretation_summary.text()


def test_raw_trailing_bytes_are_allowed_with_exact_ignored_offset(
    qtbot: object, tmp_path: Path
) -> None:
    path = tmp_path / "trailing.raw"
    path.write_bytes(bytes(21))
    dialog = RawOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.set_source_path(path)
    dialog.set_profile(_raw(stride_bytes=10))
    assert dialog.file_size_state == "warning"
    assert "3 trailing bytes" in dialog.file_status.text()
    assert "[18, 21)" in dialog.file_status.text()
    assert dialog.ok_button.isEnabled()


def test_yuv_dialog_strict_size_and_native_summary(qtbot: object, tmp_path: Path) -> None:
    path = tmp_path / "plane.yuv"
    path.write_bytes(bytes(24))
    dialog = YuvOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.set_profile(YuvProfile(width=4, height=4, channel_layout="YUV420"))
    dialog.set_source_path(path)
    assert dialog.file_size_state == "match"
    assert "Y-first / interleaved UV" in dialog.interpretation_summary.text()

    path.write_bytes(bytes(23))
    dialog.set_source_path(path)
    assert dialog.file_size_state == "truncated"
    assert "reject" in dialog.file_size.text()

    path.write_bytes(bytes(25))
    dialog.set_source_path(path)
    assert dialog.file_size_state == "trailing"
    assert "reject for native YUV" in dialog.file_size.text()

    path.write_bytes(bytes(24))
    dialog.set_source_path(path)
    dialog._accept_validated()
    assert dialog.result() == dialog.DialogCode.Accepted


def test_yuv_favorite_and_explicit_json_provenance_track_edits(
    qtbot: object, tmp_path: Path
) -> None:
    library = InputProfileLibrary(_settings(tmp_path))
    saved = YuvProfile(width=4, height=4, channel_layout="YUV420")
    library.add_favorite(saved, "4x4 favorite")
    dialog = YuvOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    controls = dialog.profile_library_controls
    controls.library = library
    controls.refresh()
    controls.favorite_box.setCurrentIndex(1)
    assert "Origin: Favorite" in dialog.interpretation_summary.text()
    dialog.width_box.setValue(6)
    assert "Origin: Modified from Favorite" in dialog.interpretation_summary.text()
    dialog._accept_validated()
    assert library.recent("yuv")[0].origin == "Modified from Favorite"
    assert library.favorites("yuv")[0].profile.width == 4

    other = YuvOpenDialog()
    qtbot.addWidget(other)  # type: ignore[attr-defined]
    other.set_profile(saved)
    other.profile_library_controls.mark_origin("Explicit JSON", saved)
    other._update_file_size()
    other.height_box.setValue(6)
    assert "Origin: Modified from Explicit JSON" in other.interpretation_summary.text()


def test_yuv_missing_source_never_accepts_or_records_recent(
    qtbot: object, tmp_path: Path, monkeypatch: object
) -> None:
    from PySide6.QtWidgets import QMessageBox

    shown: list[str] = []
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QMessageBox, "warning", lambda _parent, _title, reason: shown.append(str(reason))
    )
    path = tmp_path / "vanished.yuv"
    path.write_bytes(bytes(24))
    dialog = YuvOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    library = InputProfileLibrary(_settings(tmp_path))
    dialog.profile_library_controls.library = library
    dialog.set_profile(YuvProfile(width=4, height=4, channel_layout="YUV420"))
    dialog.set_source_path(path)
    path.unlink()
    dialog._accept_validated()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert shown
    assert not library.recent("yuv")


def test_yuv_rejects_truncated_and_trailing_at_accept_time(
    qtbot: object, tmp_path: Path, monkeypatch: object
) -> None:
    from PySide6.QtWidgets import QMessageBox

    warnings: list[str] = []
    monkeypatch.setattr(  # type: ignore[attr-defined]
        QMessageBox, "warning", lambda _parent, _title, reason: warnings.append(str(reason))
    )
    path = tmp_path / "size.yuv"
    dialog = YuvOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    library = InputProfileLibrary(_settings(tmp_path))
    dialog.profile_library_controls.library = library
    dialog.set_profile(YuvProfile(width=4, height=4, channel_layout="YUV420"))

    for size in (23, 25):
        path.write_bytes(bytes(size))
        dialog.set_source_path(path)
        dialog._accept_validated()
        assert dialog.result() != dialog.DialogCode.Accepted
    assert len(warnings) == 2
    assert not library.recent("yuv")


def test_yuv_profile_only_acceptance_does_not_require_file(qtbot: object, tmp_path: Path) -> None:
    dialog = YuvOpenDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    library = InputProfileLibrary(_settings(tmp_path))
    dialog.profile_library_controls.library = library
    dialog.set_profile(YuvProfile(width=4, height=4, channel_layout="YUV420"))
    dialog._accept_validated()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert len(library.recent("yuv")) == 1
