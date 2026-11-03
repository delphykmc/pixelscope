from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest

from pixelscope.core.review_analysis import (
    AnalysisMeasurementV1,
    AnalysisSnapshotV1,
    AnalysisSourceV1,
    PresentedAnalysisTokenV1,
    capture_presented_analysis,
    measurement,
    parse_analysis_context,
    serialize_analysis_context,
)
from pixelscope.io.analysis_bundle import verify_analysis_bundle, write_analysis_bundle


def _snapshot(roi: tuple[int, int, int, int] | None = None) -> AnalysisSnapshotV1:
    document_id = str(uuid4())
    source_key = str(uuid4())
    digest = "a" * 64
    token = PresentedAnalysisTokenV1(
        feature="statistics",
        request_id=str(uuid4()),
        request_epoch=2,
        source_documents=((document_id, 7),),
        source_keys=(source_key,),
        roi_ref=roi,
        channel="All",
        domain="native",
        profile_signatures=(digest,),
        difference_cache_key=None,
    )
    return AnalysisSnapshotV1(
        snapshot_id=str(uuid4()),
        captured_utc="2026-11-04T00:00:00+00:00",
        token=token,
        sources=(
            AnalysisSourceV1(
                source_key=source_key,
                document_id=document_id,
                generation=7,
                native_shape=(12, 16, 3),
                reference_shape=(12, 16),
                native_dtype="uint16",
                channel_layout="RGB",
                effective_bits=10,
                profile_signature=digest,
            ),
        ),
        measurements=(measurement(source_key, "R", "Mean", 23.0, 20),),
        presentation=(("scope", "roi" if roi else "full"),),
    )


class _FakeAdapter:
    def __init__(self, snapshot: AnalysisSnapshotV1) -> None:
        self.snapshot = snapshot
        self.current = snapshot.token
        self.presented = snapshot.token
        self.mutate_during_read = False

    def get_presented_analysis_token(self) -> PresentedAnalysisTokenV1 | None:
        return self.presented

    def get_current_analysis_token(self) -> PresentedAnalysisTokenV1 | None:
        return self.current

    def read_presented_analysis(self) -> tuple:
        if self.mutate_during_read:
            self.current = replace(self.current, request_epoch=99)
        s = self.snapshot
        return s.sources, s.measurements, s.presentation


def test_capture_blocks_pending_stale_source_and_changed_during_read() -> None:
    snapshot = _snapshot((0, 0, 4, 5))
    adapter = _FakeAdapter(snapshot)
    captured = capture_presented_analysis(adapter, snapshot.token)
    assert captured.available
    assert captured.snapshot is not None
    assert captured.snapshot.measurements == snapshot.measurements
    adapter.presented = None
    assert capture_presented_analysis(adapter, snapshot.token).reason == "pending_or_uncomputed"
    adapter.presented = snapshot.token
    adapter.current = replace(
        snapshot.token, source_documents=((snapshot.token.source_documents[0][0], 8),)
    )
    assert capture_presented_analysis(adapter, snapshot.token).reason == "stale_or_mismatched"
    adapter.current = snapshot.token
    adapter.mutate_during_read = True
    assert capture_presented_analysis(adapter, snapshot.token).reason == "changed_during_capture"


def test_identical_roi_area_different_origin_are_distinct() -> None:
    first = _snapshot((0, 0, 4, 5))
    second = replace(first, token=replace(first.token, roi_ref=(3, 4, 4, 5)))
    assert serialize_analysis_context(first) != serialize_analysis_context(second)
    assert parse_analysis_context(serialize_analysis_context(second))["roi_ref"] == [3, 4, 4, 5]


@pytest.mark.parametrize("dtype", ["uint8", "uint16", "int32", "float32", ">u2", ">f4", "<u2"])
def test_native_dtype_roundtrip_preserves_endianness(dtype: str) -> None:
    snapshot = _snapshot()
    source = replace(snapshot.sources[0], native_dtype=dtype)
    parsed = parse_analysis_context(
        serialize_analysis_context(replace(snapshot, sources=(source,)))
    )
    assert parsed["sources"][0]["native_dtype"] == dtype


@pytest.mark.parametrize("dtype", ["object", "float8", "../uint16", r"C:\private\uint16"])
def test_native_dtype_rejects_non_numeric_or_path_values(dtype: str) -> None:
    snapshot = _snapshot()
    with pytest.raises(ValueError, match="native format"):
        replace(snapshot.sources[0], native_dtype=dtype)
    data = parse_analysis_context(serialize_analysis_context(snapshot))
    data["sources"][0]["native_dtype"] = dtype
    with pytest.raises(ValueError, match="native signature"):
        parse_analysis_context(json.dumps(data).encode())


def test_analysis_labels_accept_producer_values_and_reject_path_separators() -> None:
    snapshot = _snapshot()
    assert snapshot.token.channel == "All"
    assert snapshot.token.domain == "native"
    assert snapshot.measurements[0].metric == "Mean"
    for channel in (r"w\w", "folder/R"):
        with pytest.raises(ValueError, match="channel/domain"):
            replace(snapshot.token, channel=channel)


