from __future__ import annotations

import hashlib
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import BinaryIO

import pytest

import pixelscope.remote.iqa_storage as iqa_storage
from pixelscope.remote.iqa_settings import RemoteIqaSettings, RemoteIqaStorageRoot
from pixelscope.remote.iqa_storage import (
    StorageResolutionError,
    resolve_existing_source,
    resolve_or_stage_source,
    resolve_result_reference,
    stage_source,
)


def _directory_link(link: Path, target: Path) -> None:
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            check=False,
            text=True,
        )
        if completed.returncode == 0:
            return
    try:
        link.symlink_to(target, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory links unavailable: {exc}")


def test_concurrent_staging_uses_unique_temps_and_one_verified_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.bin"
    payload = b"concurrent-pixelscope" * 100_000
    source.write_bytes(payload)
    staging = tmp_path / "share"
    staging.mkdir()

    barrier = Barrier(2)
    original_copy = iqa_storage.shutil.copyfileobj

    def synchronized_copy(src: BinaryIO, dst: BinaryIO, length: int = 0) -> None:
        barrier.wait(timeout=5)
        original_copy(src, dst, length=length)

    monkeypatch.setattr(iqa_storage.shutil, "copyfileobj", synchronized_copy)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(stage_source, source, staging, "shared")
            for _ in range(2)
        ]
        results = [future.result(timeout=10) for future in futures]

    expected_digest = hashlib.sha256(payload).hexdigest()
    expected_final = staging / "staging" / expected_digest / source.name
    assert {item.local_path for item in results} == {expected_final}
    assert {item.sha256 for item in results} == {expected_digest}
    assert expected_final.read_bytes() == payload
    assert list(staging.rglob("*.part")) == []


def test_staging_rejects_escaping_directory_link_before_external_mutation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"payload")
    staging = tmp_path / "share"
    staging.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _directory_link(staging / "staging", outside)

    with pytest.raises(StorageResolutionError, match="escapes configured storage root"):
        stage_source(source, staging, "shared")

    assert list(outside.iterdir()) == []


@pytest.mark.skipif(
    os.name != "nt",
    reason="client storage mappings intentionally require drive/UNC paths",
)
def test_configured_source_directory_link_escape_is_staged_not_referenced(
    tmp_path: Path,
) -> None:
    root = tmp_path / "share"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    source = outside / "sample.png"
    source.write_bytes(b"outside")
    linked_dir = root / "linked"
    _directory_link(linked_dir, outside)
    linked_source = linked_dir / source.name

    settings = RemoteIqaSettings(
        storage_roots=(RemoteIqaStorageRoot("shared", str(root)),),
        staging_root_id="shared",
    )

    assert resolve_existing_source(linked_source, settings) is None

    staged = resolve_or_stage_source(linked_source, settings)
    assert staged.staged
    assert staged.logical_path.storage_root_id == "shared"
    assert staged.logical_path.relative_path.startswith("staging/")
    assert staged.local_path.read_bytes() == b"outside"


@pytest.mark.skipif(
    os.name != "nt",
    reason="client storage mappings intentionally require drive/UNC paths",
)
def test_result_reference_rejects_directory_link_escape(
    tmp_path: Path,
) -> None:
    root = tmp_path / "share"
    root.mkdir()
    outside = tmp_path / "outside"
    result = outside / "job"
    result.mkdir(parents=True)
    _directory_link(root / "results", outside)

    settings = RemoteIqaSettings(
        storage_roots=(RemoteIqaStorageRoot("shared", str(root)),),
    )

    with pytest.raises(StorageResolutionError, match="escapes configured storage root"):
        resolve_result_reference("shared", "results/job", settings)
