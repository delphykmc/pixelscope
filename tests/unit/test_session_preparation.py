from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest

from pixelscope.core.cancellation import CooperativeCancellation, cancellation_scope
from pixelscope.core.comparison_set import Session, SessionSource
from pixelscope.io.comparison_set_repository import ComparisonSetRepository
from pixelscope.io.dialog_directory import prepare_dialog_directory
from pixelscope.io.session_preparation import prepare_recent_session


def test_session_preflight_preserves_profiles_and_prepares_canonical_registration(tmp_path):
    source = tmp_path / "frame.png"
    source.write_bytes(b"not decoded during preflight")
    missing = tmp_path / "missing.png"
    repository = ComparisonSetRepository()
    path = tmp_path / "workspace.pixelscope"
    session = Session((SessionSource(str(source)), SessionSource(str(missing))), (str(source),))
    repository.save(path, session)
    prepared = prepare_recent_session(path, repository)
    assert prepared.session == session
    assert prepared.missing == (missing,)
    assert len(prepared.sources) == 1
    saved, record = prepared.sources[0]
    assert saved == session.registered_sources[0]
    assert record.image_input.path == source.resolve()
    assert record.canonical_path_key == str(source.resolve()).casefold()
    assert record.canonical_folder_path == tmp_path.resolve()
    assert not record.resolve_raw_profile and not record.select_on_complete


def test_preflight_rejects_wrong_kind_and_cancels_before_another_source_probe(
    tmp_path, monkeypatch
):
    repository = ComparisonSetRepository()
    assert prepare_recent_session(tmp_path, repository).state == "wrong_type"
    assert prepare_recent_session(tmp_path / "absent", repository).state == "missing"
    cancel = Event()
    cancel.set()
    with cancellation_scope(cancel), pytest.raises(CooperativeCancellation):
        prepare_recent_session(tmp_path / "absent", repository)


def test_dialog_directory_missing_configured_falls_back_to_existing_last_used(tmp_path):
    assert prepare_dialog_directory(str(tmp_path / "absent"), str(tmp_path)) == str(tmp_path)
    assert prepare_dialog_directory(str(tmp_path), "") == str(tmp_path)


def test_dialog_directory_inaccessible_configured_does_not_prevent_fallback(tmp_path, monkeypatch):
    original = Path.is_dir
    denied = tmp_path / "denied"

    def is_dir(path):
        if path == denied:
            raise PermissionError("simulated inaccessible directory")
        return original(path)

    monkeypatch.setattr(Path, "is_dir", is_dir)
    assert prepare_dialog_directory(str(denied), str(tmp_path)) == str(tmp_path)