def test_snapshot_rejects_generation_and_profile_mismatch() -> None:
    snap = _snapshot()
    with pytest.raises(ValueError, match="generations"):
        replace(snap, sources=(replace(snap.sources[0], generation=8),))
    with pytest.raises(ValueError, match="profiles"):
        replace(snap, sources=(replace(snap.sources[0], profile_signature="b" * 64),))
    with pytest.raises(ValueError, match="half-open"):
        replace(snap.token, roi_ref=(1, 2, 0, 4))


def test_nonfinite_values_have_explicit_state_and_no_json_nan() -> None:
    snap = _snapshot()
    nan = measurement(snap.sources[0].source_key, "R", "PSNR", float("inf"), 20)
    assert nan.state == "pos_inf" and nan.value is None
    snap = replace(snap, measurements=(nan,))
    raw = serialize_analysis_context(snap)
    assert b"Infinity" not in raw
    assert parse_analysis_context(raw)["measurements"][0]["state"] == "pos_inf"
    with pytest.raises(ValueError):
        AnalysisMeasurementV1(snap.sources[0].source_key, "R", "Mean", float("nan"), 10)


def test_context_roundtrip_excludes_private_source_data() -> None:
    snap = _snapshot()
    raw = serialize_analysis_context(snap)
    parsed = parse_analysis_context(raw)
    assert parsed["kind"] == "pixelscope-analysis-context"
    assert parsed["sources"][0]["verification"] == "unverified"
    assert snap.sources[0].document_id.encode() not in raw
    assert b"source_path" not in raw
    assert b"alias" not in raw


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema_version=2),
        lambda d: d.update(kind="pixelscope-session"),
        lambda d: d.update(roi_ref=[-1, 0, 4, 5], scope="roi"),
        lambda d: d.update(roi_ref=[0, 0, 4, 5], scope="full"),
        lambda d: d["sources"][0].update(source_path="/home/user/private.raw"),
        lambda d: d["measurements"][0].update(value=float("nan")),
        lambda d: d["sources"][0].update(verification="verified"),
        lambda d: d.update(schema_version=True),
    ],
)
def test_invalid_context_schema_is_rejected(mutation: object) -> None:
    data = parse_analysis_context(serialize_analysis_context(_snapshot()))
    data = copy.deepcopy(data)
    mutation(data)  # type: ignore[operator]
    with pytest.raises((ValueError, TypeError)):
        parse_analysis_context(json.dumps(data).encode("utf-8"))


def test_duplicate_json_keys_rejected() -> None:
    raw = serialize_analysis_context(_snapshot())
    hostile = raw.replace(b'"schema_version":1', b'"schema_version":1,"schema_version":1')
    with pytest.raises(ValueError, match="duplicate"):
        parse_analysis_context(hostile)


def test_zip_roundtrip_and_private_path_sentinel(tmp_path: Path) -> None:
    snap = _snapshot((1, 2, 4, 5))
    target = tmp_path / "bundle.zip"
    write_analysis_bundle(target, (snap,))
    manifest = verify_analysis_bundle(target)
    assert manifest["snapshot_count"] == 1
    with ZipFile(target) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert {
            "manifest.json",
            "data/context.json",
            "data/measurements.csv",
            "data/measurements.json",
        } == set(names)
        for name in names:
            payload = archive.read(name)
            assert b"C:\\\\Users\\\\secret" not in payload
            assert b"/home/private" not in payload
            assert b"private.raw" not in payload


def test_cancel_and_write_failure_never_publish_partial_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snap = _snapshot()
    target = tmp_path / "bundle.zip"
    with pytest.raises(RuntimeError, match="cancel"):
        write_analysis_bundle(target, (snap,), cancelled=lambda: True)
    assert not target.exists()
    assert not list(tmp_path.glob("*.tmp"))

    def deny(_source: Path, _target: Path) -> None:
        raise PermissionError("simulated replace failure")

    monkeypatch.setattr("pixelscope.io.analysis_bundle.os.replace", deny)
    with pytest.raises(PermissionError):
        write_analysis_bundle(target, (snap,))
    assert not target.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_target_collision_requires_overwrite_token(tmp_path: Path) -> None:
    snap = _snapshot()
    target = tmp_path / "bundle.zip"
    target.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        write_analysis_bundle(target, (snap,))
    assert target.read_bytes() == b"existing"
    previous = target.stat()
    write_analysis_bundle(
        target,
        (snap,),
        expected_existing=(previous.st_dev, previous.st_ino, previous.st_mtime_ns),
    )
    assert verify_analysis_bundle(target)["kind"] == "pixelscope-analysis-bundle"


def test_reject_manifest_tamper(tmp_path: Path) -> None:
    path = tmp_path / "bundle.zip"
    write_analysis_bundle(path, (_snapshot(),))
    with ZipFile(path, "a") as archive:
        archive.writestr("data/measurements.csv", b"forged")
    with pytest.raises(ValueError, match="duplicate"):
        verify_analysis_bundle(path)
